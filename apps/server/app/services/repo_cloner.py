"""Async git clone service for repository fetching.

Handles:
- Shallow clones (--depth=1 --single-branch) for speed
- Authenticated URLs for private repos via GitHub token
- Configurable timeout (default 60s)
- Post-clone size validation
- URL validation (GitHub only)
"""

from __future__ import annotations

import asyncio
import re
import shutil
import uuid
from pathlib import Path

import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

# Only allow github.com URLs
_GITHUB_URL_RE = re.compile(
    r"^https://github\.com/[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+/?$"
)

# Clone timeout in seconds
_CLONE_TIMEOUT_S = 60


def _validate_url(repo_url: str) -> str:
    """Validate and normalize a GitHub repository URL.

    Raises:
        ValueError: If the URL is not a valid github.com repository URL.
    """
    cleaned = repo_url.rstrip("/").split("?")[0].split("#")[0]
    if not _GITHUB_URL_RE.match(cleaned):
        raise ValueError(
            f"Invalid repository URL: must be https://github.com/owner/repo — got {repo_url!r}"
        )
    return cleaned


def _build_auth_url(repo_url: str, github_token: str) -> str:
    """Inject a GitHub token into a clone URL for private repo access.

    Format: https://x-access-token:{token}@github.com/owner/repo.git
    """
    return repo_url.replace(
        "https://github.com/",
        f"https://x-access-token:{github_token}@github.com/",
    )


def _dir_size_mb(path: Path) -> float:
    """Calculate directory size in megabytes (excluding .git)."""
    total = 0
    for f in path.rglob("*"):
        if f.is_file() and ".git" not in f.parts:
            total += f.stat().st_size
    return total / (1024 * 1024)


async def clone(repo_url: str, github_token: str | None = None) -> Path:
    """Clone a GitHub repository asynchronously.

    Uses ``asyncio.create_subprocess_exec`` with ``--depth=1 --single-branch``
    for fast shallow clones.

    Args:
        repo_url: GitHub repository URL (https://github.com/owner/repo).
        github_token: Optional GitHub token for private repo access.

    Returns:
        Path to the cloned directory.

    Raises:
        ValueError: If the URL is invalid or the clone exceeds size limits.
        TimeoutError: If the clone takes longer than 60 seconds.
        RuntimeError: If git clone fails.
    """
    clean_url = _validate_url(repo_url)

    # Build the clone URL (with auth if needed)
    clone_url = clean_url
    if github_token:
        clone_url = _build_auth_url(clean_url, github_token)

    # Ensure .git suffix for git clone
    if not clone_url.endswith(".git"):
        clone_url += ".git"

    # Create unique clone directory
    clone_base = Path(settings.CLONE_BASE_DIR)
    clone_base.mkdir(parents=True, exist_ok=True)
    clone_dir = clone_base / f"repo-{uuid.uuid4().hex[:12]}"

    # Log with clean URL (no token)
    repo_name = _extract_repo_name(clean_url)
    logger.info("clone_start", repo=repo_name, target=str(clone_dir))

    try:
        process = await asyncio.create_subprocess_exec(
            "git",
            "clone",
            "--depth=1",
            "--single-branch",
            clone_url,
            str(clone_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=_CLONE_TIMEOUT_S,
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            # Clean up partial clone
            shutil.rmtree(clone_dir, ignore_errors=True)
            raise TimeoutError(
                f"Git clone timed out after {_CLONE_TIMEOUT_S}s for {repo_name}"
            )

        if process.returncode != 0:
            stderr_text = stderr.decode(errors="replace").strip()
            # Sanitize: never log the full URL (may contain token)
            safe_error = stderr_text.replace(clone_url, clean_url)
            shutil.rmtree(clone_dir, ignore_errors=True)
            raise RuntimeError(f"Git clone failed for {repo_name}: {safe_error}")

    except (TimeoutError, RuntimeError):
        raise
    except Exception as exc:
        shutil.rmtree(clone_dir, ignore_errors=True)
        raise RuntimeError(f"Git clone failed for {repo_name}: {exc}") from exc

    # Size check
    max_mb = settings.MAX_REPO_SIZE_MB
    size_mb = await asyncio.to_thread(_dir_size_mb, clone_dir)
    if size_mb > max_mb:
        shutil.rmtree(clone_dir, ignore_errors=True)
        raise ValueError(
            f"Repository {repo_name} is too large: {size_mb:.1f}MB (max {max_mb}MB)"
        )

    logger.info("clone_complete", repo=repo_name, size_mb=round(size_mb, 1))
    return clone_dir


def _extract_repo_name(repo_url: str) -> str:
    """Extract 'owner/repo' from a GitHub URL."""
    parts = repo_url.rstrip("/").split("/")
    if len(parts) >= 2:
        return f"{parts[-2]}/{parts[-1]}"
    return repo_url
