"""Declarations a skill prompt must copy, and the gate that checks the draft.

The skill prompt used to list export names and then demand a code example.
Models filled the example with a literal that was never in the source.
This module pastes the declaration itself and rejects a draft that contradicts it.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

_UNION = re.compile(
    r"^export\s+type\s+([A-Za-z_]\w*)\s*=\s*([^;\n]+)",
    re.M,
)
_QUOTED = re.compile(r"""['"]([^'"]+)['"]""")
_INTERFACE = re.compile(
    r"export\s+interface\s+\w+[^{]*\{([^}]*)\}",
    re.S,
)
_FIELD = re.compile(
    r"^\s*([A-Za-z_]\w*)\??\s*:\s*([A-Za-z_]\w*)\s*;",
    re.M,
)
_AS_CAST = re.compile(
    r"""(['"])([^'"]+)\1\s+as\s+([A-Za-z_]\w*)"""
)
_FIELD_ASSIGN = re.compile(
    r"""\b([A-Za-z_]\w*)\s*:\s*(['"])([^'"]+)\2"""
)
_CALL = re.compile(r"\b([A-Za-z_]\w*)\s*\(([^)]*)\)")
_KW = re.compile(r"^([A-Za-z_]\w*)\s*=")

_MAX_FILES = 8
_MAX_CHUNKS = 40
_MAX_BLOCK_CHARS = 12_000


@dataclass(frozen=True)
class Signature:
    """Callable shape used to reject invented arguments."""

    positional: tuple[str, ...]
    keywords: frozenset[str]
    unlimited_positional: bool = False
    unlimited_keywords: bool = False


@dataclass(frozen=True)
class Bindings:
    unions: dict[str, frozenset[str]]
    fields: dict[str, str]
    signatures: dict[str, Signature]


def read_sources(root: Path, relative_paths: list[str]) -> list[tuple[str, str]]:
    """Read existing source files. Missing paths are skipped."""
    found: list[tuple[str, str]] = []
    for rel in relative_paths:
        if not rel or len(found) >= _MAX_FILES:
            break
        path = root / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        found.append((rel, text))
    return found


def declarations_block(sources: list[tuple[str, str]]) -> str:
    """Markdown section of declarations the model is allowed to copy."""
    sections: list[str] = []
    for rel, text in sources:
        chunks = _declaration_chunks(text)
        if not chunks:
            continue
        body = "\n".join(chunks[:_MAX_CHUNKS])
        sections.append(f"### `{rel}`\n{body}")
        if sum(len(part) for part in sections) >= _MAX_BLOCK_CHARS:
            break
    if not sections:
        return ""
    return (
        "## API Surface (copied from source — use these EXACT declarations)\n\n"
        "Code examples must copy the declarations below. Do not invent "
        "parameters, decorators, or string-literal union members.\n\n"
        + "\n\n".join(sections)
    )


def bindings_from_sources(sources: list[tuple[str, str]]) -> Bindings:
    unions: dict[str, frozenset[str]] = {}
    fields: dict[str, str] = {}
    signatures: dict[str, Signature] = {}
    for _rel, text in sources:
        unions.update(_string_unions(text))
        for field, type_name in _interface_fields(text).items():
            if type_name in unions or type_name in _string_unions(text):
                fields[field] = type_name
        signatures.update(_python_signatures(text))
    fields = {name: type_name for name, type_name in fields.items() if type_name in unions}
    return Bindings(unions=unions, fields=fields, signatures=signatures)


def skill_draft_problems(content: str, sources: list[tuple[str, str]]) -> list[str]:
    """Problems that block writing this draft. Empty means the draft can be written."""
    problems = _shape_problems(content)
    bindings = bindings_from_sources(sources)
    problems.extend(_union_problems(content, bindings))
    problems.extend(_call_problems(content, bindings))
    return problems


def settle_skill_draft(
    llm,
    content: str,
    sources: list[tuple[str, str]],
    *,
    system: str,
) -> tuple[str | None, list[str]]:
    """Return the draft, or one repair. None when the repair is still wrong."""
    problems = skill_draft_problems(content, sources)
    if not problems:
        return content, []
    repaired = llm.complete(
        _repair_prompt(content, problems, sources),
        system=system,
    )
    problems = skill_draft_problems(repaired or "", sources)
    if problems:
        return None, problems
    return repaired, []


def _repair_prompt(
    content: str,
    problems: list[str],
    sources: list[tuple[str, str]],
) -> str:
    listed = "\n".join(f"- {item}" for item in problems)
    surface = declarations_block(sources)
    return (
        "Rewrite this skill. The draft contradicts the source.\n\n"
        f"Problems:\n{listed}\n\n"
        f"{surface}\n\n"
        "Return only the skill markdown. Start with `---`. "
        "Do not wrap it in a fence. Do not return a tool transcript.\n\n"
        f"Draft:\n{content}"
    )


def _declaration_chunks(text: str) -> list[str]:
    chunks: list[str] = []
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        if stripped.startswith("export "):
            block = [lines[index].rstrip()]
            opened = "{" in lines[index] and "}" not in lines[index].split("{", 1)[-1]
            if opened:
                index += 1
                while index < len(lines) and len(block) < 40:
                    block.append(lines[index].rstrip())
                    if "}" in lines[index]:
                        break
                    index += 1
            chunks.append("\n".join(block))
        elif stripped.startswith("@app.middleware"):
            block = [lines[index].rstrip()]
            if index + 1 < len(lines):
                block.append(lines[index + 1].rstrip())
            chunks.append("\n".join(block))
        index += 1
    chunks.extend(_python_signature_lines(text))
    return chunks


def _string_unions(text: str) -> dict[str, frozenset[str]]:
    found: dict[str, frozenset[str]] = {}
    for match in _UNION.finditer(text):
        rhs = match.group(2)
        if re.search(r"[A-Za-z_]\w*", re.sub(r"""['"][^'"]*['"]""", "", rhs)):
            continue
        members = frozenset(_QUOTED.findall(rhs))
        if members:
            found[match.group(1)] = members
    return found


def _interface_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for body in _INTERFACE.findall(text):
        for name, type_name in _FIELD.findall(body):
            fields[name] = type_name
    return fields


def _python_signatures(text: str) -> dict[str, Signature]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return {}
    found: dict[str, Signature] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            found[node.name] = _signature(node)
    return found


def _python_signature_lines(text: str) -> list[str]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    lines: list[str] = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name.startswith("_"):
            continue
        node.body = [ast.Pass()]
        node.decorator_list = []
        rendered = ast.unparse(node)
        rendered = re.sub(r"\s*\n\s*pass\s*$", "", rendered)
        lines.append(" ".join(rendered.split()))
    return lines


def _signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> Signature:
    positional: list[str] = []
    for arg in [*node.args.posonlyargs, *node.args.args]:
        if arg.arg in {"self", "cls"}:
            continue
        positional.append(arg.arg)
    keywords = set(positional)
    keywords.update(arg.arg for arg in node.args.kwonlyargs)
    return Signature(
        positional=tuple(positional),
        keywords=frozenset(keywords),
        unlimited_positional=node.args.vararg is not None,
        unlimited_keywords=node.args.kwarg is not None,
    )


def _shape_problems(content: str) -> list[str]:
    stripped = content.strip()
    if not stripped:
        return ["draft is empty"]
    if stripped.startswith("```"):
        return ["draft is wrapped in a fence"]
    if stripped.startswith("{"):
        return ["draft is a tool transcript, not a skill"]
    if content.count('{"type":') >= 2:
        return ["draft contains a tool transcript"]
    if not (
        stripped.startswith("---")
        or stripped.startswith("#")
        or stripped.startswith("<!--")
    ):
        return ["draft does not start as skill markdown"]
    return []


def _union_problems(content: str, bindings: Bindings) -> list[str]:
    problems: list[str] = []
    for _quote, literal, type_name in _AS_CAST.findall(content):
        members = bindings.unions.get(type_name)
        if members and literal not in members:
            problems.append(
                f"{literal!r} is not a member of {type_name} "
                f"({', '.join(sorted(members))})"
            )
    for field, _quote, literal in _FIELD_ASSIGN.findall(content):
        type_name = bindings.fields.get(field)
        if not type_name:
            continue
        members = bindings.unions.get(type_name, frozenset())
        if literal not in members:
            problems.append(
                f"{field}: {literal!r} is not a member of {type_name} "
                f"({', '.join(sorted(members))})"
            )
    return problems


def _call_problems(content: str, bindings: Bindings) -> list[str]:
    problems: list[str] = []
    for name, args in _CALL.findall(content):
        signature = bindings.signatures.get(name)
        if signature is None or "(" in args:
            continue
        parts = [part.strip() for part in args.split(",") if part.strip()]
        positionals = 0
        for part in parts:
            keyword = _KW.match(part)
            if keyword:
                kw_name = keyword.group(1)
                if (
                    not signature.unlimited_keywords
                    and kw_name not in signature.keywords
                ):
                    problems.append(f"{name}() has no parameter {kw_name}")
                continue
            positionals += 1
        if (
            not signature.unlimited_positional
            and positionals > len(signature.positional)
        ):
            problems.append(
                f"{name}() takes {len(signature.positional)} positional "
                f"arguments, the draft passes {positionals}"
            )
    return problems
