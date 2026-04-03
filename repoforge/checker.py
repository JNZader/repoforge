"""
checker.py - Validate code references in generated documentation.

Scans markdown files for code references (file paths, symbols) and validates
them against the actual codebase. No LLM needed — purely deterministic.

Reference types detected:
  1. File paths in backticks: `src/auth.ts`, `repoforge/cli.py`
  2. Symbol references: `scan_repo`, `CheckResult`

Works standalone: regex-based extraction, filesystem validation.

Inspired by:
  - cased/kit (doc reference validation)
  - 1st1/lat.md (code link checking)
  - repoforge security.py (scanner pattern)

Usage:
    from repoforge.checker import check_docs, ReferenceChecker

    result = check_docs("/path/to/repo", docs_dir="docs")
    # result.broken_count > 0 means stale references exist
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

class RefStatus(Enum):
    VALID = "valid"
    BROKEN = "broken"
    UNRESOLVABLE = "unresolvable"  # Can't determine (ambiguous symbol)


class RefType(Enum):
    FILE = "file"
    SYMBOL = "symbol"


@dataclass
class CodeRef:
    """A single code reference found in documentation."""

    ref_text: str
    ref_type: RefType
    status: RefStatus
    source_file: str
    line_number: int
    resolved_path: str = ""  # Filled when status is VALID

    @property
    def is_broken(self) -> bool:
        return self.status == RefStatus.BROKEN


@dataclass
class CheckResult:
    """Aggregated results from checking one or more documentation files."""

    files_scanned: int
    refs: list[CodeRef] = field(default_factory=list)

    @property
    def valid_count(self) -> int:
        return sum(1 for r in self.refs if r.status == RefStatus.VALID)

    @property
    def broken_count(self) -> int:
        return sum(1 for r in self.refs if r.status == RefStatus.BROKEN)

    @property
    def unresolvable_count(self) -> int:
        return sum(1 for r in self.refs if r.status == RefStatus.UNRESOLVABLE)

    @property
    def total_count(self) -> int:
        return len(self.refs)


# ---------------------------------------------------------------------------
# Reference extraction patterns
# ---------------------------------------------------------------------------

# Matches backtick content that looks like a file path (has directory separator and/or extension)
_FILE_REF_RE = re.compile(
    r"(?<!`)`(?!`)"                   # opening backtick (not fenced)
    r"([\w][\w./\-]*\.[\w]{1,10})"    # path with extension
    r"`(?!`)",                         # closing backtick (not fenced)
)

# Matches backtick content that looks like a qualified symbol (Module.method, file::symbol)
_QUALIFIED_SYMBOL_RE = re.compile(
    r"(?<!`)`(?!`)"
    r"([\w]+(?:::|\.)[\w]+)"          # e.g., auth::validate or Auth.validate
    r"`(?!`)",
)

# Matches backtick content that looks like a standalone identifier (PascalCase or snake_case function)
_SYMBOL_RE = re.compile(
    r"(?<!`)`(?!`)"
    r"([A-Z][\w]{2,}|[a-z][\w]*_[\w]+)"  # PascalCase or snake_case with underscore
    r"`(?!`)",
)

# Fenced code block boundaries (to skip content inside them)
_FENCE_RE = re.compile(r"^(`{3,}|~{3,})", re.MULTILINE)

# Common false positives to skip
_SKIP_PATTERNS = {
    "true", "false", "null", "none", "nil", "undefined",
    "int", "str", "bool", "float", "string", "number",
    "dict", "list", "tuple", "set", "map", "array",
    "http", "https", "localhost", "stdout", "stderr", "stdin",
    "pip", "npm", "yarn", "pnpm", "cargo", "brew", "apt",
    "git", "docker", "kubectl", "make", "bash", "zsh", "sh",
    "todo", "fixme", "note", "hack", "xxx",
    "utf-8", "utf-16", "ascii", "json", "yaml", "toml", "xml", "html", "css",
}

# Extensions that indicate a real file reference
_CODE_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java",
    ".rb", ".php", ".c", ".cpp", ".h", ".hpp", ".cs", ".swift",
    ".kt", ".scala", ".lua", ".sh", ".bash", ".zsh",
    ".yaml", ".yml", ".toml", ".json", ".xml", ".html", ".css",
    ".scss", ".less", ".sql", ".md", ".txt", ".cfg", ".ini", ".env",
    ".dockerfile", ".makefile",
}


# ---------------------------------------------------------------------------
# ReferenceChecker
# ---------------------------------------------------------------------------


class ReferenceChecker:
    """Scans markdown docs for code references and validates them against a codebase."""

    def __init__(self, workspace: str | Path) -> None:
        self.workspace = Path(workspace).resolve()
        self._file_index: set[str] | None = None
        self._symbol_cache: dict[str, str] = {}

    # -- File index -----------------------------------------------------------

    def _build_file_index(self) -> set[str]:
        """Build an index of all files in the workspace (relative paths)."""
        if self._file_index is not None:
            return self._file_index

        self._file_index = set()

        # Try ripgrep first for speed + .gitignore respect
        try:
            result = subprocess.run(
                ["rg", "--files", str(self.workspace)],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().splitlines():
                    line = line.strip()
                    if line:
                        try:
                            rel = str(Path(line).relative_to(self.workspace))
                            self._file_index.add(rel)
                        except ValueError:
                            self._file_index.add(line)
                return self._file_index
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Fallback: pathlib walk
        skip_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv",
                     ".tox", "dist", "build", ".eggs", ".mypy_cache"}
        for path in self.workspace.rglob("*"):
            if path.is_file():
                parts = path.relative_to(self.workspace).parts
                if not any(p in skip_dirs for p in parts):
                    self._file_index.add(str(path.relative_to(self.workspace)))

        return self._file_index

    # -- Extraction -----------------------------------------------------------

    def _outside_fenced_blocks(self, content: str) -> list[tuple[str, int]]:
        """Return (line_text, line_number) pairs for lines NOT inside fenced code blocks."""
        lines = content.splitlines()
        result: list[tuple[str, int]] = []
        in_fence = False

        for i, line in enumerate(lines, start=1):
            if _FENCE_RE.match(line.strip()):
                in_fence = not in_fence
                continue
            if not in_fence:
                result.append((line, i))

        return result

    def _extract_refs_from_line(
        self, line: str, line_number: int, source_file: str
    ) -> list[CodeRef]:
        """Extract code references from a single line of markdown."""
        refs: list[CodeRef] = []
        seen: set[str] = set()

        # 1. File path references
        for m in _FILE_REF_RE.finditer(line):
            text = m.group(1)
            if text.lower() in _SKIP_PATTERNS:
                continue
            ext = Path(text).suffix.lower()
            if ext not in _CODE_EXTENSIONS:
                continue
            if text not in seen:
                seen.add(text)
                refs.append(CodeRef(
                    ref_text=text,
                    ref_type=RefType.FILE,
                    status=RefStatus.BROKEN,  # Will be validated later
                    source_file=source_file,
                    line_number=line_number,
                ))

        # 2. Qualified symbol references (file::symbol or Module.method)
        for m in _QUALIFIED_SYMBOL_RE.finditer(line):
            text = m.group(1)
            if text not in seen:
                seen.add(text)
                refs.append(CodeRef(
                    ref_text=text,
                    ref_type=RefType.SYMBOL,
                    status=RefStatus.UNRESOLVABLE,
                    source_file=source_file,
                    line_number=line_number,
                ))

        return refs

    # -- Validation -----------------------------------------------------------

    def _validate_file_ref(self, ref: CodeRef) -> None:
        """Validate a file reference against the file index."""
        file_index = self._build_file_index()
        text = ref.ref_text

        # Direct match
        if text in file_index:
            ref.status = RefStatus.VALID
            ref.resolved_path = text
            return

        # Try with/without leading separators
        normalized = text.lstrip("./")
        if normalized in file_index:
            ref.status = RefStatus.VALID
            ref.resolved_path = normalized
            return

        # Try suffix matching (e.g., `cli.py` matches `repoforge/cli.py`)
        matches = [f for f in file_index if f.endswith("/" + normalized) or f == normalized]
        if len(matches) == 1:
            ref.status = RefStatus.VALID
            ref.resolved_path = matches[0]
            return
        elif len(matches) > 1:
            # Ambiguous but exists — mark as valid (first match)
            ref.status = RefStatus.VALID
            ref.resolved_path = matches[0]
            return

        # Not found
        ref.status = RefStatus.BROKEN

    def _validate_symbol_ref(self, ref: CodeRef) -> None:
        """Validate a symbol reference by searching the codebase."""
        # Split qualified symbols
        if "::" in ref.ref_text:
            parts = ref.ref_text.split("::")
            symbol = parts[-1]
        elif "." in ref.ref_text:
            parts = ref.ref_text.split(".")
            symbol = parts[-1]
        else:
            symbol = ref.ref_text

        # Check cache first
        if symbol in self._symbol_cache:
            ref.status = RefStatus.VALID
            ref.resolved_path = self._symbol_cache[symbol]
            return

        # Try rg for fast symbol search
        try:
            result = subprocess.run(
                ["rg", "-l", "--max-count=1",
                 f"(def |class |function |const |let |var |type |interface ){symbol}\\b",
                 str(self.workspace),
                 "--glob", "!*.md",
                 "--glob", "!node_modules/**",
                 "--glob", "!.venv/**",
                 "--glob", "!dist/**"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                first_match = result.stdout.strip().splitlines()[0]
                try:
                    resolved = str(Path(first_match).relative_to(self.workspace))
                except ValueError:
                    resolved = first_match
                self._symbol_cache[symbol] = resolved
                ref.status = RefStatus.VALID
                ref.resolved_path = resolved
                return
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Fallback: simple text search in Python files
        for f in self._build_file_index():
            if not f.endswith((".py", ".ts", ".js", ".go", ".rs", ".java")):
                continue
            try:
                full_path = self.workspace / f
                text = full_path.read_text(encoding="utf-8", errors="ignore")
                if re.search(rf"\b(def|class|function|const|let|var|type|interface)\s+{re.escape(symbol)}\b", text):
                    self._symbol_cache[symbol] = f
                    ref.status = RefStatus.VALID
                    ref.resolved_path = f
                    return
            except (OSError, UnicodeDecodeError):
                continue

        ref.status = RefStatus.UNRESOLVABLE

    # -- Public API -----------------------------------------------------------

    def scan_content(self, content: str, file_path: str = "<string>") -> list[CodeRef]:
        """Scan markdown content for code references and validate them.

        Args:
            content: Markdown text to scan.
            file_path: Source file path for reporting.

        Returns:
            List of CodeRef with validated statuses.
        """
        refs: list[CodeRef] = []
        lines = self._outside_fenced_blocks(content)

        for line_text, line_number in lines:
            refs.extend(self._extract_refs_from_line(line_text, line_number, file_path))

        # Validate each ref
        for ref in refs:
            if ref.ref_type == RefType.FILE:
                self._validate_file_ref(ref)
            elif ref.ref_type == RefType.SYMBOL:
                self._validate_symbol_ref(ref)

        return refs

    def scan_file(self, path: str | Path) -> list[CodeRef]:
        """Scan a single markdown file for code references."""
        path = Path(path)
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            logger.warning("Cannot read %s: %s", path, e)
            return []
        return self.scan_content(content, str(path))

    def scan_directory(
        self,
        docs_dir: str | Path,
        glob_pattern: str = "**/*.md",
    ) -> CheckResult:
        """Scan all markdown files in a directory for code references.

        Args:
            docs_dir: Path to the documentation directory.
            glob_pattern: Glob pattern for files to scan.

        Returns:
            CheckResult with all found references and their validation status.
        """
        docs_path = Path(docs_dir)
        if not docs_path.exists():
            logger.error("Documentation directory not found: %s", docs_path)
            return CheckResult(files_scanned=0)

        md_files = sorted(docs_path.glob(glob_pattern))
        all_refs: list[CodeRef] = []

        for md_file in md_files:
            refs = self.scan_file(md_file)
            all_refs.extend(refs)

        return CheckResult(files_scanned=len(md_files), refs=all_refs)

    # -- Reporting ------------------------------------------------------------

    @staticmethod
    def report(result: CheckResult, fmt: str = "table") -> str:
        """Format a CheckResult into a human-readable report.

        Args:
            result: The check result to format.
            fmt: Output format — 'table', 'json', or 'markdown'.

        Returns:
            Formatted report string.
        """
        if fmt == "json":
            return _report_json(result)
        elif fmt == "markdown":
            return _report_markdown(result)
        return _report_table(result)


# ---------------------------------------------------------------------------
# Report formatters
# ---------------------------------------------------------------------------


def _report_table(result: CheckResult) -> str:
    """Format as a simple ASCII table."""
    lines: list[str] = []

    lines.append(f"Files scanned: {result.files_scanned}")
    lines.append(
        f"References: {result.total_count} total, "
        f"{result.valid_count} valid, "
        f"{result.broken_count} broken, "
        f"{result.unresolvable_count} unresolvable"
    )
    lines.append("")

    broken = [r for r in result.refs if r.status == RefStatus.BROKEN]
    unresolvable = [r for r in result.refs if r.status == RefStatus.UNRESOLVABLE]

    if broken:
        lines.append("BROKEN REFERENCES:")
        lines.append(f"{'Reference':<40} {'Type':<8} {'Source':<40} {'Line':<6}")
        lines.append("-" * 96)
        for ref in broken:
            lines.append(
                f"{ref.ref_text:<40} {ref.ref_type.value:<8} "
                f"{ref.source_file:<40} {ref.line_number:<6}"
            )
        lines.append("")

    if unresolvable:
        lines.append("UNRESOLVABLE REFERENCES:")
        lines.append(f"{'Reference':<40} {'Type':<8} {'Source':<40} {'Line':<6}")
        lines.append("-" * 96)
        for ref in unresolvable:
            lines.append(
                f"{ref.ref_text:<40} {ref.ref_type.value:<8} "
                f"{ref.source_file:<40} {ref.line_number:<6}"
            )

    if not broken and not unresolvable:
        lines.append("All references are valid.")

    return "\n".join(lines)


def _report_json(result: CheckResult) -> str:
    """Format as JSON."""
    data = {
        "files_scanned": result.files_scanned,
        "summary": {
            "total": result.total_count,
            "valid": result.valid_count,
            "broken": result.broken_count,
            "unresolvable": result.unresolvable_count,
        },
        "refs": [
            {
                "ref_text": r.ref_text,
                "ref_type": r.ref_type.value,
                "status": r.status.value,
                "source_file": r.source_file,
                "line_number": r.line_number,
                "resolved_path": r.resolved_path,
            }
            for r in result.refs
        ],
    }
    return json.dumps(data, indent=2)


def _report_markdown(result: CheckResult) -> str:
    """Format as Markdown."""
    lines: list[str] = []

    lines.append("## Reference Check Report")
    lines.append("")
    lines.append(f"- **Files scanned**: {result.files_scanned}")
    lines.append(f"- **Total references**: {result.total_count}")
    lines.append(f"- **Valid**: {result.valid_count}")
    lines.append(f"- **Broken**: {result.broken_count}")
    lines.append(f"- **Unresolvable**: {result.unresolvable_count}")
    lines.append("")

    broken = [r for r in result.refs if r.status == RefStatus.BROKEN]
    if broken:
        lines.append("### Broken References")
        lines.append("")
        lines.append("| Reference | Type | Source | Line |")
        lines.append("|-----------|------|--------|------|")
        for ref in broken:
            lines.append(
                f"| `{ref.ref_text}` | {ref.ref_type.value} "
                f"| {ref.source_file} | {ref.line_number} |"
            )
        lines.append("")

    unresolvable = [r for r in result.refs if r.status == RefStatus.UNRESOLVABLE]
    if unresolvable:
        lines.append("### Unresolvable References")
        lines.append("")
        lines.append("| Reference | Type | Source | Line |")
        lines.append("|-----------|------|--------|------|")
        for ref in unresolvable:
            lines.append(
                f"| `{ref.ref_text}` | {ref.ref_type.value} "
                f"| {ref.source_file} | {ref.line_number} |"
            )

    if not broken and not unresolvable:
        lines.append("All references are valid.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------


def check_docs(
    workspace: str,
    docs_dir: str = "docs",
) -> CheckResult:
    """Check all documentation files for broken code references.

    Convenience wrapper for CLI and programmatic use.

    Args:
        workspace: Path to the project root.
        docs_dir: Documentation directory (relative to workspace or absolute).

    Returns:
        CheckResult with all references and their validation status.
    """
    workspace_path = Path(workspace).resolve()
    docs_path = Path(docs_dir)
    if not docs_path.is_absolute():
        docs_path = workspace_path / docs_dir

    checker = ReferenceChecker(workspace_path)
    return checker.scan_directory(docs_path)
