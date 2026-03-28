"""
Tree-sitter based source code compression.

Extracts ONLY the API surface from source files:
  - Function/method signatures (no bodies)
  - Class/struct/interface definitions (no method bodies)
  - Import statements
  - Top-level constants/variables
  - Docstrings/comments on exported symbols

Result: a skeleton of the file that preserves the API surface while
removing implementation details. Estimated 60-80% token reduction.

Falls back to first-N-lines extraction when tree-sitter is not available.
"""

from __future__ import annotations

import logging
import re
from pathlib import PurePosixPath

logger = logging.getLogger(__name__)

# Characters per token for estimation
_CHARS_PER_TOKEN = 4

# Max lines to include in fallback mode
_FALLBACK_MAX_LINES = 30


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compress_file(content: str, file_path: str) -> str:
    """Compress a source file to its API surface using tree-sitter.

    Extracts only:
      - Import/use/require statements
      - Function/method signatures (no bodies)
      - Class/struct/interface/enum definitions (no method bodies)
      - Top-level constants and variables
      - Docstrings on exported symbols

    Falls back to first N lines if tree-sitter is not available or
    the language is not supported.

    Args:
        content: Source file content as string.
        file_path: Relative file path (used for language detection).

    Returns:
        Compressed source — API skeleton only.
    """
    if not content.strip():
        return ""

    # Detect language from extension
    ext = PurePosixPath(file_path).suffix.lower()

    # Try tree-sitter compression
    try:
        from . import INTELLIGENCE_AVAILABLE
        if INTELLIGENCE_AVAILABLE:
            compressed = _compress_with_treesitter(content, ext)
            if compressed is not None:
                return compressed
    except Exception:
        logger.debug("Tree-sitter compression failed for %s", file_path, exc_info=True)

    # Fallback: first N lines
    return _fallback_compress(content)


def compress_batch(contents: dict[str, str]) -> dict[str, str]:
    """Compress multiple source files to their API surfaces.

    Iterates over all entries calling :func:`compress_file` for each one.
    If compression fails for a file (unsupported extension, parse error, etc.)
    the original content is used as fallback.

    Args:
        contents: Mapping of relative file path to source content.

    Returns:
        Mapping with the same keys; values are compressed content.
    """
    result: dict[str, str] = {}
    for path, content in contents.items():
        try:
            result[path] = compress_file(content, path)
        except Exception:
            logger.warning("Compression failed for %s, using original content", path)
            result[path] = content
    return result


