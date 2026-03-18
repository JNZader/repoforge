"""Generation routes — start, stream, cancel, download.

Endpoints:
    POST /api/generate           — Start a new generation job (202 Accepted)
    GET  /api/generate/{id}/stream — SSE event stream for real-time progress
    GET  /api/generate/{id}      — Get generation details (status, metadata)
    POST /api/generate/{id}/cancel — Cancel a running generation
    GET  /api/generate/{id}/download — Download ZIP artifact
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from pathlib import Path

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.middleware.auth import CurrentUser
from app.middleware.rate_limit import API_LIMIT, GENERATE_LIMIT, get_user_id_key, limiter
from app.models import Generation, get_db
from app.models.schemas import GenerateRequest, GenerateResponse, GenerationDetail
from app.services.generation_service import generation_service

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/generate", tags=["generate"])


# ---------- POST /api/generate ----------


@router.post("", response_model=GenerateResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit(GENERATE_LIMIT, key_func=get_user_id_key)
async def start_generation(
    request: Request,
    body: GenerateRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> GenerateResponse:
    """Start a new documentation/skills generation job.

    Returns 202 Accepted immediately with a generation_id.
    Connect to ``GET /api/generate/{id}/stream`` for real-time SSE progress.

    The API key is resolved in priority order:
    1. Session key (in-memory, highest priority)
    2. Persistent key (encrypted in DB)
    3. Error if no key is configured for the provider
    """
    user_id = current_user["sub"]

    # Resolve API key before launching the generation
    try:
        api_key = await generation_service._resolve_api_key(user_id, body.provider)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "missing_api_key", "message": str(exc)},
        ) from exc

    # Build config dict from request
    config = {
        "mode": body.mode,
        "model": body.model,
        "provider": body.provider,
        "language": body.language,
        "complexity": body.complexity,
    }
    if body.options:
        config["options"] = body.options

    try:
        result = await generation_service.start_generation(
            user_id=user_id,
            repo_url=body.repo_url,
            config=config,
            api_key=api_key,
            provider=body.provider,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_request", "message": str(exc)},
        ) from exc

    return GenerateResponse(
        generation_id=result["generation_id"],
        status=result["status"],
        created_at=result["created_at"],
    )


# ---------- GET /api/generate/{generation_id}/stream ----------


@router.get("/{generation_id}/stream")
@limiter.limit(API_LIMIT, key_func=get_user_id_key)
async def stream_generation(
    request: Request,
    generation_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> EventSourceResponse:
    """SSE stream of generation progress events.

    Events: ``generation_started``, ``phase_changed``, ``scan_complete``,
    ``chapter_started``, ``chapter_completed``, ``skill_started``,
    ``skill_completed``, ``generation_completed``, ``generation_error``,
    ``generation_cancelled``.

    Auth: uses ``?token=`` query param (EventSource doesn't support headers).
    """
    user_id = current_user["sub"]

    # Verify ownership
    result = await db.execute(
        select(Generation).where(
            Generation.id == generation_id,
            Generation.user_id == user_id,
        )
    )
    generation = result.scalar_one_or_none()
    if not generation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Generation not found."},
        )

    # If generation is already completed/failed, return the final state
    if generation.status in ("completed", "failed", "cancelled"):
        async def completed_events() -> AsyncGenerator[dict[str, str], None]:
            if generation.status == "completed":
                yield {
                    "event": "generation_completed",
                    "data": json.dumps({
                        "type": "generation_completed",
                        "generation_id": generation_id,
                        "duration_ms": generation.total_duration_ms or 0,
                        "files_generated": generation.files_generated or 0,
                    }),
                }
            elif generation.status == "failed":
                yield {
                    "event": "generation_error",
                    "data": json.dumps({
                        "type": "generation_error",
                        "generation_id": generation_id,
                        "error": generation.error_message or "Unknown error",
                    }),
                }
            else:
                yield {
                    "event": "generation_cancelled",
                    "data": json.dumps({
                        "type": "generation_cancelled",
                        "generation_id": generation_id,
                    }),
                }

        return EventSourceResponse(completed_events())

    # Stream live events from the queue
    async def event_generator() -> AsyncGenerator[dict[str, str], None]:
        queue = generation_service.get_event_queue(generation_id)
        if queue is None:
            # Queue might have been cleaned up — send a synthetic event
            yield {
                "event": "generation_error",
                "data": json.dumps({
                    "type": "generation_error",
                    "generation_id": generation_id,
                    "error": "Event stream not available. Refresh to check generation status.",
                }),
            }
            return

        terminal_events = {"generation_completed", "generation_error", "generation_cancelled"}
        while True:
            try:
                event = await queue.get()
                yield {
                    "event": event["type"],
                    "data": json.dumps(event),
                }
                if event["type"] in terminal_events:
                    break
            except Exception:
                logger.exception("sse_error", generation_id=generation_id)
                break

    return EventSourceResponse(event_generator())


# ---------- GET /api/generate/{generation_id} ----------


@router.get("/{generation_id}", response_model=GenerationDetail)
@limiter.limit(API_LIMIT, key_func=get_user_id_key)
async def get_generation(
    request: Request,
    generation_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> GenerationDetail:
    """Get full generation details including status and result metadata."""
    user_id = current_user["sub"]
    result = await db.execute(
        select(Generation).where(
            Generation.id == generation_id,
            Generation.user_id == user_id,
        )
    )
    generation = result.scalar_one_or_none()
    if not generation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Generation not found."},
        )

    return GenerationDetail.model_validate(generation)


# ---------- POST /api/generate/{generation_id}/cancel ----------


@router.post("/{generation_id}/cancel")
@limiter.limit(API_LIMIT, key_func=get_user_id_key)
async def cancel_generation(
    request: Request,
    generation_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Cancel a running generation."""
    user_id = current_user["sub"]

    # Verify ownership
    result = await db.execute(
        select(Generation).where(
            Generation.id == generation_id,
            Generation.user_id == user_id,
        )
    )
    generation = result.scalar_one_or_none()
    if not generation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Generation not found."},
        )

    if generation.status not in ("queued", "cloning", "scanning", "generating"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "not_cancellable",
                "message": f"Generation is already {generation.status}.",
            },
        )

    cancelled = await generation_service.cancel(generation_id)
    if not cancelled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "not_running",
                "message": "Generation task is not currently running.",
            },
        )

    return {"generation_id": generation_id, "status": "cancelled"}


# ---------- GET /api/generate/{generation_id}/download ----------


@router.get("/{generation_id}/download")
@limiter.limit(API_LIMIT, key_func=get_user_id_key)
async def download_generation(
    request: Request,
    generation_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Download the generated output as a ZIP file."""
    user_id = current_user["sub"]
    result = await db.execute(
        select(Generation).where(
            Generation.id == generation_id,
            Generation.user_id == user_id,
        )
    )
    generation = result.scalar_one_or_none()
    if not generation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Generation not found."},
        )

    if generation.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "not_completed",
                "message": f"Generation is {generation.status}, not completed.",
            },
        )

    if not generation.artifact_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "no_artifact", "message": "No artifact available for this generation."},
        )

    artifact = Path(generation.artifact_path)
    if not artifact.exists():
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={
                "error": "artifact_expired",
                "message": "Artifact file has been cleaned up. Run the generation again.",
            },
        )

    filename = f"{generation.repo_name.replace('/', '-')}-{generation.mode}.zip"
    return FileResponse(
        path=str(artifact),
        media_type="application/zip",
        filename=filename,
    )
