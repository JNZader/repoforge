"""
ripgrep.py - ripgrep integration for fast file discovery and pattern extraction.

Why ripgrep over rglob:
  - Respects .gitignore natively
  - 10-100x faster on large repos
  - Can extract definitions in one pass via --json

All functions gracefully fall back to Python stdlib if rg is not installed.
Install: brew install ripgrep / sudo apt install ripgrep / scoop install ripgrep
"""

import json
import logging
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Availability — NOT cached (avoids stale state between tests/imports)
# ---------------------------------------------------------------------------

def _find_rg() -> Optional[str]:
    """Return path to rg binary, or None."""
    return shutil.which("rg")


def rg_available() -> bool:
    """True if ripgrep is installed and on PATH."""
    return _find_rg() is not None


def rg_version() -> Optional[str]:
    """Return ripgrep version string or None."""
    rg = _find_rg()
    if not rg:
        return None
    try:
        result = subprocess.run(
            [rg, "--version"],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.split("\n")[0].strip()
    except Exception as e:
        logger.debug("Failed to get ripgrep version: %s", e)
        return None


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GLOB_PATTERNS = [
    "*.py", "*.ts", "*.tsx", "*.js", "*.jsx",
    "*.go", "*.rs", "*.java", "*.rb", "*.cs",
    "*.cpp", "*.c", "*.h", "*.php", "*.swift", "*.kt",
]

EXTRA_IGNORE_DIRS = [
    "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", ".nuxt", "coverage",
    ".pytest_cache", ".mypy_cache", "vendor", ".git",
]

SUPPORTED_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".rb",
    ".cs", ".cpp", ".c", ".h", ".php", ".swift", ".kt",
}

EXT_TO_LANG = {
    ".py": "Python",
    ".ts": "TypeScript", ".tsx": "TypeScript",
    ".js": "JavaScript", ".jsx": "JavaScript",
    ".go": "Go",
    ".rs": "Rust",
}

DEFINITION_PATTERNS = {
    "Python": [
        (r"^(?:async\s+)?def\s+([A-Za-z][A-Za-z0-9_]*)\s*\(", "function"),
        (r"^class\s+([A-Za-z][A-Za-z0-9_]*)\s*[\(:]", "class"),
    ],
    "TypeScript": [
        (r"^export\s+(?:default\s+)?(?:async\s+)?function\s+([A-Za-z_$][A-Za-z0-9_$]*)", "function"),
        (r"^export\s+class\s+([A-Za-z_$][A-Za-z0-9_$]*)", "class"),
        (r"^export\s+const\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*[=:]", "const"),
        (r"^export\s+type\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*[=<]", "type"),
        (r"^export\s+interface\s+([A-Za-z_$][A-Za-z0-9_$]*)", "interface"),
    ],
    "JavaScript": [
        (r"^export\s+(?:async\s+)?function\s+([A-Za-z_$][A-Za-z0-9_$]*)", "function"),
        (r"^export\s+class\s+([A-Za-z_$][A-Za-z0-9_$]*)", "class"),
        (r"^export\s+const\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=", "const"),
    ],
    "Go": [
        (r"^func\s+(?:\([^)]+\)\s+)?([A-Z][A-Za-z0-9_]*)\s*\(", "function"),
        (r"^type\s+([A-Z][A-Za-z0-9_]*)\s+(?:struct|interface)", "type"),
    ],
    "Rust": [
        (r"^pub\s+(?:async\s+)?fn\s+([A-Za-z][A-Za-z0-9_]*)", "function"),
        (r"^pub\s+struct\s+([A-Za-z][A-Za-z0-9_]*)", "struct"),
        (r"^pub\s+trait\s+([A-Za-z][A-Za-z0-9_]*)", "trait"),
    ],
}

IMPORT_PATTERNS = {
    "Python": r"^(?:import\s+([\w]+)|from\s+([\w]+)\s+import)",
    "TypeScript": r"""^import\s+.*\s+from\s+['"]([^'"./][^'"]*)['"']?""",
    "JavaScript": r"""^import\s+.*\s+from\s+['"]([^'"./][^'"]*)['"']?""",
    "Go": r"""^\s*"([^"./][^"]*)"$""",
    "Rust": r"^use\s+([\w:]+)",
}


