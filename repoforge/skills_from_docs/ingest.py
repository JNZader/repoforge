"""
ingest.py - Multi-source documentation ingestion.

Supports three source types:
  - HTTP/HTTPS URL: fetches HTML content
  - GitHub repo URL: clones to temp dir, reads .md files
  - Local directory: reads .md/.html files recursively

No external dependencies — uses stdlib urllib + subprocess.
"""

import logging
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from .types import SourceType

logger = logging.getLogger(__name__)

# GitHub URL pattern: https://github.com/owner/repo or https://github.com/owner/repo.git
_GITHUB_RE = re.compile(
    r"^https?://github\.com/[\w.\-]+/[\w.\-]+(\.git)?/?$"
)

# Generic URL pattern
_URL_RE = re.compile(r"^https?://")

# Max file size to read (5 MB)
_MAX_FILE_SIZE = 5 * 1024 * 1024

# Max total content size (20 MB)
_MAX_TOTAL_SIZE = 20 * 1024 * 1024


def detect_source_type(source: str) -> SourceType:
    """Auto-detect the source type from the input string.

    Returns:
        SourceType enum value.

    Raises:
        ValueError: If source type cannot be determined.
    """
    if _GITHUB_RE.match(source):
        return SourceType.GITHUB_REPO
    if _URL_RE.match(source):
        return SourceType.URL
    if Path(source).is_dir():
        return SourceType.LOCAL_DIR
    raise ValueError(
        f"Cannot determine source type for: {source!r}. "
        "Expected an HTTP(S) URL, GitHub repo URL, or existing local directory."
    )


def fetch_url(url: str, *, timeout: int = 30) -> list[str]:
    """Fetch content from an HTTP(S) URL.

    Returns:
        List with a single string containing the fetched content.

    Raises:
        RuntimeError: On network or HTTP errors.
    """
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "repoforge/0.4 (skills-from-docs)"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(_MAX_FILE_SIZE)
            charset = resp.headers.get_content_charset() or "utf-8"
            return [raw.decode(charset, errors="replace")]
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} fetching {url}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Failed to fetch {url}: {exc.reason}") from exc
    except Exception as exc:
        raise RuntimeError(f"Failed to fetch {url}: {exc}") from exc


def clone_github_repo(url: str) -> list[str]:
    """Clone a GitHub repo to a temp dir and read all markdown files.

    Returns:
        List of markdown file contents.

    Raises:
        RuntimeError: If git clone fails or no markdown files found.
    """
    # Ensure .git suffix for clone
    clone_url = url.rstrip("/")
    if not clone_url.endswith(".git"):
        clone_url += ".git"

    tmpdir = tempfile.mkdtemp(prefix="repoforge-docs-")
    try:
        logger.info("Cloning %s to %s ...", clone_url, tmpdir)
        result = subprocess.run(
            ["git", "clone", "--depth=1", "--single-branch", clone_url, tmpdir],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"git clone failed (exit {result.returncode}): {result.stderr.strip()}"
            )

        return _read_markdown_dir(Path(tmpdir))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def read_local_dir(path: str) -> list[str]:
    """Read all markdown and HTML files from a local directory.

    Returns:
        List of file contents.

    Raises:
        RuntimeError: If directory doesn't exist or contains no docs.
    """
    dirpath = Path(path)
    if not dirpath.is_dir():
        raise RuntimeError(f"Directory does not exist: {path}")

    return _read_markdown_dir(dirpath)


def _read_markdown_dir(dirpath: Path) -> list[str]:
    """Read .md and .html files from a directory tree.

    Respects _MAX_FILE_SIZE and _MAX_TOTAL_SIZE limits.
    """
    contents: list[str] = []
    total_size = 0
    extensions = {".md", ".markdown", ".mdx", ".html", ".htm", ".rst", ".txt"}

    # Sort for deterministic ordering
    files = sorted(
        f
        for f in dirpath.rglob("*")
        if f.is_file()
        and f.suffix.lower() in extensions
        and ".git" not in f.parts
        and "node_modules" not in f.parts
    )

    if not files:
        raise RuntimeError(
            f"No documentation files found in {dirpath}. "
            f"Looked for: {', '.join(sorted(extensions))}"
        )

    for filepath in files:
        if filepath.stat().st_size > _MAX_FILE_SIZE:
            logger.warning("Skipping oversized file: %s", filepath)
            continue
        if total_size > _MAX_TOTAL_SIZE:
            logger.warning("Total content size limit reached, stopping at %s", filepath)
            break

        try:
            text = filepath.read_text(encoding="utf-8", errors="replace")
            contents.append(text)
            total_size += len(text)
        except OSError as exc:
            logger.warning("Failed to read %s: %s", filepath, exc)

    return contents


def ingest(source: str) -> list[str]:
    """Main entry point: detect source type and fetch content.

    Returns:
        List of raw text contents from the source.

    Raises:
        ValueError: If source type cannot be determined.
        RuntimeError: On fetch/clone/read errors.
    """
    source_type = detect_source_type(source)

    if source_type == SourceType.URL:
        logger.info("Fetching URL: %s", source)
        return fetch_url(source)
    elif source_type == SourceType.GITHUB_REPO:
        logger.info("Cloning GitHub repo: %s", source)
        return clone_github_repo(source)
    elif source_type == SourceType.LOCAL_DIR:
        logger.info("Reading local directory: %s", source)
        return read_local_dir(source)
    else:
        raise ValueError(f"Unsupported source type: {source_type}")
