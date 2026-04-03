"""
ingest.py - Multi-source documentation ingestion.

Supports six source types:
  - HTTP/HTTPS URL: fetches HTML content
  - GitHub repo URL: clones to temp dir, reads .md files
  - Local directory: reads .md/.html files recursively
  - PDF file: extracts text via pdfplumber (optional dep)
  - YouTube URL: downloads transcript via youtube-transcript-api (optional dep)
  - Jupyter notebook (.ipynb): parses JSON, extracts markdown + code cells

Core uses stdlib only. PDF and YouTube require optional extras:
  pip install repoforge[pdf]
  pip install repoforge[youtube]
"""

import json
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

# YouTube URL patterns
_YOUTUBE_RE = re.compile(
    r"^https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)[\w\-]+"
)

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
    # Check file extensions first (PDF, notebook)
    source_lower = source.lower()
    if source_lower.endswith(".pdf"):
        return SourceType.PDF
    if source_lower.endswith(".ipynb"):
        return SourceType.JUPYTER_NOTEBOOK

    # YouTube before generic URL (YouTube URLs would match generic URL otherwise)
    if _YOUTUBE_RE.match(source):
        return SourceType.YOUTUBE

    if _GITHUB_RE.match(source):
        return SourceType.GITHUB_REPO
    if _URL_RE.match(source):
        return SourceType.URL
    if Path(source).is_dir():
        return SourceType.LOCAL_DIR
    raise ValueError(
        f"Cannot determine source type for: {source!r}. "
        "Expected an HTTP(S) URL, GitHub repo URL, local directory, "
        ".pdf file, .ipynb notebook, or YouTube URL."
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
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        # OSError: network/socket errors; UnicodeDecodeError: charset issues; ValueError: URL errors
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


def extract_pdf(path: str) -> list[str]:
    """Extract text from a PDF file using pdfplumber.

    Requires: pip install repoforge[pdf]

    Returns:
        List with a single string containing all extracted page text.

    Raises:
        RuntimeError: If pdfplumber is not installed or file cannot be read.
    """
    try:
        import pdfplumber
    except ImportError:
        raise RuntimeError(
            "PDF support requires pdfplumber. "
            "Install it with: pip install repoforge[pdf]"
        )

    filepath = Path(path)
    if not filepath.is_file():
        raise RuntimeError(f"PDF file does not exist: {path}")

    try:
        pages_text: list[str] = []
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text and text.strip():
                    pages_text.append(text.strip())

        if not pages_text:
            raise RuntimeError(f"No text could be extracted from PDF: {path}")

        return ["\n\n".join(pages_text)]
    except RuntimeError:
        raise
    except (OSError, ValueError, TypeError) as exc:
        # OSError: file read error; ValueError/TypeError: PDF parsing failures
        raise RuntimeError(f"Failed to read PDF {path}: {exc}") from exc


def _extract_youtube_video_id(url: str) -> str:
    """Extract video ID from a YouTube URL.

    Supports:
      - https://www.youtube.com/watch?v=VIDEO_ID
      - https://youtu.be/VIDEO_ID
    """
    # youtube.com/watch?v=ID
    match = re.search(r"[?&]v=([\w\-]+)", url)
    if match:
        return match.group(1)

    # youtu.be/ID
    match = re.search(r"youtu\.be/([\w\-]+)", url)
    if match:
        return match.group(1)

    raise ValueError(f"Could not extract video ID from YouTube URL: {url}")


def fetch_youtube_transcript(url: str) -> list[str]:
    """Fetch transcript from a YouTube video.

    Requires: pip install repoforge[youtube]

    Returns:
        List with a single string containing the full transcript text.

    Raises:
        RuntimeError: If youtube-transcript-api is not installed or transcript unavailable.
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        raise RuntimeError(
            "YouTube support requires youtube-transcript-api. "
            "Install it with: pip install repoforge[youtube]"
        )

    try:
        video_id = _extract_youtube_video_id(url)
    except ValueError as exc:
        raise RuntimeError(str(exc)) from exc

    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        # Prefer manually created transcripts, fall back to generated
        try:
            transcript = transcript_list.find_manually_created_transcript(["en"])
        except (KeyError, ValueError, StopIteration, LookupError):
            # No manually-created English transcript available
            try:
                transcript = transcript_list.find_generated_transcript(["en"])
            except (KeyError, ValueError, StopIteration, LookupError):
                # No generated English transcript — try any available
                transcript = next(iter(transcript_list))

        segments = transcript.fetch()
        text = " ".join(
            segment.get("text", "") if isinstance(segment, dict) else str(segment)
            for segment in segments
        )
        if not text.strip():
            raise RuntimeError(f"Empty transcript for YouTube video: {url}")

        return [text.strip()]
    except RuntimeError:
        raise
    except (OSError, ValueError, StopIteration, LookupError) as exc:
        # Network errors, API failures, or no transcripts available
        raise RuntimeError(f"Failed to fetch YouTube transcript for {url}: {exc}") from exc


def extract_notebook(path: str) -> list[str]:
    """Extract content from a Jupyter notebook (.ipynb).

    Parses the JSON structure and extracts markdown and code cells.
    No external dependencies needed — uses stdlib json.

    Returns:
        List with a single string containing formatted notebook content.

    Raises:
        RuntimeError: If file cannot be read or parsed.
    """
    filepath = Path(path)
    if not filepath.is_file():
        raise RuntimeError(f"Notebook file does not exist: {path}")

    try:
        raw = filepath.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Failed to read notebook {path}: {exc}") from exc

    try:
        nb = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON in notebook {path}: {exc}") from exc

    cells = nb.get("cells", [])
    if not cells:
        raise RuntimeError(f"No cells found in notebook: {path}")

    parts: list[str] = []
    for cell in cells:
        cell_type = cell.get("cell_type", "")
        source_lines = cell.get("source", [])
        # source can be a list of strings or a single string
        if isinstance(source_lines, list):
            content = "".join(source_lines)
        else:
            content = str(source_lines)

        content = content.strip()
        if not content:
            continue

        if cell_type == "markdown":
            parts.append(content)
        elif cell_type == "code":
            # Detect language from notebook metadata
            lang = (
                nb.get("metadata", {})
                .get("kernelspec", {})
                .get("language", "python")
            )
            parts.append(f"```{lang}\n{content}\n```")

    if not parts:
        raise RuntimeError(f"No content could be extracted from notebook: {path}")

    return ["\n\n".join(parts)]


def ingest(source: str) -> list[str]:
    """Main entry point: detect source type and fetch content.

    Returns:
        List of raw text contents from the source.

    Raises:
        ValueError: If source type cannot be determined.
        RuntimeError: On fetch/clone/read errors.
    """
    source_type = detect_source_type(source)

    if source_type == SourceType.PDF:
        logger.info("Extracting PDF: %s", source)
        return extract_pdf(source)
    elif source_type == SourceType.YOUTUBE:
        logger.info("Fetching YouTube transcript: %s", source)
        return fetch_youtube_transcript(source)
    elif source_type == SourceType.JUPYTER_NOTEBOOK:
        logger.info("Extracting notebook: %s", source)
        return extract_notebook(source)
    elif source_type == SourceType.URL:
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
