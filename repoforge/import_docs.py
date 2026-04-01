"""
import_docs.py - Fetch external dependency documentation for context enrichment.

Supports three source types:
  - npm packages: fetches README from the npm registry API
  - PyPI packages: fetches description from the PyPI JSON API
  - GitHub repos: shallow-clones and extracts README + docs/

Output is saved to `.repoforge/external-docs/` as flat markdown files.
No external dependencies — uses stdlib urllib + subprocess.
"""

import base64
import json
import logging
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_NPM_REGISTRY = "https://registry.npmjs.org"
_PYPI_API = "https://pypi.org/pypi"
_OUTPUT_DIR = ".repoforge/external-docs"
_USER_AGENT = "repoforge/0.4 (import-docs)"
_TIMEOUT = 30
_MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB per file
_GITHUB_RE = re.compile(r"^https?://github\.com/([\w.\-]+)/([\w.\-]+)")


# ---------------------------------------------------------------------------
# Fetchers
# ---------------------------------------------------------------------------


def fetch_npm_readme(package: str) -> str:
    """Fetch the README for an npm package from the registry.

    Returns:
        Markdown string with the README content.

    Raises:
        RuntimeError: On HTTP or parsing errors.
    """
    url = f"{_NPM_REGISTRY}/{package}"
    data = _fetch_json(url)
    readme = data.get("readme", "")
    if not readme or readme == "ERROR: No README data found!":
        # Fallback: try the description
        desc = data.get("description", "")
        if desc:
            return f"# {package}\n\n{desc}\n"
        raise RuntimeError(f"No README found for npm package: {package}")
    return readme


def fetch_pypi_description(package: str) -> str:
    """Fetch the long description for a PyPI package.

    Returns:
        Markdown string with the package description.

    Raises:
        RuntimeError: On HTTP or parsing errors.
    """
    url = f"{_PYPI_API}/{package}/json"
    data = _fetch_json(url)
    info = data.get("info", {})

    # Prefer the long description (usually the full README)
    description = info.get("description", "")
    if not description:
        summary = info.get("summary", "")
        if summary:
            return f"# {package}\n\n{summary}\n"
        raise RuntimeError(f"No description found for PyPI package: {package}")
    return description


def fetch_github_docs(url: str) -> str:
    """Clone a GitHub repo (shallow) and extract README + docs/ content.

    Returns:
        Concatenated markdown string of README and docs/ files.

    Raises:
        RuntimeError: On clone failures or missing docs.
    """
    match = _GITHUB_RE.match(url)
    if not match:
        raise ValueError(f"Not a valid GitHub URL: {url}")

    clone_url = url.rstrip("/")
    if not clone_url.endswith(".git"):
        clone_url += ".git"

    tmpdir = tempfile.mkdtemp(prefix="repoforge-import-docs-")
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

        parts: list[str] = []

        # Extract README
        tmproot = Path(tmpdir)
        for name in ["README.md", "README.rst", "README.txt", "README"]:
            readme = tmproot / name
            if readme.exists() and readme.stat().st_size <= _MAX_FILE_SIZE:
                parts.append(readme.read_text(encoding="utf-8", errors="replace"))
                break

        # Extract docs/ directory
        docs_dir = tmproot / "docs"
        if docs_dir.is_dir():
            md_files = sorted(
                f
                for f in docs_dir.rglob("*")
                if f.is_file()
                and f.suffix.lower() in {".md", ".markdown", ".mdx", ".rst", ".txt"}
                and f.stat().st_size <= _MAX_FILE_SIZE
            )
            for md_file in md_files[:20]:  # Cap at 20 doc files
                rel = md_file.relative_to(tmproot)
                content = md_file.read_text(encoding="utf-8", errors="replace")
                parts.append(f"\n---\n## {rel}\n\n{content}")

        if not parts:
            raise RuntimeError(f"No documentation found in {url}")

        return "\n".join(parts)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def import_docs(
    working_dir: str = ".",
    npm: list[str] | None = None,
    pypi: list[str] | None = None,
    github: list[str] | None = None,
    quiet: bool = False,
) -> dict:
    """Import external documentation for enriching analysis context.

    Fetches docs from npm, PyPI, and GitHub sources, saving them as
    flat markdown files in `.repoforge/external-docs/`.

    Returns:
        Summary dict with 'imported', 'failed', and 'output_dir' keys.
    """
    npm = npm or []
    pypi = pypi or []
    github = github or []

    root = Path(working_dir).resolve()
    out_dir = root / _OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    imported: list[str] = []
    failed: list[dict] = []

    def _log(msg: str) -> None:
        if not quiet:
            logger.info(msg)

    # npm packages
    for pkg in npm:
        try:
            _log(f"Fetching npm: {pkg}")
            content = fetch_npm_readme(pkg)
            fname = f"npm--{_sanitize_name(pkg)}.md"
            (out_dir / fname).write_text(content, encoding="utf-8")
            imported.append(fname)
        except Exception as exc:
            logger.warning("Failed to fetch npm/%s: %s", pkg, exc)
            failed.append({"source": f"npm/{pkg}", "error": str(exc)})

    # PyPI packages
    for pkg in pypi:
        try:
            _log(f"Fetching PyPI: {pkg}")
            content = fetch_pypi_description(pkg)
            fname = f"pypi--{_sanitize_name(pkg)}.md"
            (out_dir / fname).write_text(content, encoding="utf-8")
            imported.append(fname)
        except Exception as exc:
            logger.warning("Failed to fetch pypi/%s: %s", pkg, exc)
            failed.append({"source": f"pypi/{pkg}", "error": str(exc)})

    # GitHub repos
    for url in github:
        try:
            _log(f"Fetching GitHub: {url}")
            content = fetch_github_docs(url)
            match = _GITHUB_RE.match(url)
            if match:
                owner, repo = match.group(1), match.group(2)
                fname = f"github--{_sanitize_name(owner)}--{_sanitize_name(repo)}.md"
            else:
                fname = f"github--{_sanitize_name(url)}.md"
            (out_dir / fname).write_text(content, encoding="utf-8")
            imported.append(fname)
        except Exception as exc:
            logger.warning("Failed to fetch github/%s: %s", url, exc)
            failed.append({"source": f"github/{url}", "error": str(exc)})

    return {
        "imported": imported,
        "failed": failed,
        "output_dir": str(out_dir),
        "total": len(imported),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fetch_json(url: str) -> dict:
    """Fetch a URL and parse JSON response."""
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            raw = resp.read(_MAX_FILE_SIZE)
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} fetching {url}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Failed to fetch {url}: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON from {url}: {exc}") from exc


def _sanitize_name(name: str) -> str:
    """Sanitize a package/repo name for use as a filename."""
    # Replace slashes, @, and other special chars with dashes
    sanitized = re.sub(r"[/@\\:*?\"<>|]+", "-", name)
    # Collapse multiple dashes
    sanitized = re.sub(r"-+", "-", sanitized)
    # Strip leading/trailing dashes
    return sanitized.strip("-").lower()
