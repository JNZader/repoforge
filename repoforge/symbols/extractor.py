"""
Symbol Extractor — regex-based function/class extraction with body ranges.

Extracts symbols (function and class definitions) from source code using
language-specific regex patterns. Each symbol includes name, kind, file,
line range, and parameter list. Designed for call graph construction.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Symbol:
    """A code symbol extracted from source via regex."""

    name: str
    """Symbol name (e.g., 'process_data', 'UserService')."""

    kind: str
    """Symbol kind: 'function' or 'class'."""

    file: str
    """Relative file path."""

    line: int
    """1-based start line number."""

    end_line: int
    """1-based end line number (last line of body)."""

    params: list[str] = field(default_factory=list)
    """Parameter list (e.g., ['items: list', 'name: str'])."""

    @property
    def id(self) -> str:
        """Unique identifier: file::name."""
        return f"{self.file}::{self.name}"


# ---------------------------------------------------------------------------
# Language-specific regex patterns
# ---------------------------------------------------------------------------

# Python: def func_name(...):  /  class ClassName(...):
_PY_FUNC_RE = re.compile(
    r"^([ \t]*)def\s+(\w+)\s*\(([^)]*)\)\s*(?:->.*?)?:", re.MULTILINE
)
_PY_CLASS_RE = re.compile(
    r"^([ \t]*)class\s+(\w+)\s*(?:\([^)]*\))?\s*:", re.MULTILINE
)

# TypeScript/JavaScript: function name(...)  /  const name = (...) =>
# export function / export class / class Name
_TS_FUNC_RE = re.compile(
    r"^[ \t]*(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)",
    re.MULTILINE,
)
_TS_ARROW_RE = re.compile(
    r"^[ \t]*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(([^)]*)\)\s*(?::\s*\w[^=]*)?\s*=>",
    re.MULTILINE,
)
_TS_CLASS_RE = re.compile(
    r"^[ \t]*(?:export\s+)?class\s+(\w+)", re.MULTILINE,
)
_TS_METHOD_RE = re.compile(
    r"^[ \t]+(?:async\s+)?(\w+)\s*\(([^)]*)\)\s*(?::\s*\w[^{]*)?\s*\{",
    re.MULTILINE,
)

# Go: func Name(...)  /  func (r *Receiver) Name(...)  /  type Name struct
_GO_FUNC_RE = re.compile(
    r"^func\s+(?:\(\s*\w+\s+\*?\w+\s*\)\s+)?(\w+)\s*\(([^)]*)\)",
    re.MULTILINE,
)
_GO_TYPE_RE = re.compile(
    r"^type\s+(\w+)\s+(?:struct|interface)\s*\{", re.MULTILINE,
)


# ---------------------------------------------------------------------------
# Call detection patterns (used by graph builder, exposed here for reuse)
# ---------------------------------------------------------------------------

# Generic function call: name(  — but not keywords
_CALL_RE = re.compile(r"\b(\w+)\s*\(")

# Names to skip (language keywords, builtins)
SKIP_NAMES: frozenset[str] = frozenset({
    # Python
    "if", "for", "while", "with", "return", "yield", "raise", "assert",
    "print", "len", "range", "str", "int", "float", "bool", "list", "dict",
    "set", "tuple", "type", "isinstance", "issubclass", "super", "property",
    "staticmethod", "classmethod", "lambda", "import", "from", "class", "def",
    "True", "False", "None", "self", "cls", "async", "await", "not", "and",
    "or", "in", "is", "del", "try", "except", "finally", "pass", "break",
    "continue", "elif", "else", "global", "nonlocal", "open", "map", "filter",
    "sorted", "reversed", "enumerate", "zip", "any", "all", "min", "max",
    "abs", "round", "hasattr", "getattr", "setattr", "delattr", "callable",
    "repr", "hash", "id", "dir", "vars", "hex", "oct", "bin", "format",
    # JS/TS
    "require", "console", "setTimeout", "setInterval", "Promise", "Array",
    "Object", "String", "Number", "Boolean", "Map", "Set", "Date", "Error",
    "JSON", "Math", "RegExp", "Symbol", "Function", "Proxy", "Reflect",
    "undefined", "null", "new", "this", "typeof", "instanceof", "void",
    "delete", "throw", "switch", "case", "default", "catch",
    # Go
    "make", "append", "copy", "close", "panic", "recover", "cap",
    "fmt", "log", "errors", "context", "nil", "func", "go", "defer",
    "select", "chan", "var", "const", "package", "struct", "interface",
})


# ---------------------------------------------------------------------------
# Extraction logic
# ---------------------------------------------------------------------------


def _compute_end_line_indent(lines: list[str], start_line: int, indent: str) -> int:
    """Compute end line of a block based on indentation (Python-style).

    Walks forward from start_line until a line with equal or less indentation
    is found (or EOF). Returns the 1-based end line.
    """
    indent_len = len(indent)
    end = start_line
    for i in range(start_line, len(lines)):
        line = lines[i]
        stripped = line.lstrip()
        if not stripped:  # blank line — continue
            continue
        line_indent = len(line) - len(stripped)
        if line_indent <= indent_len and i > start_line - 1:
            break
        end = i + 1  # 1-based
    return end


def _compute_end_line_brace(content: str, start_pos: int) -> int:
    """Compute end line of a brace-delimited block ({...}).

    Counts braces from start_pos until balanced. Returns 1-based end line.
    """
    depth = 0
    found_open = False
    line = content[:start_pos].count("\n") + 1

    for i in range(start_pos, len(content)):
        ch = content[i]
        if ch == "{":
            depth += 1
            found_open = True
        elif ch == "}":
            depth -= 1
            if found_open and depth == 0:
                return content[:i + 1].count("\n") + 1
        elif ch == "\n":
            line += 1

    return line


def _extract_python(content: str, file_path: str) -> list[Symbol]:
    """Extract symbols from Python source."""
    symbols: list[Symbol] = []
    lines = content.split("\n")

    for m in _PY_FUNC_RE.finditer(content):
        indent = m.group(1)
        name = m.group(2)
        params_raw = m.group(3).strip()
        params = [p.strip() for p in params_raw.split(",") if p.strip()] if params_raw else []
        line = content[:m.start()].count("\n") + 1
        end_line = _compute_end_line_indent(lines, line, indent)
        symbols.append(Symbol(
            name=name, kind="function", file=file_path,
            line=line, end_line=end_line, params=params,
        ))

    for m in _PY_CLASS_RE.finditer(content):
        indent = m.group(1)
        name = m.group(2)
        line = content[:m.start()].count("\n") + 1
        end_line = _compute_end_line_indent(lines, line, indent)
        symbols.append(Symbol(
            name=name, kind="class", file=file_path,
            line=line, end_line=end_line,
        ))

    return symbols


def _extract_typescript(content: str, file_path: str) -> list[Symbol]:
    """Extract symbols from TypeScript/JavaScript source."""
    symbols: list[Symbol] = []

    for m in _TS_FUNC_RE.finditer(content):
        name = m.group(1)
        params_raw = m.group(2).strip()
        params = [p.strip() for p in params_raw.split(",") if p.strip()] if params_raw else []
        line = content[:m.start()].count("\n") + 1
        end_line = _compute_end_line_brace(content, m.start())
        symbols.append(Symbol(
            name=name, kind="function", file=file_path,
            line=line, end_line=end_line, params=params,
        ))

    for m in _TS_ARROW_RE.finditer(content):
        name = m.group(1)
        params_raw = m.group(2).strip()
        params = [p.strip() for p in params_raw.split(",") if p.strip()] if params_raw else []
        line = content[:m.start()].count("\n") + 1
        # Arrow functions may use braces or expression body
        end_line = _compute_end_line_brace(content, m.start())
        symbols.append(Symbol(
            name=name, kind="function", file=file_path,
            line=line, end_line=end_line, params=params,
        ))

    for m in _TS_CLASS_RE.finditer(content):
        name = m.group(1)
        line = content[:m.start()].count("\n") + 1
        end_line = _compute_end_line_brace(content, m.start())
        symbols.append(Symbol(
            name=name, kind="class", file=file_path,
            line=line, end_line=end_line,
        ))

    return symbols


def _extract_go(content: str, file_path: str) -> list[Symbol]:
    """Extract symbols from Go source."""
    symbols: list[Symbol] = []

    for m in _GO_FUNC_RE.finditer(content):
        name = m.group(1)
        params_raw = m.group(2).strip()
        params = [p.strip() for p in params_raw.split(",") if p.strip()] if params_raw else []
        line = content[:m.start()].count("\n") + 1
        end_line = _compute_end_line_brace(content, m.start())
        symbols.append(Symbol(
            name=name, kind="function", file=file_path,
            line=line, end_line=end_line, params=params,
        ))

    for m in _GO_TYPE_RE.finditer(content):
        name = m.group(1)
        line = content[:m.start()].count("\n") + 1
        end_line = _compute_end_line_brace(content, m.start())
        symbols.append(Symbol(
            name=name, kind="class", file=file_path,
            line=line, end_line=end_line,
        ))

    return symbols


# ---------------------------------------------------------------------------
# Language dispatch
# ---------------------------------------------------------------------------

_LANG_MAP: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript", ".tsx": "typescript",
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript",
    ".go": "go",
}

_EXTRACTORS = {
    "python": _extract_python,
    "typescript": _extract_typescript,
    "javascript": _extract_typescript,  # same regex patterns
    "go": _extract_go,
}


def detect_language(file_path: str) -> str | None:
    """Detect language from file extension. Returns None if unsupported."""
    from pathlib import Path
    ext = Path(file_path).suffix.lower()
    return _LANG_MAP.get(ext)


def extract_symbols(content: str, language: str, file_path: str = "") -> list[Symbol]:
    """Extract symbols from source code for a given language.

    Args:
        content: Source file content.
        language: Language identifier ('python', 'typescript', 'go', etc.).
        file_path: Relative file path for Symbol.file field.

    Returns:
        List of Symbol instances. Empty list if language is unsupported
        or content is empty.
    """
    if not content or not content.strip():
        return []

    extractor = _EXTRACTORS.get(language)
    if extractor is None:
        return []

    try:
        return extractor(content, file_path)
    except Exception as e:
        logger.debug("Symbol extraction failed for %s: %s", file_path, e)
        return []
