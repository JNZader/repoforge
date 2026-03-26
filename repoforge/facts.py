"""
facts.py - Public API for semantic fact extraction.

Re-exports FactItem, FACT_PATTERNS, and extract_facts from ripgrep.py
where the rg+fallback implementation lives.

Usage:
    from repoforge.facts import extract_facts, FactItem
    facts = extract_facts(root_dir, file_paths)
"""

from pathlib import Path

from .ripgrep import (
    FactItem,
    FACT_PATTERNS,
    extract_facts as _extract_facts_raw,
)

__all__ = ["FactItem", "FACT_PATTERNS", "extract_facts"]


def extract_facts(
    root_dir: str,
    file_paths: list[str],
) -> list[FactItem]:
    """Extract semantic facts from source files under root_dir.

    Convenience wrapper that accepts string paths (as returned by
    scanners and graph builders) and delegates to ripgrep.extract_facts.

    Args:
        root_dir: Absolute path to the project root.
        file_paths: List of file paths (absolute or relative to root_dir).

    Returns:
        Sorted, deduplicated list of FactItem.
    """
    root = Path(root_dir).resolve()
    resolved: list[Path] = []
    for fp in file_paths:
        p = Path(fp)
        if not p.is_absolute():
            p = root / p
        p = p.resolve()
        if p.is_file():
            resolved.append(p)
    return _extract_facts_raw(resolved, root)
