"""Pure-stdlib guard validating ``tests/intelligence_tests.txt`` classification.

This test governs the pre-collection CI partition (S1). It does NOT import any
``repoforge`` module and does NOT require ``tree_sitter``/``.[intelligence]``,
so it runs in the lean ``test-core`` job.

RED state (before the manifest is checked in): ``tests/intelligence_tests.txt``
is absent, so every test here fails.

GREEN state:
  * the manifest exists and lists every intelligence test path,
  * every listed path exists on disk,
  * the manifest set equals the set of test files that *directly* import
    ``repoforge.intelligence`` or ``tree_sitter`` (classification drift -> red).

The guard deliberately covers ONLY direct test-file imports. Transitive
*production* imports of ``repoforge.intelligence`` (e.g. ``repoforge.analysis``
or ``repoforge.graph_context``, which import ``intelligence`` lazily) remain
allowed and are intentionally out of scope for this guard.
"""

import ast
import pathlib

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = REPO_ROOT / "tests" / "intelligence_tests.txt"


def _directly_imports_intelligence(path: pathlib.Path) -> bool:
    """Return True if *path* directly imports repoforge.intelligence or tree_sitter.

    Only module-level ``import`` / ``from ... import`` statements are inspected,
    so lazy/guarded imports inside functions are NOT counted (they are fine for
    the lean core job).
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if (
                    alias.name == "tree_sitter"
                    or alias.name.startswith("repoforge.intelligence")
                ):
                    return True
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod == "tree_sitter" or mod.startswith("repoforge.intelligence"):
                return True
    return False


def _discover_direct_importers() -> set[str]:
    importers: set[str] = set()
    for p in sorted((REPO_ROOT / "tests").rglob("test_*.py")):
        if _directly_imports_intelligence(p):
            importers.add(str(p.relative_to(REPO_ROOT)))
    return importers


def _load_manifest():
    if not MANIFEST.exists():
        return None
    entries = []
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        entries.append(line)
    return entries


def test_manifest_exists():
    assert MANIFEST.exists(), "tests/intelligence_tests.txt must be checked in (S1 partition)"


def test_manifest_lists_paths():
    entries = _load_manifest()
    assert entries is not None and entries, "manifest must list intelligence test paths"


def test_manifest_paths_exist():
    entries = _load_manifest()
    assert entries is not None
    missing = [e for e in entries if not (REPO_ROOT / e).exists()]
    assert not missing, f"manifest lists non-existent paths: {missing}"


def test_manifest_classification_matches_source():
    entries = _load_manifest()
    assert entries is not None
    manifest_set = set(entries)
    source_set = _discover_direct_importers()

    missing_from_manifest = source_set - manifest_set
    extra_in_manifest = manifest_set - source_set

    assert not missing_from_manifest, (
        "test files that directly import repoforge.intelligence/tree_sitter are "
        f"missing from the manifest: {sorted(missing_from_manifest)}"
    )
    assert not extra_in_manifest, (
        "manifest lists files that do NOT directly import "
        f"repoforge.intelligence/tree_sitter: {sorted(extra_in_manifest)}"
    )