def compression_stats(original: str, compressed: str) -> dict[str, int | float]:
    """Compute compression statistics.

    Returns:
        Dict with original_tokens, compressed_tokens, ratio, reduction_pct.
    """
    orig_tokens = max(1, len(original) // _CHARS_PER_TOKEN)
    comp_tokens = max(1, len(compressed) // _CHARS_PER_TOKEN) if compressed else 0
    ratio = comp_tokens / orig_tokens if orig_tokens > 0 else 0.0
    return {
        "original_tokens": orig_tokens,
        "compressed_tokens": comp_tokens,
        "ratio": ratio,
        "reduction_pct": (1.0 - ratio) * 100,
    }


# ---------------------------------------------------------------------------
# Tree-sitter compression by language
# ---------------------------------------------------------------------------

# Extension -> tree-sitter language name
_EXT_TO_LANG: dict[str, str] = {
    ".py": "python",
    ".go": "go",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".jsx": "javascript",
    ".java": "java",
    ".rs": "rust",
}


def _compress_with_treesitter(content: str, ext: str) -> str | None:
    """Compress using tree-sitter AST. Returns None if unsupported."""
    lang = _EXT_TO_LANG.get(ext)
    if not lang:
        return None

    from .ast_extractor import get_parser, parse_source

    parser = get_parser(lang)
    root = parse_source(parser, content)
    if root is None:
        return None

    lines = content.split("\n")

    # Dispatch to language-specific compressor
    if lang == "python":
        return _compress_python(root, lines)
    elif lang == "go":
        return _compress_go(root, lines)
    elif lang in ("typescript", "tsx", "javascript"):
        return _compress_ts_js(root, lines)
    elif lang == "java":
        return _compress_java(root, lines)
    elif lang == "rust":
        return _compress_rust(root, lines)
    return None


# ---------------------------------------------------------------------------
# Python compressor
# ---------------------------------------------------------------------------


def _compress_python(root, lines: list[str]) -> str:
    """Extract Python API surface: imports, class/def signatures, docstrings."""
    parts: list[str] = []

    for node in root.children:
        ntype = node.type

        # Import statements
        if ntype in ("import_statement", "import_from_statement"):
            parts.append(_get_source_lines(lines, node))

        # Module-level assignments (constants, __all__, etc.)
        elif ntype == "expression_statement":
            text = _get_source_lines(lines, node)
            # Include assignments that look like constants or __all__
            if "=" in text and (text.split("=")[0].strip().isupper() or "__" in text.split("=")[0]):
                parts.append(text)

        # Function definitions
        elif ntype == "function_definition":
            parts.append(_python_function_skeleton(node, lines))

        # Class definitions
        elif ntype == "class_definition":
            parts.append(_python_class_skeleton(node, lines))

        # Decorated definitions
        elif ntype == "decorated_definition":
            parts.append(_python_decorated_skeleton(node, lines))

    return "\n\n".join(parts) if parts else _fallback_compress("\n".join(lines))


def _python_function_skeleton(node, lines: list[str]) -> str:
    """Extract function signature + docstring."""
    # Get the def line(s) — may span multiple lines with long params
    sig_parts: list[str] = []
    for child in node.children:
        if child.type == "block":
            break
        sig_parts.append(_get_source_lines(lines, child))

    sig = " ".join(sig_parts) if sig_parts else _get_first_line(lines, node)

    # Reconstruct a clean signature
    first_line = _get_first_line(lines, node)
    # Find colon position to get full signature
    sig = _extract_until_colon(lines, node)

    docstring = _python_docstring(node)
    if docstring:
        return f"{sig}\n    {docstring}"
    return f"{sig}\n    ..."


def _python_class_skeleton(node, lines: list[str]) -> str:
    """Extract class definition + method signatures."""
    # Class header
    header = _extract_until_colon(lines, node)
    body_parts: list[str] = []

    # Find the block child
    for child in node.children:
        if child.type == "block":
            # Extract docstring and method signatures from class body
            for member in child.children:
                if member.type == "expression_statement":
                    # Could be a docstring
                    text = _get_source_lines(lines, member).strip()
                    if text.startswith(('"""', "'''", '"', "'")):
                        body_parts.append(f"    {text}")
                elif member.type == "function_definition":
                    sig = _extract_until_colon(lines, member)
                    body_parts.append(f"    {sig.strip()}\n        ...")
                elif member.type == "decorated_definition":
                    deco_text = _python_decorated_sig(member, lines, indent="    ")
                    body_parts.append(deco_text)
            break

    if body_parts:
        return header + "\n" + "\n".join(body_parts)
    return header + "\n    ..."


def _python_decorated_skeleton(node, lines: list[str]) -> str:
    """Extract decorator + function/class signature."""
    parts: list[str] = []
    for child in node.children:
        if child.type == "decorator":
            parts.append(_get_source_lines(lines, child))
        elif child.type == "function_definition":
            parts.append(_python_function_skeleton(child, lines))
        elif child.type == "class_definition":
            parts.append(_python_class_skeleton(child, lines))
    return "\n".join(parts)


def _python_decorated_sig(node, lines: list[str], indent: str = "") -> str:
    """Extract decorator + def signature for class methods."""
    parts: list[str] = []
    for child in node.children:
        if child.type == "decorator":
            parts.append(f"{indent}{_get_source_lines(lines, child).strip()}")
        elif child.type == "function_definition":
            sig = _extract_until_colon(lines, child)
            parts.append(f"{indent}{sig.strip()}\n{indent}    ...")
    return "\n".join(parts)


def _python_docstring(node) -> str | None:
    """Extract first-line docstring from a function/class node."""
    for child in node.children:
        if child.type == "block":
            for stmt in child.children:
                if stmt.type == "expression_statement":
                    for expr in stmt.children:
                        if expr.type == "string":
                            text = expr.text.decode("utf-8") if isinstance(expr.text, bytes) else str(expr.text)
                            return text
                    return None
                elif stmt.type not in ("comment", "newline"):
                    return None
    return None


# ---------------------------------------------------------------------------
# Go compressor
# ---------------------------------------------------------------------------


def _compress_go(root, lines: list[str]) -> str:
    """Extract Go API surface: package, imports, func signatures, types."""
    parts: list[str] = []

    for node in root.children:
        ntype = node.type

        # Package declaration
        if ntype == "package_clause":
            parts.append(_get_source_lines(lines, node))

        # Import declarations
        elif ntype == "import_declaration":
            parts.append(_get_source_lines(lines, node))

        # Function/method declarations (signature only)
        elif ntype in ("function_declaration", "method_declaration"):
            # Get everything up to the body block
            sig = _go_function_sig(node, lines)
            parts.append(sig)

        # Type declarations (struct, interface, etc.)
        elif ntype == "type_declaration":
            parts.append(_get_source_lines(lines, node))

        # Const/var declarations
        elif ntype in ("const_declaration", "var_declaration"):
            parts.append(_get_source_lines(lines, node))

        # Comment groups (package-level docs)
        elif ntype == "comment":
            text = _get_source_lines(lines, node)
            if text.startswith("//") and not text.startswith("// +build"):
                parts.append(text)

    return "\n\n".join(parts) if parts else _fallback_compress("\n".join(lines))


def _go_function_sig(node, lines: list[str]) -> str:
    """Extract Go function signature without body."""
    # Collect all children up to the block (function body)
    sig_end_line = node.start_point[0]
    for child in node.children:
        if child.type == "block":
            break
        sig_end_line = child.end_point[0]

    # Get lines from start to before block
    start = node.start_point[0]
    return "\n".join(lines[start:sig_end_line + 1]).rstrip(" {")


# ---------------------------------------------------------------------------
# TypeScript/JavaScript compressor
# ---------------------------------------------------------------------------


def _compress_ts_js(root, lines: list[str]) -> str:
    """Extract TS/JS API surface: imports, exports, interfaces, function sigs."""
    parts: list[str] = []

    for node in root.children:
        ntype = node.type

        # Imports
        if ntype == "import_statement":
            parts.append(_get_source_lines(lines, node))

        # Export statements
        elif ntype == "export_statement":
            parts.append(_ts_export_skeleton(node, lines))

        # Interface/type declarations
        elif ntype in ("interface_declaration", "type_alias_declaration"):
            parts.append(_get_source_lines(lines, node))

        # Enum declarations
        elif ntype == "enum_declaration":
            parts.append(_get_source_lines(lines, node))

        # Function declarations
        elif ntype == "function_declaration":
            sig = _ts_function_sig(node, lines)
            parts.append(sig)

        # Class declarations
        elif ntype == "class_declaration":
            parts.append(_ts_class_skeleton(node, lines))

        # Lexical (const/let) declarations at top level
        elif ntype == "lexical_declaration":
            text = _get_source_lines(lines, node)
            # Only include if it looks like a constant or export
            if "const " in text:
                # Truncate long declarations
                if len(text) > 200:
                    text = text[:200] + " ..."
                parts.append(text)

    return "\n\n".join(parts) if parts else _fallback_compress("\n".join(lines))


def _ts_export_skeleton(node, lines: list[str]) -> str:
    """Extract export statement, compressing function/class bodies."""
    # For simple exports, include full text
    text = _get_source_lines(lines, node)
    # If it contains a function body, truncate
    for child in node.children:
        if child.type in ("function_declaration", "class_declaration"):
            if child.type == "function_declaration":
                sig = _ts_function_sig(child, lines)
                return f"export {sig}"
            elif child.type == "class_declaration":
                skeleton = _ts_class_skeleton(child, lines)
                return f"export {skeleton}"
    # For short exports, include as-is
    if len(text) <= 300:
        return text
    return text[:300] + " ..."


def _ts_function_sig(node, lines: list[str]) -> str:
    """Extract TS/JS function signature without body."""
    start = node.start_point[0]
    # Find the statement_block child
    for child in node.children:
        if child.type == "statement_block":
            # Get everything up to the opening brace
            end = child.start_point[0]
            sig_lines = lines[start:end + 1]
            sig = "\n".join(sig_lines).rstrip().rstrip("{").rstrip()
            return sig + " { ... }"
    return _get_first_line(lines, node)


def _ts_class_skeleton(node, lines: list[str]) -> str:
    """Extract TS/JS class with method signatures only."""
    first_line = _get_first_line(lines, node)
    body_parts: list[str] = []

    for child in node.children:
        if child.type == "class_body":
            for member in child.children:
                if member.type in ("method_definition", "public_field_definition",
                                   "property_declaration"):
                    sig = _get_first_line(lines, member)
                    body_parts.append(f"  {sig.strip()}")
    if body_parts:
        return first_line + "\n" + "\n".join(body_parts) + "\n}"
    return first_line + " { ... }"


# ---------------------------------------------------------------------------
# Java compressor
# ---------------------------------------------------------------------------


def _compress_java(root, lines: list[str]) -> str:
    """Extract Java API surface: package, imports, class/interface signatures."""
    parts: list[str] = []

    for node in root.children:
        ntype = node.type

        if ntype == "package_declaration":
            parts.append(_get_source_lines(lines, node))
        elif ntype == "import_declaration":
            parts.append(_get_source_lines(lines, node))
        elif ntype in ("class_declaration", "interface_declaration",
                       "enum_declaration", "record_declaration"):
            parts.append(_java_class_skeleton(node, lines))

    return "\n\n".join(parts) if parts else _fallback_compress("\n".join(lines))


def _java_class_skeleton(node, lines: list[str]) -> str:
    """Extract Java class with method signatures only."""
    header = _get_first_line(lines, node)
    body_parts: list[str] = []

    for child in node.children:
        if child.type == "class_body":
            for member in child.children:
                if member.type in ("method_declaration", "constructor_declaration"):
                    sig = _java_method_sig(member, lines)
                    body_parts.append(f"    {sig}")
                elif member.type == "field_declaration":
                    body_parts.append(f"    {_get_source_lines(lines, member)}")
                elif member.type in ("class_declaration", "interface_declaration",
                                     "enum_declaration"):
                    # Nested types — just show header
                    body_parts.append(f"    {_get_first_line(lines, member)} {{ ... }}")

    if body_parts:
        return header + "\n" + "\n".join(body_parts) + "\n}"
    return header + " { ... }"


def _java_method_sig(node, lines: list[str]) -> str:
    """Extract Java method signature without body."""
    start = node.start_point[0]
    for child in node.children:
        if child.type == "block":
            end = child.start_point[0]
            sig = "\n".join(lines[start:end + 1]).rstrip().rstrip("{").rstrip()
            return sig + " { ... }"
    return _get_first_line(lines, node)


# ---------------------------------------------------------------------------
# Rust compressor
# ---------------------------------------------------------------------------


def _compress_rust(root, lines: list[str]) -> str:
    """Extract Rust API surface: use, pub fn/struct/enum/trait signatures."""
    parts: list[str] = []

    for node in root.children:
        ntype = node.type

        if ntype == "use_declaration":
            parts.append(_get_source_lines(lines, node))
        elif ntype in ("function_item", "struct_item", "enum_item",
                       "trait_item", "impl_item", "type_item",
                       "const_item", "static_item"):
            parts.append(_rust_item_skeleton(node, lines))
        elif ntype == "mod_item":
            parts.append(_get_first_line(lines, node))
        elif ntype == "attribute_item":
            parts.append(_get_source_lines(lines, node))

    return "\n\n".join(parts) if parts else _fallback_compress("\n".join(lines))


def _rust_item_skeleton(node, lines: list[str]) -> str:
    """Extract Rust item signature without body."""
    ntype = node.type

    if ntype == "function_item":
        # Get everything up to the block
        start = node.start_point[0]
        for child in node.children:
            if child.type == "block":
                end = child.start_point[0]
                sig = "\n".join(lines[start:end + 1]).rstrip().rstrip("{").rstrip()
                return sig + " { ... }"
        return _get_first_line(lines, node)

    elif ntype == "impl_item":
        # Show impl header + method signatures
        header = _get_first_line(lines, node)
        body_parts: list[str] = []
        for child in node.children:
            if child.type == "declaration_list":
                for member in child.children:
                    if member.type == "function_item":
                        sig = _rust_item_skeleton(member, lines)
                        body_parts.append(f"    {sig.strip()}")
        if body_parts:
            return header + "\n" + "\n".join(body_parts) + "\n}"
        return header + " { ... }"

    elif ntype in ("struct_item", "enum_item"):
        return _get_source_lines(lines, node)

    elif ntype == "trait_item":
        header = _get_first_line(lines, node)
        body_parts: list[str] = []
        for child in node.children:
            if child.type == "declaration_list":
                for member in child.children:
                    if member.type == "function_item":
                        sig = _rust_item_skeleton(member, lines)
                        body_parts.append(f"    {sig.strip()}")
        if body_parts:
            return header + "\n" + "\n".join(body_parts) + "\n}"
        return header + " { ... }"

    # Default: include full text for const/static/type
    return _get_source_lines(lines, node)


# ---------------------------------------------------------------------------
# Fallback compression (no tree-sitter)
# ---------------------------------------------------------------------------


def _fallback_compress(content: str) -> str:
    """Fallback: include first N lines when tree-sitter is not available."""
    lines = content.split("\n")
    if len(lines) <= _FALLBACK_MAX_LINES:
        return content
    truncated = lines[:_FALLBACK_MAX_LINES]
    truncated.append(f"# ... ({len(lines) - _FALLBACK_MAX_LINES} more lines)")
    return "\n".join(truncated)


# ---------------------------------------------------------------------------
# Line extraction helpers
# ---------------------------------------------------------------------------


def _get_source_lines(lines: list[str], node) -> str:
    """Get the full source text for a node from the original lines."""
    start = node.start_point[0]
    end = node.end_point[0]
    return "\n".join(lines[start:end + 1])


def _get_first_line(lines: list[str], node) -> str:
    """Get just the first line of a node."""
    return lines[node.start_point[0]]


def _extract_until_colon(lines: list[str], node) -> str:
    """Extract Python def/class lines up to and including the colon."""
    start = node.start_point[0]
    # Walk lines until we find a colon at the end
    for i in range(start, min(start + 10, len(lines))):
        stripped = lines[i].rstrip()
        if stripped.endswith(":"):
            return "\n".join(lines[start:i + 1])
    return lines[start]
