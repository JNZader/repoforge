"""Generation service — orchestrates the full documentation/skills pipeline.

Bridges FastAPI with the ``repoforge`` core library. Runs generation in
background tasks using ``asyncio.create_task``, publishes SSE events via
per-generation ``asyncio.Queue`` instances, and persists results to the DB.

Architecture follows the md-evals ``EvalService`` pattern exactly:
- In-memory event queues (no Redis needed)
- ``asyncio.Semaphore`` for concurrency control
- ``CircuitBreaker`` wraps LLM calls
- Synchronous repoforge functions wrapped with ``asyncio.to_thread``
"""

from __future__ import annotations

import asyncio
import os
import shutil
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy import select, update

from app.config import settings
from app.models import Generation, GenerationEvent, async_session_factory
from app.models import ProviderKey
from app.services.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError
from app.services import repo_cloner
from app.services.crypto import decrypt_key, derive_user_key
from app.services.session_keys import session_key_store

logger = structlog.get_logger(__name__)


class GenerationService:
    """Manages generation lifecycle: clone, scan, generate, stream, persist."""

    def __init__(self) -> None:
        self._event_queues: dict[str, asyncio.Queue[dict[str, Any]]] = {}
        self._tasks: dict[str, asyncio.Task] = {}  # type: ignore[type-arg]
        self._semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_GENERATIONS)
        self.circuit_breaker = CircuitBreaker(threshold=5, reset_timeout_s=30.0)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start_generation(
        self,
        *,
        user_id: str,
        repo_url: str,
        config: dict[str, Any],
        api_key: str,
        provider: str,
        db: Any,
    ) -> dict[str, Any]:
        """Create a DB record, launch background task, return generation metadata.

        Args:
            user_id: UUID string of the authenticated user.
            repo_url: Validated GitHub repository URL.
            config: Generation config dict (mode, model, language, etc.).
            api_key: Resolved API key for the LLM provider.
            provider: LLM provider name.
            db: Async database session.

        Returns:
            Dict with ``generation_id``, ``status``, ``created_at``.
        """
        repo_name = repo_cloner._extract_repo_name(repo_url)
        mode = config.get("mode", "docs")

        # Create DB record
        generation = Generation(
            user_id=user_id,
            repo_url=repo_url,
            repo_name=repo_name,
            mode=mode,
            status="queued",
            config=config,
        )
        db.add(generation)
        await db.commit()
        await db.refresh(generation)

        generation_id = str(generation.id)
        created_at = generation.created_at

        # Create event queue for SSE consumers
        self._event_queues[generation_id] = asyncio.Queue()

        # Resolve github_token for private repo access
        github_token = await self._resolve_github_token(user_id)

        # Launch background execution
        task = asyncio.create_task(
            self._execute(
                generation_id=generation_id,
                repo_url=repo_url,
                config=config,
                api_key=api_key,
                provider=provider,
                user_id=user_id,
                github_token=github_token,
            )
        )
        self._tasks[generation_id] = task

        logger.info(
            "generation_queued",
            generation_id=generation_id,
            repo=repo_name,
            mode=mode,
        )

        return {
            "generation_id": generation_id,
            "status": "queued",
            "created_at": created_at,
        }

    def get_event_queue(self, generation_id: str) -> asyncio.Queue[dict[str, Any]] | None:
        """Get SSE event queue for a generation. Returns None if not found."""
        return self._event_queues.get(generation_id)

    async def cancel(self, generation_id: str) -> bool:
        """Cancel a running generation. Returns True if it was running."""
        task = self._tasks.get(generation_id)
        if task and not task.done():
            task.cancel()
            return True
        return False

    async def shutdown(self) -> None:
        """Cancel all running tasks (graceful shutdown)."""
        if not self._tasks:
            return
        logger.info("generation_service_shutdown", active=len(self._tasks))
        for task in self._tasks.values():
            task.cancel()
        await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._tasks.clear()

    def active_count(self) -> int:
        """Count of currently running (non-done) generation tasks."""
        return sum(1 for t in self._tasks.values() if not t.done())

    # ------------------------------------------------------------------
    # Background execution pipeline
    # ------------------------------------------------------------------

    async def _execute(
        self,
        generation_id: str,
        repo_url: str,
        config: dict[str, Any],
        api_key: str,
        provider: str,
        user_id: str,
        github_token: str | None = None,
    ) -> None:
        """The actual generation pipeline — runs in a background task.

        Steps:
            1. Clone repo (shallow)
            2. Scan codebase (deterministic, no LLM)
            3. Build LLM with provider API key
            4. Generate docs/skills/both
            5. Package output as ZIP
            6. Update DB with results
        """
        clone_dir: Path | None = None
        start_time = time.monotonic()
        env_key_set: str | None = None

        async with self._semaphore:
            try:
                # --- Phase 1: Clone ---
                await self._emit(generation_id, "generation_started", repo_url=repo_url, mode=config.get("mode", "docs"))
                await self._emit(generation_id, "phase_changed", phase="cloning")
                await self._update_status(generation_id, "cloning")

                clone_dir = await repo_cloner.clone(repo_url, github_token=github_token)

                # --- Phase 2: Scan (deterministic, no LLM) ---
                await self._emit(generation_id, "phase_changed", phase="scanning")
                await self._update_status(generation_id, "scanning")

                from repoforge.scanner import scan_repo, classify_complexity

                repo_map = await asyncio.to_thread(scan_repo, str(clone_dir))
                complexity = classify_complexity(repo_map)

                layers = list(repo_map.get("layers", {}).keys())
                total_files = repo_map.get("stats", {}).get("total_files", 0)

                await self._emit(
                    generation_id,
                    "scan_complete",
                    layers=len(layers),
                    layer_names=layers,
                    files=total_files,
                    complexity=complexity["size"],
                    tech_stack=repo_map.get("tech_stack", []),
                )

                # --- Phase 3: Set up LLM ---
                # The repoforge build_llm reads API key from env vars if not passed directly.
                # We set the appropriate env var, call build_llm, then clean up.
                env_key_set = self._set_provider_env(provider, api_key)

                from repoforge.llm import build_llm

                model = config.get("model", "claude-haiku-3-5")

                # For GitHub Models, the model name must be prefixed with
                # "github/" so build_llm can detect the provider and set the
                # correct api_base (models.inference.ai.azure.com).
                # Without the prefix, a model like "claude-3-5-haiku-20241022"
                # would match the "claude" (Anthropic) preset and miss the
                # GitHub Models api_base entirely, causing all LLM calls to fail.
                litellm_model = self._to_litellm_model(provider, model)

                llm = build_llm(model=litellm_model, api_key=api_key)

                # --- Phase 4: Generate ---
                await self._emit(generation_id, "phase_changed", phase="generating")
                await self._update_status(generation_id, "generating", started_at=datetime.now(timezone.utc))

                mode = config.get("mode", "docs")
                language = config.get("language", "English")
                complexity_override = config.get("complexity", "auto")
                output_dir = clone_dir / "_repoforge_output"
                output_dir.mkdir(parents=True, exist_ok=True)

                files_generated = 0
                result_metadata: dict[str, Any] = {
                    "complexity": complexity,
                    "mode": mode,
                    "model": model,
                    "provider": provider,
                }

                if mode in ("docs", "both"):
                    from repoforge.docs_generator import generate_docs

                    docs_output = output_dir / "docs"
                    docs_output.mkdir(parents=True, exist_ok=True)

                    await self._emit(generation_id, "chapter_started", index=0, total=0, title="Documentation")

                    docs_result = await self.circuit_breaker.execute(
                        asyncio.to_thread,
                        generate_docs,
                        working_dir=str(clone_dir),
                        output_dir=str(docs_output),
                        model=litellm_model,
                        api_key=api_key,
                        language=language,
                        verbose=False,
                        complexity=complexity_override,
                    )

                    chapters_generated = docs_result.get("chapters_generated", [])
                    docsify_files = docs_result.get("docsify_files", [])
                    errors = docs_result.get("errors", [])
                    files_generated += len(chapters_generated) + len(docsify_files)

                    if errors:
                        logger.warning(
                            "docs_chapter_errors",
                            generation_id=generation_id,
                            error_count=len(errors),
                            errors=errors,
                            model=litellm_model,
                            provider=provider,
                        )

                    result_metadata["docs"] = {
                        "chapters": len(chapters_generated),
                        "docsify_files": len(docsify_files),
                        "errors": len(errors),
                        "error_details": errors[:5] if errors else [],  # store first 5 error details
                        "project_name": docs_result.get("project_name", ""),
                        "language": docs_result.get("language", language),
                    }

                    # Emit per-chapter completion events
                    for i, chapter_path in enumerate(chapters_generated, 1):
                        chapter_name = Path(chapter_path).name
                        await self._emit(
                            generation_id,
                            "chapter_completed",
                            index=i,
                            total=len(chapters_generated),
                            title=chapter_name,
                        )

                if mode in ("skills", "both"):
                    from repoforge.generator import generate_artifacts

                    skills_output = output_dir / ".claude"
                    skills_output.mkdir(parents=True, exist_ok=True)

                    await self._emit(generation_id, "skill_started", index=0, total=0, layer="all", module="all")

                    skills_result = await self.circuit_breaker.execute(
                        asyncio.to_thread,
                        generate_artifacts,
                        working_dir=str(clone_dir),
                        output_dir=str(skills_output),
                        model=litellm_model,
                        api_key=api_key,
                        verbose=False,
                        complexity=complexity_override,
                    )

                    skills_generated = skills_result.get("skills", [])
                    agents_generated = skills_result.get("agents", [])
                    files_generated += len(skills_generated) + len(agents_generated)
                    result_metadata["skills"] = {
                        "skills_count": len(skills_generated),
                        "agents_count": len(agents_generated),
                        "complexity": skills_result.get("complexity", {}),
                    }

                    # Emit per-skill completion events
                    for i, skill_path in enumerate(skills_generated, 1):
                        skill_name = Path(skill_path).stem
                        await self._emit(
                            generation_id,
                            "skill_completed",
                            index=i,
                            total=len(skills_generated),
                            layer="",
                            module=skill_name,
                        )

                # --- Phase 5: Package as ZIP ---
                await self._emit(generation_id, "phase_changed", phase="packaging")

                zip_path = self._create_zip(output_dir, generation_id)

                # --- Phase 6: Update DB ---
                duration_ms = int((time.monotonic() - start_time) * 1000)

                await self._update_completed(
                    generation_id=generation_id,
                    result_metadata=result_metadata,
                    files_generated=files_generated,
                    total_duration_ms=duration_ms,
                    artifact_path=zip_path,
                )

                await self._emit(
                    generation_id,
                    "generation_completed",
                    duration_ms=duration_ms,
                    files_generated=files_generated,
                )

                logger.info(
                    "generation_completed",
                    generation_id=generation_id,
                    duration_ms=duration_ms,
                    files=files_generated,
                )

            except CircuitBreakerOpenError:
                await self._update_failed(
                    generation_id, "LLM provider temporarily unavailable (circuit breaker open)"
                )
                await self._emit(
                    generation_id,
                    "generation_error",
                    error="LLM provider temporarily unavailable. Please try again later.",
                )
                logger.warning("generation_circuit_breaker_open", generation_id=generation_id)

            except asyncio.CancelledError:
                await self._update_failed(generation_id, "cancelled")
                await self._emit(generation_id, "generation_cancelled")
                logger.info("generation_cancelled", generation_id=generation_id)

            except Exception as exc:
                error_id = str(uuid.uuid4())[:8]
                await self._update_failed(generation_id, str(exc), error_id=error_id)
                await self._emit(
                    generation_id,
                    "generation_error",
                    error=str(exc),
                    error_id=error_id,
                )
                logger.error(
                    "generation_failed",
                    generation_id=generation_id,
                    error=str(exc),
                    error_id=error_id,
                    exc_info=True,
                )

            finally:
                # Clean up env var
                if env_key_set:
                    os.environ.pop(env_key_set, None)

                # Clean up clone directory
                if clone_dir and clone_dir.exists():
                    shutil.rmtree(clone_dir, ignore_errors=True)

                # Remove task reference
                self._tasks.pop(generation_id, None)

                # Clean up event queue after a delay (allow SSE clients to catch up)
                loop = asyncio.get_running_loop()
                loop.call_later(60, self._cleanup_queue, generation_id)

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    async def _emit(self, generation_id: str, event_type: str, **payload: Any) -> None:
        """Push event to SSE queue and persist to DB (fire-and-forget)."""
        event: dict[str, Any] = {
            "type": event_type,
            "generation_id": generation_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **payload,
        }

        # Push to SSE queue
        queue = self._event_queues.get(generation_id)
        if queue:
            await queue.put(event)

        # Persist to DB (fire-and-forget — don't block the pipeline)
        asyncio.create_task(self._persist_event(generation_id, event_type, event))

    async def _persist_event(
        self, generation_id: str, event_type: str, payload: dict[str, Any]
    ) -> None:
        """Save an event to the generation_events table."""
        try:
            async with async_session_factory() as session:
                event = GenerationEvent(
                    generation_id=generation_id,
                    event_type=event_type,
                    payload=payload,
                )
                session.add(event)
                await session.commit()
        except (OSError, RuntimeError, ConnectionError) as exc:
            # Fire-and-forget — never let event persistence crash the pipeline
            logger.debug("event_persist_failed", generation_id=generation_id,
                         event_type=event_type, error=str(exc))

    # ------------------------------------------------------------------
    # DB updates
    # ------------------------------------------------------------------

    async def _update_status(
        self,
        generation_id: str,
        status: str,
        started_at: datetime | None = None,
    ) -> None:
        """Update generation status in DB."""
        values: dict[str, Any] = {"status": status}
        if started_at:
            values["started_at"] = started_at
        try:
            async with async_session_factory() as session:
                await session.execute(
                    update(Generation)
                    .where(Generation.id == generation_id)
                    .values(**values)
                )
                await session.commit()
        except (OSError, RuntimeError, ConnectionError):
            # DB write failure — log and continue, don't crash the pipeline
            logger.debug("status_update_failed", generation_id=generation_id, status=status)

    async def _update_completed(
        self,
        generation_id: str,
        result_metadata: dict[str, Any],
        files_generated: int,
        total_duration_ms: int,
        artifact_path: str,
    ) -> None:
        """Mark generation as completed with results."""
        async with async_session_factory() as session:
            await session.execute(
                update(Generation)
                .where(Generation.id == generation_id)
                .values(
                    status="completed",
                    result_metadata=result_metadata,
                    files_generated=files_generated,
                    total_duration_ms=total_duration_ms,
                    artifact_path=artifact_path,
                    completed_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()

    async def _update_failed(
        self,
        generation_id: str,
        error_message: str,
        error_id: str | None = None,
    ) -> None:
        """Mark generation as failed with error info."""
        try:
            async with async_session_factory() as session:
                await session.execute(
                    update(Generation)
                    .where(Generation.id == generation_id)
                    .values(
                        status="failed",
                        error_message=error_message,
                        error_id=error_id,
                        completed_at=datetime.now(timezone.utc),
                    )
                )
                await session.commit()
        except (OSError, RuntimeError, ConnectionError):
            # DB write failure — log and continue
            logger.debug("failed_update_failed", generation_id=generation_id)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _resolve_api_key(self, user_id: str, provider: str) -> str:
        """Resolve API key: session key (in-memory) > persistent key (DB).

        Follows the md-evals pattern for key resolution.
        """
        # 1. Check session keys first
        session_entry = await session_key_store.get_key(user_id, provider)
        if session_entry is not None:
            return session_entry.api_key

        # 2. Fall back to persistent keys in DB
        async with async_session_factory() as session:
            result = await session.execute(
                select(ProviderKey).where(
                    ProviderKey.user_id == user_id,
                    ProviderKey.provider == provider,
                )
            )
            row = result.scalar_one_or_none()

        if row is None:
            if provider == "github-models":
                raise ValueError(
                    "GitHub Models requires a Personal Access Token (PAT) — "
                    "the OAuth login token doesn't work for inference. "
                    "Add one in Settings > Provider Keys."
                )
            raise ValueError(
                f"No API key configured for '{provider}'. "
                f"Add one in Settings > Provider Keys."
            )

        master_key = bytes.fromhex(settings.ENCRYPTION_KEY)
        user_key = derive_user_key(master_key, user_id)
        return decrypt_key(row.encrypted_api_key, user_key)

    async def _resolve_github_token(self, user_id: str) -> str | None:
        """Try to get the user's GitHub token for private repo access."""
        try:
            from app.models import User
            async with async_session_factory() as session:
                result = await session.execute(
                    select(User).where(User.id == user_id)
                )
                user = result.scalar_one_or_none()
                if user and user.github_token:
                    master_key = bytes.fromhex(settings.ENCRYPTION_KEY)
                    user_key = derive_user_key(master_key, str(user.id))
                    return decrypt_key(user.github_token, user_key)
        except (OSError, RuntimeError, ConnectionError, ValueError) as exc:
            # DB read, decryption, or key derivation failures
            logger.debug("github_token_resolve_failed", user_id=user_id, error=str(exc))
        return None

    @staticmethod
    def _to_litellm_model(provider: str, model: str) -> str:
        """Prefix the model name with the LiteLLM provider prefix when needed.

        The repoforge ``build_llm`` function uses the model string prefix to
        detect the provider and configure api_base / api_key_env accordingly.
        When the web frontend sends ``provider="github-models"`` with
        ``model="claude-3-5-haiku-20241022"``, build_llm would match the
        ``claude`` (Anthropic) preset and miss the GitHub Models api_base.

        This method ensures the model name carries the correct LiteLLM
        prefix so routing works correctly.
        """
        # Mapping from our provider id → litellm prefix
        prefix_map: dict[str, str] = {
            "github-models": "github",
            "groq": "groq",
            "google": "gemini",
            "mistral": "mistral",
        }

        prefix = prefix_map.get(provider)

        # No prefix needed for anthropic/openai — LiteLLM auto-detects them
        if not prefix:
            return model

        # Don't double-prefix
        if model.startswith(f"{prefix}/"):
            return model

        return f"{prefix}/{model}"

    @staticmethod
    def _set_provider_env(provider: str, api_key: str) -> str | None:
        """Set the appropriate environment variable for the LLM provider.

        Returns the env var name that was set, or None.
        The caller MUST clean this up in a finally block.
        """
        env_map = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "groq": "GROQ_API_KEY",
            "google": "GEMINI_API_KEY",
            "github-models": "GITHUB_TOKEN",
            "mistral": "MISTRAL_API_KEY",
        }
        env_var = env_map.get(provider)
        if env_var:
            os.environ[env_var] = api_key
            return env_var
        return None

    @staticmethod
    def _create_zip(output_dir: Path, generation_id: str) -> str:
        """Create a ZIP file from the output directory.

        Returns the absolute path to the ZIP file.
        """
        artifacts_dir = Path(settings.CLONE_BASE_DIR) / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        zip_path = artifacts_dir / f"{generation_id}.zip"

        with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in output_dir.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(output_dir)
                    zf.write(file_path, arcname)

        return str(zip_path)

    def _cleanup_queue(self, generation_id: str) -> None:
        """Remove an event queue after a delay (called via call_later)."""
        self._event_queues.pop(generation_id, None)


# Module-level singleton
generation_service = GenerationService()
