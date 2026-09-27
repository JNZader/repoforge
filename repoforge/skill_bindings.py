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
_MAX_IMPORTS = 6
_MAX_CHUNKS = 40
_MAX_BLOCK_CHARS = 12_000
_FROM_SPEC = re.compile(r"""from\s+['"](\.[^'"]+)['"]""")
_PY_RELATIVE = re.compile(r"^\s*from\s+(\.+)([\w.]*)\s+import", re.M)
_PROBLEM_CALL = re.compile(r"\b([A-Za-z_]\w*)\(\)")
_PROBLEM_TYPE = re.compile(r"member of ([A-Za-z_]\w*)")


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


def include_local_imports(
    root: Path,
    sources: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Add files imported by relative specifiers, one hop, so a union can cross files.

    ``api.ts`` imports ``./types``. A skill for ``api.ts`` has to see
    ``GenerationMode`` even though that alias lives in the other file.
    """
    root = root.resolve()
    seen = {rel for rel, _text in sources}
    extra: list[tuple[str, str]] = []
    for rel, text in sources:
        for imported in _local_import_paths(root, rel, text):
            if imported in seen or len(extra) >= _MAX_IMPORTS:
                continue
            path = root / imported
            if not path.is_file():
                continue
            try:
                body = path.read_text(encoding="utf-8")
            except OSError:
                continue
            seen.add(imported)
            extra.append((imported, body))
    return [*sources, *extra]


def declarations_block(
    sources: list[tuple[str, str]],
    full_rels: set[str] | None = None,
) -> str:
    """Markdown section of declarations the model is allowed to copy.

    Imported files contribute only their union lines. The file under
    documentation keeps its full declaration list.
    """
    if full_rels is None:
        full_rels = {rel for rel, _text in sources}
    sections: list[str] = []
    for rel, text in sources:
        chunks = _declaration_chunks(text) if rel in full_rels else _union_lines(text)
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
    """Ask for one correction. Quote the broken declaration, not the whole file."""
    listed = "\n".join(f"- {item}" for item in problems)
    cited = _cited_lines(problems, sources)
    guide = f"Use exactly:\n{cited}\n\n" if cited else ""
    return (
        "Fix this skill. Change only the lines named below. "
        "Keep every other section.\n"
        "Start with `---`. Do not wrap the skill in a fence.\n\n"
        f"Problems:\n{listed}\n\n"
        f"{guide}"
        f"Draft:\n{content}"
    )


def _cited_lines(problems: list[str], sources: list[tuple[str, str]]) -> str:
    names: set[str] = set()
    for problem in problems:
        names.update(_PROBLEM_CALL.findall(problem))
        names.update(_PROBLEM_TYPE.findall(problem))
    if not names:
        return ""
    lines: list[str] = []
    seen: set[str] = set()
    for _rel, text in sources:
        for chunk in _declaration_chunks(text):
            for line in chunk.splitlines():
                stripped = line.strip()
                if stripped in seen:
                    continue
                if _line_names(stripped, names):
                    seen.add(stripped)
                    lines.append(stripped)
        for line in _union_lines(text):
            if line not in seen and _line_names(line, names):
                seen.add(line)
                lines.append(line)
    return "\n".join(lines)


def _line_names(line: str, names: set[str]) -> bool:
    for name in names:
        if re.search(rf"\bdef\s+{re.escape(name)}\b", line):
            return True
        if re.search(rf"\btype\s+{re.escape(name)}\b", line):
            return True
        if re.search(rf"\b{re.escape(name)}\s*:", line):
            return True
    return False


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


def _union_lines(text: str) -> list[str]:
    """Union aliases and the fields that use them. Short enough for a small model."""
    unions = _string_unions(text)
    lines: list[str] = []
    for match in _UNION.finditer(text):
        if match.group(1) in unions:
            lines.append(match.group(0).strip())
    for field, type_name in _interface_fields(text).items():
        if type_name in unions:
            lines.append(f"{field}: {type_name}")
    return lines


def _local_import_paths(root: Path, rel: str, text: str) -> list[str]:
    found: list[str] = []
    for spec in _FROM_SPEC.findall(text):
        resolved = _resolve_relative(root, rel, spec)
        if resolved and resolved not in found:
            found.append(resolved)
    if rel.endswith(".py"):
        for dots, rest in _PY_RELATIVE.findall(text):
            spec = "../" * (len(dots) - 1) + rest.replace(".", "/")
            if spec.endswith("/"):
                spec = spec[:-1]
            if not spec:
                continue
            resolved = _resolve_relative(root, rel, spec)
            if resolved and resolved not in found:
                found.append(resolved)
    return found


def _resolve_relative(root: Path, rel: str, spec: str) -> str | None:
    root_resolved = root.resolve()
    raw = ((root / rel).parent / spec).resolve()
    suffixes = ("", ".ts", ".tsx", ".js", ".mjs", ".py")
    indexes = ("index.ts", "index.tsx", "__init__.py")
    candidates = [Path(str(raw) + suffix) for suffix in suffixes]
    candidates.extend(raw / name for name in indexes)
    for candidate in candidates:
        try:
            relative = candidate.resolve().relative_to(root_resolved).as_posix()
        except ValueError:
            continue
        if candidate.is_file():
            return relative
    return None


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
