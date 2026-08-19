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


TRANSITIVE_MARKER = "TRANSITIVE:"


def _parse_manifest_annotated():
    """Return [(path, annotation)] rows, or None if the manifest is absent.

    Inline ``# TRANSITIVE: ...`` annotations are preserved for review and for the
    reachability guard, but never reach pytest as path arguments.
    """
    if not MANIFEST.exists():
        return None
    rows = []
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        path, _, annotation = raw.partition("#")
        rows.append((path.strip(), annotation.strip()))
    return rows


def _import_targets(file_path):
    """Yield absolute module names imported by *file_path* (resolves relative)."""
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
    except (SyntaxError, OSError, UnicodeDecodeError):
        return
    pkg = list(file_path.resolve().relative_to(REPO_ROOT).parts[:-1])
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if node.level:
                base = pkg[: len(pkg) - (node.level - 1)] if node.level > 1 else pkg
                mod = ".".join((base + mod.split(".")) if mod else list(base))
            if mod:
                yield mod


def _transitive_reaches_intelligence(start):
    """BFS the import graph from *start*; True if it reaches tree_sitter or
    repoforge.intelligence (directly or transitively). Bounded by a visited set.
    """
    seen: set[str] = set()
    stack = [start]
    while stack:
        cur = stack.pop()
        if str(cur) in seen:
            continue
        seen.add(str(cur))
        for mod in _import_targets(cur):
            if mod == "tree_sitter" or mod.startswith("repoforge.intelligence"):
                return True
            if mod.startswith("repoforge."):
                f = REPO_ROOT.joinpath(*mod.split("."))
                f = f.with_suffix(".py") if f.with_suffix(".py").exists() else (
                    f / "__init__.py" if (f / "__init__.py").exists() else None
                )
                if f:
                    stack.append(f)
    return False


def _validate_classification(rows, source_set):
    """Return (missing_from_manifest, stale_extra, documented_transitive)."""
    manifest_set = {p for p, _ in rows}
    missing = source_set - manifest_set
    documented = {p for p, ann in rows if TRANSITIVE_MARKER in (ann or "")}
    extra = manifest_set - source_set - documented
    return missing, extra, documented


def _manifest_ignore_args():
    rows = _parse_manifest_annotated()
    if rows is None:
        return None
    return [f"--ignore={path}" for path, _ in rows]


def _load_manifest():
    if not MANIFEST.exists():
        return None
    entries = []
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        line = line.split("#", 1)[0].strip()  # drop inline TRANSITIVE annotation
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
    rows = _parse_manifest_annotated()
    assert rows is not None
    source_set = _discover_direct_importers()
    missing, extra, _ = _validate_classification(rows, source_set)

    assert not missing, (
        "test files that directly import repoforge.intelligence/tree_sitter are "
        f"missing from the manifest: {sorted(missing)}"
    )
    assert not extra, (
        "manifest lists files that are neither direct importers nor documented "
        f"transitive members: {sorted(extra)}"
    )

    # Every documented transitive member must REALLY reach the optional dep,
    # otherwise the guard is silently weakened by the transitive exception.
    for p, ann in rows:
        if TRANSITIVE_MARKER not in (ann or ""):
            continue
        assert _transitive_reaches_intelligence(REPO_ROOT / p), (
            f"documented transitive member {p} does not actually reach "
            f"repoforge.intelligence/tree_sitter: annotation={ann!r}"
        )


def test_manifest_has_no_duplicates():
    entries = _load_manifest()
    assert entries is not None
    dupes = {e for e in entries if entries.count(e) > 1}
    assert not dupes, f"manifest contains duplicate paths: {sorted(dupes)}"


def test_transitive_member_documented_and_verified():
    rows = _parse_manifest_annotated()
    assert rows is not None
    annotated = {p: ann for p, ann in rows if TRANSITIVE_MARKER in (ann or "")}
    assert "tests/test_symbols/test_extractor.py" in annotated, (
        "tests/test_symbols/test_extractor.py must be documented as a TRANSITIVE "
        "manifest member (it reaches tree-sitter via repoforge.symbols.extractor)"
    )
    ann = annotated["tests/test_symbols/test_extractor.py"]
    assert "repoforge.intelligence" in ann or "tree_sitter" in ann, (
        f"transitive annotation must name the optional dependency: {ann!r}"
    )
    assert _transitive_reaches_intelligence(
        REPO_ROOT / "tests/test_symbols/test_extractor.py"
    ), "test_extractor.py must transitively reach repoforge.intelligence/tree_sitter"


def test_new_transitive_entry_present_exactly_once():
    rows = _parse_manifest_annotated()
    assert rows is not None
    paths = [p for p, _ in rows]
    assert paths.count("tests/test_symbols/test_extractor.py") == 1, (
        "tests/test_symbols/test_extractor.py must appear exactly once in the manifest"
    )


def test_manifest_parser_emits_ignore_args():
    rows = _parse_manifest_annotated()
    assert rows is not None
    ignores = _manifest_ignore_args()
    assert ignores is not None
    direct_importers = _discover_direct_importers()
    documented_transitive = {
        path for path, annotation in rows
        if TRANSITIVE_MARKER in (annotation or "")
    }
    expected_paths = direct_importers | documented_transitive
    manifest_paths = [path for path, _ in rows]

    assert len(direct_importers) == 23
    assert documented_transitive == {"tests/test_symbols/test_extractor.py"}
    assert len(expected_paths) == 24
    assert set(manifest_paths) == expected_paths
    assert len(manifest_paths) == len(set(manifest_paths)) == 24
    assert set(ignores) == {f"--ignore={path}" for path in expected_paths}
    assert len(ignores) == len(set(ignores)) == 24


def test_undocumented_non_direct_entry_is_rejected():
    # A manifest entry that is neither a direct importer nor a documented
    # transitive member must still be flagged as stale — the guard is NOT
    # silently weakened by the transitive exception.
    source_set = _discover_direct_importers()
    rows = [("tests/test_symbols/test_extractor.py", "")]  # no annotation
    _, extra, _ = _validate_classification(rows, source_set)
    assert "tests/test_symbols/test_extractor.py" in extra
