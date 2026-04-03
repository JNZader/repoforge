"""
diff.py — Entity-level semantic diffs.

Compares two git refs at the symbol level: which functions/classes were
added, removed, modified (cosmetic vs logic), or renamed.  Reuses the
regex-based symbol extractor from ``symbols/extractor.py``.

No external dependencies beyond git on PATH.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .symbols.extractor import Symbol, detect_language, extract_symbols

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class DiffEntry:
    """A single entity-level diff entry."""

    name: str
    """Symbol name (e.g. 'process_data', 'UserService')."""

    kind: str
    """Symbol kind: 'function' or 'class'."""

    file: str
    """Relative file path."""

    status: str
    """One of: 'added', 'removed', 'modified', 'renamed'."""

    change_type: str | None = None
    """For 'modified': 'cosmetic' (whitespace only) or 'logic'. None otherwise."""

    old_name: str | None = None
    """For 'renamed': the previous symbol name. None otherwise."""

    line: int | None = None
    """1-based line number in the *target* ref (ref_b). None for removed."""


@dataclass
class DiffResult:
    """Aggregated result of an entity-level diff."""

    ref_a: str
    ref_b: str
    entries: list[DiffEntry] = field(default_factory=list)

    @property
    def added(self) -> list[DiffEntry]:
        return [e for e in self.entries if e.status == "added"]

    @property
    def removed(self) -> list[DiffEntry]:
        return [e for e in self.entries if e.status == "removed"]

    @property
    def modified(self) -> list[DiffEntry]:
        return [e for e in self.entries if e.status == "modified"]

    @property
    def renamed(self) -> list[DiffEntry]:
        return [e for e in self.entries if e.status == "renamed"]

    @property
    def summary(self) -> dict[str, int]:
        return {
            "added": len(self.added),
            "removed": len(self.removed),
            "modified": len(self.modified),
            "renamed": len(self.renamed),
            "total": len(self.entries),
        }


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _run_git(repo_path: str, *args: str) -> str:
    """Run a git command and return stdout. Raises on failure."""
    cmd = ["git", "-C", repo_path, *args]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(
            f"git command failed: {' '.join(cmd)}\n{result.stderr.strip()}"
        )
    return result.stdout


def _get_changed_files(repo_path: str, ref_a: str, ref_b: str) -> list[str]:
    """Return list of files changed between two refs."""
    out = _run_git(repo_path, "diff", "--name-only", ref_a, ref_b)
    return [f for f in out.strip().splitlines() if f]


def _get_file_at_ref(repo_path: str, ref: str, file_path: str) -> str | None:
    """Return file content at a git ref, or None if file doesn't exist at that ref."""
    try:
        return _run_git(repo_path, "show", f"{ref}:{file_path}")
    except RuntimeError:
        return None


# ---------------------------------------------------------------------------
# Body normalization & hashing
# ---------------------------------------------------------------------------

# Pattern to strip single-line comments (Python #, JS/TS/Go //)
_COMMENT_RE = re.compile(r"(#|//).*$", re.MULTILINE)


def _normalize_body(
    content: str, start_line: int, end_line: int, *, skip_decl: bool = False,
) -> str:
    """Extract and normalize a symbol's body for comparison.

    Strips comments, collapses whitespace within lines, removes blank lines.
    Lines are 1-based.

    Args:
        skip_decl: If True, skip the first line (the def/class declaration).
                   Useful for rename detection where the name differs but body is same.
    """
    lines = content.splitlines()
    # Clamp to valid range
    start = max(0, start_line - 1)
    end = min(len(lines), end_line)
    if skip_decl and end > start + 1:
        start += 1
    body = "\n".join(lines[start:end])
    # Strip comments
    body = _COMMENT_RE.sub("", body)
    # Normalize whitespace: collapse runs within each line, strip, drop blanks
    normalized_lines = []
    for line in body.splitlines():
        # Collapse internal whitespace runs to single space
        stripped = re.sub(r"\s+", " ", line.strip())
        if stripped:
            normalized_lines.append(stripped)
    return "\n".join(normalized_lines)