# ---------------------------------------------------------------------------
# Fact extraction — semantic facts like endpoints, ports, env vars, etc.
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class FactItem:
    """A single semantic fact extracted from source code."""
    fact_type: str   # 'endpoint', 'port', 'version', 'db_table', 'cli_command', 'env_var', 'mcp_tool', 'fts_ddl', 'struct_field', 'go_version', 'db_engine', 'dedup_mechanism', 'ui_framework', 'sync_format'
    value: str       # the extracted value (e.g., "GET /health", "7437", "v1.2.3")
    file: str        # source file path (relative)
    line: int        # line number (1-based)
    language: str    # detected language


# Pattern structure: { fact_type: { lang_or_"*": [(regex, label), ...] } }
# "*" matches all languages. Language-specific keys add to (not replace) "*".
FACT_PATTERNS: dict[str, dict[str, list[tuple[str, str]]]] = {
    "endpoint": {
        "Go": [
            (r'\.(Get|Post|Put|Delete|Patch)\s*\(\s*"(/[^"]*)"', "route"),
            (r'\.Handle(?:Func)?\s*\(\s*"(/[^"]*)"', "handle"),
            (r'(?:http\.Handle|mux\.Handle)\s*\(\s*"(/[^"]*)"', "handle"),
            (r'\.Handle(?:Func)?\s*\(\s*"((?:GET|POST|PUT|DELETE|PATCH)\s+/[^"]*)"', "go122_route"),
            (r'e\.(GET|POST|PUT|DELETE|PATCH)\s*\(\s*"(/[^"]*)"', "echo"),
        ],
        "Python": [
            (r'@(?:app|router|api)\.(get|post|put|delete|patch)\s*\(\s*["\'](/[^"\']*)', "decorator"),
            (r'@(?:app|router|api)\.route\s*\(\s*["\'](/[^"\']*)', "decorator"),
            (r'path\s*\(\s*["\']([^"\']+)', "django_path"),
        ],
        "TypeScript": [
            (r'\.(get|post|put|delete|patch)\s*\(\s*["\'](/[^"\']*)', "route"),
            (r'server\.route\s*\(\s*["\'](/[^"\']*)', "route"),
        ],
        "JavaScript": [
            (r'\.(get|post|put|delete|patch)\s*\(\s*["\'](/[^"\']*)', "route"),
        ],
        "Java": [
            (r'@(Get|Post|Put|Delete|Patch)Mapping\s*\(\s*["\']?(/[^"\')\s]*)', "annotation"),
            (r'@RequestMapping\s*\([^)]*value\s*=\s*["\']?(/[^"\')\s]*)', "annotation"),
        ],
        "Rust": [
            (r'#\[(get|post|put|delete|patch)\s*\(\s*"(/[^"]*)"', "macro"),
            (r'\.route\s*\(\s*"(/[^"]*)"', "route"),
        ],
    },
    "port": {
        "*": [
            (r'(?:ListenAndServe|listen|EXPOSE)\s*[(]?\s*["\']?[:]?(\d{2,5})', "port"),
            (r'(?:port|PORT)\s*[:=]{1,2}\s*["\']?(\d{2,5})', "port_assign"),
            (r'(?:defaultPort|DEFAULT_PORT)\s*[:=]{1,2}\s*["\']?(\d{2,5})', "port_default"),
        ],
    },
    "version": {
        "*": [
            (r'(?:version|VERSION|Version)\s*[:=]\s*["\']([^"\']+)', "version"),
        ],
    },
    "db_table": {
        "*": [
            (r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`"\']?(\w+)', "sql"),
        ],
        "Python": [
            (r'__tablename__\s*=\s*["\'](\w+)', "orm"),
            (r'class\s+\w+.*\bModel\b', "django_model"),
        ],
        "TypeScript": [
            (r'@Entity\s*\(\s*["\'](\w+)', "typeorm"),
            (r'model\s+(\w+)\s*\{', "prisma"),
        ],
    },
    "cli_command": {
        "Go": [
            (r'Use:\s*"(\w+)"', "cobra"),
            (r'flag\.(?:String|Int|Bool)\w*\s*\(\s*"([^"]+)"', "flag"),
        ],
        "Python": [
            (r'@(?:click\.command|app\.command)\s*\(\s*["\']?(\w*)', "click"),
            (r'add_parser\s*\(\s*["\'](\w+)', "argparse"),
            (r'add_argument\s*\(\s*["\']--([^"\']+)', "argparse_flag"),
        ],
        "TypeScript": [
            (r'\.command\s*\(\s*["\'](\w+)', "commander"),
        ],
    },
    "env_var": {
        "*": [
            (r'os\.(?:Getenv|LookupEnv)\s*\(\s*["\']([A-Z][A-Z0-9_]+)', "go_env"),
            (r'os\.environ(?:\.get)?\s*[\[(]\s*["\']([A-Z][A-Z0-9_]+)', "python_env"),
            (r'process\.env\.([A-Z][A-Z0-9_]+)', "node_env"),
            (r'os\.getenv\s*\(\s*["\']([A-Z][A-Z0-9_]+)', "python_getenv"),
        ],
    },
    "mcp_tool": {
        "Go": [
            (r'mcp\.NewTool\s*\(\s*"([^"]+)"', "mcp_new_tool"),
            (r'server\.AddTool\s*\(\s*"([^"]+)"', "mcp_add_tool"),
            (r'tool\.NewTool\s*\(', "mcp_tool_new"),
        ],
        "Python": [
            (r'@mcp\.tool', "mcp_decorator"),
            (r'server\.add_tool', "mcp_add_tool"),
            (r'Tool\s*\(\s*name\s*=\s*"([^"]+)"', "mcp_tool_init"),
        ],
        "TypeScript": [
            (r'server\.tool\s*\(\s*"([^"]+)"', "mcp_server_tool"),
            (r'new\s+McpTool\s*\(', "mcp_tool_new"),
        ],
    },
    "fts_ddl": {
        "*": [
            (r'(?i)CREATE\s+VIRTUAL\s+TABLE\s+(\w+\s+USING\s+fts\d?)', "fts_virtual_table"),
        ],
    },
    "struct_field": {
        "Go": [
            (r'^\s+[A-Z]\w+\s+\S+', "exported_field"),
        ],
    },
    "go_version": {
        "*": [
            (r'^go\s+1\.\d+', "go_mod_version"),
        ],
    },
    "dedup_mechanism": {
        "*": [
            (r'normalized_hash', "normalized_hash"),
            (r'content_hash', "content_hash"),
            (r'dedup(?:licate)?', "dedup"),
        ],
        "Go": [
            (r'NormalizedHash', "go_normalized_hash"),
            (r'ContentHash', "go_content_hash"),
        ],
        "Python": [
            (r'unique_together', "unique_together"),
            (r'unique\s*=\s*True', "unique_field"),
        ],
    },
    "ui_framework": {
        "Go": [
            (r'bubbletea', "bubbletea"),
            (r'charmbracelet', "charmbracelet"),
            (r'tview', "tview"),
            (r'termui', "termui"),
        ],
        "Python": [
            (r'tkinter', "tkinter"),
            (r'PyQt', "pyqt"),
            (r'streamlit', "streamlit"),
            (r'gradio', "gradio"),
            (r'\brich\b', "rich"),
        ],
        "TypeScript": [
            (r'\bink\b', "ink"),
            (r'blessed', "blessed"),
        ],
    },
    "sync_format": {
        "*": [
            (r'\.jsonl', "jsonl"),
            (r'\.ndjson', "ndjson"),
            (r'jsonlines', "jsonlines"),
            (r'json\s+lines', "json_lines"),
        ],
        "Go": [
            (r'jsonl\.gz', "jsonl_gz"),
            (r'gzip.*json', "gzip_json"),
            (r'json.*gzip', "json_gzip"),
        ],
    },
    "db_engine": {
        "Go": [
            (r'"(modernc\.org/sqlite)"', "modernc_sqlite"),
            (r'"(github\.com/mattn/go-sqlite3)"', "go_sqlite3"),
            (r'"(github\.com/lib/pq)"', "lib_pq"),
            (r'"(github\.com/go-sql-driver/mysql)"', "go_mysql"),
            (r'"(github\.com/jackc/pgx[^"]*)"', "pgx"),
        ],
        "Python": [
            (r'^import\s+(sqlite3)', "python_sqlite3"),
            (r'^import\s+(psycopg2)', "python_psycopg2"),
            (r'^from\s+(psycopg2)', "python_psycopg2"),
            (r'^from\s+(sqlalchemy)', "python_sqlalchemy"),
            (r'^import\s+(pymongo)', "python_pymongo"),
            (r'^from\s+(pymongo)', "python_pymongo"),
        ],
        "TypeScript": [
            (r"""require\s*\(\s*['"](pg)['"]\)""", "ts_pg"),
            (r"""require\s*\(\s*['"](mysql2)['"]\)""", "ts_mysql2"),
            (r"""require\s*\(\s*['"](better-sqlite3)['"]\)""", "ts_better_sqlite3"),
            (r"""from\s+['"]((?:@?prisma)[^'"]*)['"']""", "ts_prisma"),
            (r"""from\s+['"](drizzle-orm)['"']""", "ts_drizzle"),
        ],
        "JavaScript": [
            (r"""require\s*\(\s*['"](pg)['"]\)""", "js_pg"),
            (r"""require\s*\(\s*['"](mysql2)['"]\)""", "js_mysql2"),
            (r"""require\s*\(\s*['"](better-sqlite3)['"]\)""", "js_better_sqlite3"),
            (r"""from\s+['"]((?:@?prisma)[^'"]*)['"']""", "js_prisma"),
            (r"""from\s+['"](drizzle-orm)['"']""", "js_drizzle"),
        ],
    },
}


# Max files per rg invocation to avoid "argument list too long"
_MAX_FILES_PER_RG_CALL = 200


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def list_files(
    directory: Path,
    max_size_kb: int = 100,
    extra_ignore: Optional[set[str]] = None,
) -> list[Path]:
    """
    Return all source files under `directory`, respecting .gitignore.
    Uses ripgrep if available, falls back to Python rglob.

    Args:
        extra_ignore: Additional patterns to exclude (from .repoignore).
    """
    rg = _find_rg()
    if rg:
        result = _rg_list_files(rg, directory, max_size_kb, extra_ignore)
        if result is not None:
            return result
    return _fallback_list_files(directory, max_size_kb, extra_ignore)


def _rg_list_files(
    rg: str,
    directory: Path,
    max_size_kb: int,
    extra_ignore: Optional[set[str]] = None,
) -> Optional[list[Path]]:
    """Use `rg --files` for fast, .gitignore-aware file discovery."""
    cmd = [
        rg, "--files",
        "--follow",
        f"--max-filesize={max_size_kb}K",
    ]
    for glob in GLOB_PATTERNS:
        cmd.extend(["--glob", glob])
    for d in EXTRA_IGNORE_DIRS:
        cmd.extend(["--glob", f"!{d}"])
        cmd.extend(["--glob", f"!{d}/**"])
        cmd.extend(["--glob", f"!**/{d}/**"])
    for pattern in extra_ignore or ():
        cmd.extend(["--glob", f"!{pattern}"])

    cmd.append(str(directory))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode not in (0, 1):
            return None

        paths = []
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            p = Path(line)
            if not p.is_absolute():
                p = directory / p
            if p.exists() and p.is_file():
                paths.append(p.resolve())
        return sorted(paths)

    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def _fallback_list_files(
    directory: Path,
    max_size_kb: int,
    extra_ignore: Optional[set[str]] = None,
) -> list[Path]:
    """Pure Python fallback using rglob."""
    max_bytes = max_size_kb * 1024
    ignore_dirs = set(EXTRA_IGNORE_DIRS) | (extra_ignore or set())
    result = []
    try:
        for entry in sorted(directory.rglob("*")):
            try:
                rel_parts = entry.relative_to(directory).parts
            except ValueError:
                continue
            if any(part in ignore_dirs for part in rel_parts):
                continue
            if not entry.is_file():
                continue
            if entry.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            try:
                if entry.stat().st_size <= max_bytes:
                    result.append(entry.resolve())
            except OSError:
                continue
    except PermissionError:
        pass
    return result


# ---------------------------------------------------------------------------
# Definition extraction
# ---------------------------------------------------------------------------

def extract_definitions(files: list[Path], root: Path) -> dict[str, list[str]]:
    """
    Extract public function/class/const names from files.
    Returns: { "relative/path.py": ["func1", "Class2", ...] }
    """
    if not files:
        return {}
    rg = _find_rg()
    if rg:
        result = _rg_extract_definitions(rg, files, root)
        if result is not None:
            return result
    return _fallback_extract_definitions(files, root)


def _rg_extract_definitions(rg: str, files: list[Path], root: Path) -> Optional[dict[str, list[str]]]:
    """Run rg --json per language group to extract definitions."""
    by_lang: dict[str, list[Path]] = {}
    for f in files:
        lang = EXT_TO_LANG.get(f.suffix.lower())
        if lang and lang in DEFINITION_PATTERNS:
            by_lang.setdefault(lang, []).append(f)

    if not by_lang:
        return {}

    results: dict[str, list[str]] = {}

    for lang, lang_files in by_lang.items():
        patterns = DEFINITION_PATTERNS[lang]
        # Build combined OR pattern
        combined = "|".join(f"(?:{p})" for p, _ in patterns)

        # Process in batches to avoid "argument list too long"
        for batch in _batched(lang_files, _MAX_FILES_PER_RG_CALL):
            cmd = [rg, "--json", "-e", combined] + [str(f.resolve()) for f in batch]
            try:
                proc = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=60,
                )
            except (subprocess.TimeoutExpired, OSError):
                _fallback_lang_defs(batch, root, lang, results)
                continue

            _parse_rg_definitions(proc.stdout, patterns, lang, root, results)

    return results


def _parse_rg_definitions(stdout: str, patterns: list, lang: str, root: Path, results: dict):
    """Parse rg --json output and populate results dict."""
    for line in stdout.strip().split("\n"):
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("type") != "match":
            continue

        file_path_raw = obj.get("data", {}).get("path", {}).get("text", "")
        match_text = obj.get("data", {}).get("lines", {}).get("text", "")
        if not file_path_raw or not match_text:
            continue

        rel = _to_relative(Path(file_path_raw), root)

        for pattern, _ in patterns:
            m = re.search(pattern, match_text.strip())
            if m:
                name = m.group(1)
                if lang == "Python" and name.startswith("_"):
                    break
                results.setdefault(rel, [])
                if name not in results[rel]:
                    results[rel].append(name)
                break


def _fallback_extract_definitions(files: list[Path], root: Path) -> dict[str, list[str]]:
    results: dict[str, list[str]] = {}
    for f in files:
        lang = EXT_TO_LANG.get(f.suffix.lower())
        if lang:
            _fallback_lang_defs([f], root, lang, results)
    return results


def _fallback_lang_defs(files: list[Path], root: Path, lang: str, results: dict):
    patterns = DEFINITION_PATTERNS.get(lang, [])
    if not patterns:
        return
    for f in files:
        try:
            content = f.read_text(errors="replace")
        except OSError:
            continue
        rel = _to_relative(f, root)
        for line in content.split("\n"):
            for pattern, _ in patterns:
                m = re.search(pattern, line)
                if m:
                    name = m.group(1)
                    if lang == "Python" and name.startswith("_"):
                        break
                    results.setdefault(rel, [])
                    if name not in results[rel]:
                        results[rel].append(name)
                    break


# ---------------------------------------------------------------------------
# Import extraction
# ---------------------------------------------------------------------------

def extract_imports(files: list[Path], root: Path) -> dict[str, list[str]]:
    """
    Extract external import/dependency names per file.
    Returns: { "relative/path.py": ["fastapi", "pydantic", ...] }
    """
    if not files:
        return {}
    rg = _find_rg()
    if rg:
        result = _rg_extract_imports(rg, files, root)
        if result is not None:
            return result
    return _fallback_extract_imports(files, root)


def _rg_extract_imports(rg: str, files: list[Path], root: Path) -> Optional[dict[str, list[str]]]:
    by_lang: dict[str, list[Path]] = {}
    for f in files:
        lang = EXT_TO_LANG.get(f.suffix.lower())
        if lang and lang in IMPORT_PATTERNS:
            by_lang.setdefault(lang, []).append(f)

    if not by_lang:
        return {}

    results: dict[str, list[str]] = {}

    for lang, lang_files in by_lang.items():
        pattern = IMPORT_PATTERNS[lang]
        for batch in _batched(lang_files, _MAX_FILES_PER_RG_CALL):
            cmd = [rg, "--json", "-e", pattern] + [str(f.resolve()) for f in batch]
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            except (subprocess.TimeoutExpired, OSError):
                continue

            for line in proc.stdout.strip().split("\n"):
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("type") != "match":
                    continue

                file_path_raw = obj.get("data", {}).get("path", {}).get("text", "")
                match_text = obj.get("data", {}).get("lines", {}).get("text", "").strip()
                if not file_path_raw or not match_text:
                    continue

                m = re.search(pattern, match_text)
                if m:
                    pkg_raw = next((g for g in m.groups() if g), None)
                    if pkg_raw:
                        pkg = pkg_raw.split(".")[0].split(":")[0]
                        if pkg and not pkg.startswith(".") and not pkg.startswith("_"):
                            rel = _to_relative(Path(file_path_raw), root)
                            results.setdefault(rel, [])
                            if pkg not in results[rel]:
                                results[rel].append(pkg)

    return results


def _fallback_extract_imports(files: list[Path], root: Path) -> dict[str, list[str]]:
    results: dict[str, list[str]] = {}
    for f in files:
        lang = EXT_TO_LANG.get(f.suffix.lower())
        if not lang or lang not in IMPORT_PATTERNS:
            continue
        try:
            content = f.read_text(errors="replace")
        except OSError:
            continue
        rel = _to_relative(f, root)
        pattern = IMPORT_PATTERNS[lang]
        for line in content.split("\n"):
            m = re.search(pattern, line)
            if m:
                pkg_raw = next((g for g in m.groups() if g), None)
                if pkg_raw:
                    pkg = pkg_raw.split(".")[0]
                    if pkg and not pkg.startswith(".") and not pkg.startswith("_"):
                        results.setdefault(rel, [])
                        if pkg not in results[rel]:
                            results[rel].append(pkg)
    return results


# ---------------------------------------------------------------------------
# Summary hint extraction
# ---------------------------------------------------------------------------

def extract_summary_hints(files: list[Path], root: Path) -> dict[str, str]:
    """
    Extract the first meaningful comment or docstring from each file.
    Returns: { "relative/path.py": "summary text" }
    """
    if not files:
        return {}
    rg = _find_rg()
    if rg:
        result = _rg_summary_hints(rg, files, root)
        if result is not None:
            return result
    return _fallback_summary_hints(files, root)


def _rg_summary_hints(rg: str, files: list[Path], root: Path) -> Optional[dict[str, str]]:
    """Grab first comment/docstring from each file using rg."""
    pattern = (
        r'^(?:'
        r'"{3}\s*([A-Za-z][^"]{5,200})'
        r"|'{3}\s*([A-Za-z][^']{5,200})"
        r'|#\s{0,3}([A-Za-z][^#\n]{8,180})'
        r'|//\s{0,3}([A-Za-z][^/\n]{8,180})'
        r')'
    )

    results: dict[str, str] = {}

    for batch in _batched(files, _MAX_FILES_PER_RG_CALL):
        cmd = [rg, "--json", "--max-count=1", "-e", pattern] + [str(f.resolve()) for f in batch]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except (subprocess.TimeoutExpired, OSError):
            return None

        for line in proc.stdout.strip().split("\n"):
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("type") != "match":
                continue

            file_path_raw = obj.get("data", {}).get("path", {}).get("text", "")
            match_text = obj.get("data", {}).get("lines", {}).get("text", "").strip()
            if not file_path_raw or not match_text:
                continue

            rel = _to_relative(Path(file_path_raw), root)
            # Don't overwrite if already found (--max-count=1 is per-file but we batch)
            if rel in results:
                continue

            m = re.search(pattern, match_text)
            if m:
                hint_raw = next((g for g in m.groups() if g), match_text)
            else:
                hint_raw = match_text

            hint = re.sub(r'^[#/"\'`\s*]+', "", hint_raw).strip()
            if len(hint) > 8:
                results[rel] = hint[:200]

    return results


def _fallback_summary_hints(files: list[Path], root: Path) -> dict[str, str]:
    results: dict[str, str] = {}
    for f in files:
        try:
            content = f.read_text(errors="replace")
            hint = _extract_first_comment(content)
            if hint:
                results[_to_relative(f, root)] = hint
        except OSError:
            continue
    return results


def _extract_first_comment(content: str) -> str:
    """Extract first meaningful comment or docstring line from file content."""
    for line in content.split("\n")[:25]:
        stripped = line.strip()
        if stripped.startswith('"""') or stripped.startswith("'''"):
            inner = stripped.lstrip('"\'').strip()
            if len(inner) > 8:
                return inner[:200]
        if stripped.startswith("#"):
            inner = stripped.lstrip("# ").strip()
            if len(inner) > 8 and not inner.startswith("!"):
                return inner[:200]
        if stripped.startswith("//"):
            inner = stripped.lstrip("/ ").strip()
            if len(inner) > 8:
                return inner[:200]
        if stripped.startswith("/*"):
            inner = stripped.lstrip("/* ").strip()
            if len(inner) > 8:
                return inner[:200]
    return ""


# ---------------------------------------------------------------------------
# Fact extraction
# ---------------------------------------------------------------------------

def extract_facts(files: list[Path], root: Path) -> list[FactItem]:
    """
    Extract semantic facts (endpoints, ports, env vars, etc.) from source files.

    Uses ripgrep when available, falls back to Python regex.
    Returns a deduplicated, sorted list of FactItem.
    """
    if not files:
        return []
    rg = _find_rg()
    if rg:
        result = _rg_extract_facts(rg, files, root)
        if result is not None:
            return result
    return _fallback_extract_facts(files, root)


def _get_fact_patterns_for_lang(lang: str) -> list[tuple[str, str, str]]:
    """Get all (regex, label, fact_type) tuples applicable to a language.

    Merges "*" (universal) patterns with language-specific patterns.
    """
    combined: list[tuple[str, str, str]] = []
    for fact_type, lang_map in FACT_PATTERNS.items():
        # Universal patterns
        for pattern, label in lang_map.get("*", []):
            combined.append((pattern, label, fact_type))
        # Language-specific patterns
        for pattern, label in lang_map.get(lang, []):
            combined.append((pattern, label, fact_type))
    return combined


def _rg_extract_facts(
    rg: str, files: list[Path], root: Path,
) -> Optional[list[FactItem]]:
    """Use rg --json to extract facts from files, batched by language."""
    by_lang: dict[str, list[Path]] = {}
    for f in files:
        lang = EXT_TO_LANG.get(f.suffix.lower())
        if lang:
            by_lang.setdefault(lang, []).append(f)

    if not by_lang:
        return []

    facts: list[FactItem] = []

    for lang, lang_files in by_lang.items():
        patterns = _get_fact_patterns_for_lang(lang)
        if not patterns:
            continue

        # Build combined OR pattern for rg
        combined = "|".join(f"(?:{p})" for p, _, _ in patterns)

        for batch in _batched(lang_files, _MAX_FILES_PER_RG_CALL):
            cmd = [rg, "--json", "--line-number", "-e", combined] + [
                str(f.resolve()) for f in batch
            ]
            try:
                proc = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=60,
                )
            except (subprocess.TimeoutExpired, OSError):
                # Fallback for this batch
                _fallback_facts_batch(batch, root, lang, facts)
                continue

            _parse_rg_facts(proc.stdout, patterns, lang, root, facts)

    return _deduplicate_facts(facts)


def _extract_endpoint_value(m: re.Match[str], fallback: str) -> str:
    """Build fact value from regex match groups.

    For endpoint patterns with two capture groups the first group is the HTTP
    method (e.g. ``Get``, ``post``, ``GET``) and the second is the URL path.
    The method is upper-cased and prepended to the path so the final value
    looks like ``"GET /health"``.

    Single-group matches (no method available) return group(1) as-is.
    """
    if m.lastindex and m.lastindex >= 2:
        method = m.group(1).upper()
        path = m.group(2).strip()
        return f"{method} {path}"
    if m.lastindex and m.lastindex >= 1:
        return m.group(1).strip()
    return fallback.strip()


def _parse_rg_facts(
    stdout: str,
    patterns: list[tuple[str, str, str]],
    lang: str,
    root: Path,
    facts: list[FactItem],
) -> None:
    """Parse rg --json output and append FactItems to the facts list."""
    for line in stdout.strip().split("\n"):
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("type") != "match":
            continue

        file_path_raw = obj.get("data", {}).get("path", {}).get("text", "")
        match_text = obj.get("data", {}).get("lines", {}).get("text", "")
        line_number = obj.get("data", {}).get("line_number", 0)
        if not file_path_raw or not match_text:
            continue

        rel = _to_relative(Path(file_path_raw), root)

        for pattern, label, fact_type in patterns:
            m = re.search(pattern, match_text)
            if m:
                value = _extract_endpoint_value(m, match_text)
                facts.append(FactItem(
                    fact_type=fact_type,
                    value=value,
                    file=rel,
                    line=line_number,
                    language=lang,
                ))
                break  # first matching pattern wins


def _fallback_extract_facts(files: list[Path], root: Path) -> list[FactItem]:
    """Pure Python fallback for fact extraction."""
    facts: list[FactItem] = []
    for f in files:
        lang = EXT_TO_LANG.get(f.suffix.lower())
        if not lang:
            continue
        _fallback_facts_batch([f], root, lang, facts)
    return _deduplicate_facts(facts)


def _fallback_facts_batch(
    files: list[Path], root: Path, lang: str, facts: list[FactItem],
) -> None:
    """Extract facts from a batch of files using Python regex."""
    patterns = _get_fact_patterns_for_lang(lang)
    if not patterns:
        return

    for f in files:
        try:
            content = f.read_text(errors="replace")
        except OSError:
            continue
        rel = _to_relative(f, root)
        for line_num, line in enumerate(content.split("\n"), start=1):
            for pattern, label, fact_type in patterns:
                m = re.search(pattern, line)
                if m:
                    value = _extract_endpoint_value(m, line)
                    facts.append(FactItem(
                        fact_type=fact_type,
                        value=value,
                        file=rel,
                        line=line_num,
                        language=lang,
                    ))
                    break  # first matching pattern wins per line


def _deduplicate_facts(facts: list[FactItem]) -> list[FactItem]:
    """Deduplicate by (fact_type, value) keeping first occurrence, then sort."""
    seen: set[tuple[str, str]] = set()
    unique: list[FactItem] = []
    for f in facts:
        key = (f.fact_type, f.value)
        if key not in seen:
            seen.add(key)
            unique.append(f)
    return sorted(unique, key=lambda f: (f.fact_type, f.value))


# ---------------------------------------------------------------------------
# Repo stats
# ---------------------------------------------------------------------------

def repo_stats(directory: Path) -> dict:
    """Quick stats about a repo directory."""
    files = list_files(directory, max_size_kb=500)
    by_ext: dict[str, int] = {}
    for f in files:
        ext = f.suffix.lower()
        by_ext[ext] = by_ext.get(ext, 0) + 1

    return {
        "total_files": len(files),
        "by_extension": by_ext,
        "rg_available": rg_available(),
        "rg_version": rg_version(),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_relative(path: Path, root: Path) -> str:
    """Return relative path string, resolving symlinks for reliable comparison."""
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return path.name


def _batched(lst: list, size: int):
    """Yield successive chunks of `size` from list."""
    for i in range(0, len(lst), size):
        yield lst[i:i + size]