def _raw_body(content: str, start_line: int, end_line: int) -> str:
    """Extract raw (unmodified) body text for a symbol. Lines are 1-based."""
    lines = content.splitlines()
    start = max(0, start_line - 1)
    end = min(len(lines), end_line)
    return "\n".join(lines[start:end])


def _body_hash(normalized_body: str) -> str:
    """SHA256 hash of a normalized body string."""
    return hashlib.sha256(normalized_body.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Core diff logic
# ---------------------------------------------------------------------------


def _extract_file_symbols(
    repo_path: str, ref: str, file_path: str
) -> tuple[list[Symbol], str | None]:
    """Extract symbols from a file at a given ref.

    Returns (symbols, content) or ([], None) if file/language unsupported.
    """
    lang = detect_language(file_path)
    if lang is None:
        return [], None
    content = _get_file_at_ref(repo_path, ref, file_path)
    if content is None:
        return [], None
    symbols = extract_symbols(content, lang, file_path)
    return symbols, content


def _match_symbols(
    symbols_a: list[Symbol],
    symbols_b: list[Symbol],
    content_a: str | None,
    content_b: str | None,
) -> list[DiffEntry]:
    """Compare two symbol lists from the same file and produce diff entries."""
    entries: list[DiffEntry] = []

    # Index by (name, kind)
    map_a: dict[tuple[str, str], Symbol] = {(s.name, s.kind): s for s in symbols_a}
    map_b: dict[tuple[str, str], Symbol] = {(s.name, s.kind): s for s in symbols_b}

    keys_a = set(map_a.keys())
    keys_b = set(map_b.keys())

    # Modified: present in both
    for key in keys_a & keys_b:
        sym_a = map_a[key]
        sym_b = map_b[key]

        if content_a and content_b:
            # Raw body extraction (no normalization) to detect ANY change
            raw_a = _raw_body(content_a, sym_a.line, sym_a.end_line)
            raw_b = _raw_body(content_b, sym_b.line, sym_b.end_line)
            if raw_a == raw_b:
                continue  # Truly identical — no diff entry

            # Normalized comparison to classify cosmetic vs logic
            norm_a = _normalize_body(content_a, sym_a.line, sym_a.end_line)
            norm_b = _normalize_body(content_b, sym_b.line, sym_b.end_line)
            change_type = "cosmetic" if norm_a == norm_b else "logic"
        else:
            change_type = "logic"

        entries.append(DiffEntry(
            name=sym_b.name,
            kind=sym_b.kind,
            file=sym_b.file,
            status="modified",
            change_type=change_type,
            line=sym_b.line,
        ))

    # Removed: in A but not B
    only_a = [(map_a[k], k) for k in keys_a - keys_b]
    # Added: in B but not A
    only_b = [(map_b[k], k) for k in keys_b - keys_a]

    # Rename detection: match removed → added by body hash
    renamed_a: set[tuple[str, str]] = set()
    renamed_b: set[tuple[str, str]] = set()

    if content_a and content_b and only_a and only_b:
        # Build hash → symbol maps (skip declaration line so name change doesn't affect hash)
        hash_to_a: dict[str, list[tuple[Symbol, tuple[str, str]]]] = {}
        for sym, key in only_a:
            body = _normalize_body(content_a, sym.line, sym.end_line, skip_decl=True)
            h = _body_hash(body)
            hash_to_a.setdefault(h, []).append((sym, key))

        for sym_b_item, key_b in only_b:
            body = _normalize_body(content_b, sym_b_item.line, sym_b_item.end_line, skip_decl=True)
            h = _body_hash(body)
            if h in hash_to_a and hash_to_a[h]:
                sym_a_item, key_a = hash_to_a[h].pop(0)
                if sym_a_item.kind == sym_b_item.kind:
                    entries.append(DiffEntry(
                        name=sym_b_item.name,
                        kind=sym_b_item.kind,
                        file=sym_b_item.file,
                        status="renamed",
                        old_name=sym_a_item.name,
                        line=sym_b_item.line,
                    ))
                    renamed_a.add(key_a)
                    renamed_b.add(key_b)

    # Add remaining removed (not renamed)
    for sym, key in only_a:
        if key not in renamed_a:
            entries.append(DiffEntry(
                name=sym.name,
                kind=sym.kind,
                file=sym.file,
                status="removed",
                line=sym.line,
            ))

    # Add remaining added (not renamed)
    for sym, key in only_b:
        if key not in renamed_b:
            entries.append(DiffEntry(
                name=sym.name,
                kind=sym.kind,
                file=sym.file,
                status="added",
                line=sym.line,
            ))

    return entries


def diff_entities(repo_path: str, ref_a: str, ref_b: str) -> DiffResult:
    """Compute entity-level diff between two git refs.

    Args:
        repo_path: Path to the git repository.
        ref_a: Base ref (commit, branch, tag).
        ref_b: Target ref (commit, branch, tag).

    Returns:
        DiffResult with all entity-level changes.
    """
    repo = str(Path(repo_path).resolve())
    changed_files = _get_changed_files(repo, ref_a, ref_b)

    all_entries: list[DiffEntry] = []

    for file_path in changed_files:
        lang = detect_language(file_path)
        if lang is None:
            continue

        symbols_a, content_a = _extract_file_symbols(repo, ref_a, file_path)
        symbols_b, content_b = _extract_file_symbols(repo, ref_b, file_path)

        file_entries = _match_symbols(symbols_a, symbols_b, content_a, content_b)
        all_entries.extend(file_entries)

    # Sort: by file, then status order, then name
    status_order = {"added": 0, "removed": 1, "modified": 2, "renamed": 3}
    all_entries.sort(key=lambda e: (e.file, status_order.get(e.status, 9), e.name))

    return DiffResult(ref_a=ref_a, ref_b=ref_b, entries=all_entries)


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------


def render_diff_table(result: DiffResult) -> str:
    """Render diff result as an ASCII table."""
    if not result.entries:
        return f"No entity-level changes between {result.ref_a} and {result.ref_b}."

    lines: list[str] = []
    lines.append(f"Entity diff: {result.ref_a} → {result.ref_b}")
    lines.append("")

    # Column widths
    headers = ["Status", "Kind", "Name", "File", "Detail"]
    rows: list[list[str]] = []
    for e in result.entries:
        detail = ""
        if e.change_type:
            detail = e.change_type
        elif e.old_name:
            detail = f"was: {e.old_name}"
        rows.append([e.status, e.kind, e.name, e.file, detail])

    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def _fmt_row(cells: list[str]) -> str:
        return "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells))

    lines.append(_fmt_row(headers))
    lines.append("  ".join("-" * w for w in widths))
    for row in rows:
        lines.append(_fmt_row(row))

    lines.append("")
    s = result.summary
    lines.append(
        f"Summary: {s['added']} added, {s['removed']} removed, "
        f"{s['modified']} modified, {s['renamed']} renamed"
    )

    return "\n".join(lines)


def render_diff_json(result: DiffResult) -> str:
    """Render diff result as JSON."""
    data = {
        "ref_a": result.ref_a,
        "ref_b": result.ref_b,
        "summary": result.summary,
        "entries": [asdict(e) for e in result.entries],
    }
    return json.dumps(data, indent=2)


def render_diff_markdown(result: DiffResult) -> str:
    """Render diff result as Markdown."""
    if not result.entries:
        return f"No entity-level changes between `{result.ref_a}` and `{result.ref_b}`."

    lines: list[str] = []
    lines.append(f"# Entity Diff: `{result.ref_a}` → `{result.ref_b}`")
    lines.append("")

    s = result.summary
    lines.append(
        f"**{s['added']}** added, **{s['removed']}** removed, "
        f"**{s['modified']}** modified, **{s['renamed']}** renamed"
    )
    lines.append("")

    lines.append("| Status | Kind | Name | File | Detail |")
    lines.append("|--------|------|------|------|--------|")
    for e in result.entries:
        detail = ""
        if e.change_type:
            detail = e.change_type
        elif e.old_name:
            detail = f"was: `{e.old_name}`"
        lines.append(f"| {e.status} | {e.kind} | `{e.name}` | `{e.file}` | {detail} |")

    return "\n".join(lines)
