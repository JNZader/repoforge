"""Snapshot integration tests: YAML templates produce equivalent chapter lists.

For each of the 10 project types, constructs a mock RepoMap that triggers
that classification, calls ``get_chapter_prompts``, and asserts:
  - The chapter list (file names, titles) matches the expected output
  - YAML templates produce results equivalent to hardcoded ADAPTIVE_CHAPTERS

This ensures the YAML migration is a faithful 1:1 replacement.
"""

from __future__ import annotations

import pytest

from repoforge.docs_prompts.chapters import (
    ADAPTIVE_CHAPTERS,
    UNIVERSAL_CHAPTERS,
    get_chapter_prompts,
)
from repoforge.docs_prompts.classify import classify_project
from repoforge.ir.repo import LayerInfo, ModuleInfo, RepoMap
from repoforge.template_loader import clear_cache

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _fresh_cache():
    """Each test starts with a clean template cache."""
    clear_cache()
    yield
    clear_cache()


# ── Helper to build expected chapter skeleton ─────────────────────────────────


def _expected_files_and_titles(project_type: str) -> list[tuple[str, str]]:
    """Build the expected (file, title) list from UNIVERSAL + ADAPTIVE."""
    index = [(c["file"], c["title"]) for c in UNIVERSAL_CHAPTERS if c["file"] == "index.md"]
    pre = [
        (c["file"], c["title"])
        for c in UNIVERSAL_CHAPTERS
        if c["file"].startswith("0") and c["file"] <= "03-z"
    ]
    adaptive = ADAPTIVE_CHAPTERS.get(project_type, ADAPTIVE_CHAPTERS["generic"])
    mid = [(c["file"], c["title"]) for c in adaptive]
    post = [
        (c["file"], c["title"])
        for c in UNIVERSAL_CHAPTERS
        if c["file"].startswith("0") and c["file"] >= "07-"
    ]
    return index + pre + mid + post


# ── Mock RepoMaps per project type ────────────────────────────────────────────
# Each RepoMap is designed to trigger exactly one classification branch in
# classify_project(). Signals are the MINIMUM needed.


def _make_repo_map(**overrides) -> RepoMap:
    defaults = dict(
        root="/tmp/test",
        tech_stack=[],
        layers={},
        entry_points=[],
        config_files=[],
        repoforge_config={},
        stats={"total_files": 10},
    )
    defaults.update(overrides)
    return RepoMap(**defaults)


# --- web_service ---
def _web_service_map() -> RepoMap:
    return _make_repo_map(
        tech_stack=["python", "flask"],
        layers={
            "core": LayerInfo(
                path="core",
                modules=[
                    ModuleInfo(path="core/server.py", name="server.py", language="python"),
                    ModuleInfo(path="core/handler.py", name="handler.py", language="python"),
                ],
            ),
        },
        entry_points=["main.py"],
    )


# --- cli_tool ---
def _cli_tool_map() -> RepoMap:
    return _make_repo_map(
        tech_stack=["python", "click"],
        layers={
            "cli": LayerInfo(
                path="cli",
                modules=[
                    ModuleInfo(path="cli/main.py", name="main.py", language="python"),
                ],
            ),
        },
        entry_points=["cli/main.py"],
        stats={"total_files": 5},
    )


# --- library_sdk ---
def _library_sdk_map() -> RepoMap:
    return _make_repo_map(
        tech_stack=["python"],
        layers={
            "lib": LayerInfo(
                path="lib",
                modules=[
                    ModuleInfo(path="lib/core.py", name="core.py", language="python"),
                    ModuleInfo(path="lib/utils.py", name="utils.py", language="python"),
                ],
            ),
        },
        entry_points=[],
        stats={"total_files": 8},
    )


# --- data_science ---
def _data_science_map() -> RepoMap:
    return _make_repo_map(
        tech_stack=["python", "pytorch", "pandas"],
        layers={
            "ml": LayerInfo(
                path="ml",
                modules=[
                    ModuleInfo(path="ml/train.py", name="train.py", language="python"),
                    ModuleInfo(path="ml/model.py", name="model.py", language="python"),
                ],
            ),
        },
    )


# --- frontend_app ---
def _frontend_app_map() -> RepoMap:
    return _make_repo_map(
        tech_stack=["react", "typescript"],
        layers={
            "src": LayerInfo(
                path="src",
                modules=[
                    ModuleInfo(path="src/App.tsx", name="App.tsx", language="typescript"),
                    ModuleInfo(path="src/routes.tsx", name="routes.tsx", language="typescript"),
                ],
            ),
        },
    )


# --- mobile_app ---
def _mobile_app_map() -> RepoMap:
    return _make_repo_map(
        tech_stack=["react native", "typescript"],
        layers={
            "app": LayerInfo(
                path="app",
                modules=[
                    ModuleInfo(path="app/index.tsx", name="index.tsx", language="typescript"),
                ],
            ),
        },
    )


# --- desktop_app ---
def _desktop_app_map() -> RepoMap:
    return _make_repo_map(
        tech_stack=["typescript"],
        config_files=["package.json", "electron-builder.yml"],
        layers={
            "src": LayerInfo(
                path="src",
                modules=[
                    ModuleInfo(path="src/main.ts", name="main.ts", language="typescript"),
                    ModuleInfo(path="src/electron.ts", name="electron.ts", language="typescript"),
                ],
            ),
        },
    )


# --- infra_devops ---
def _infra_devops_map() -> RepoMap:
    return _make_repo_map(
        tech_stack=["hcl"],
        config_files=["main.tf", "variables.tf"],
        layers={
            "infra": LayerInfo(
                path="infra",
                modules=[
                    ModuleInfo(path="infra/main.tf", name="main.tf", language="hcl"),
                ],
            ),
        },
    )


# --- monorepo ---
def _monorepo_map() -> RepoMap:
    return _make_repo_map(
        tech_stack=["python", "typescript"],
        layers={
            "frontend": LayerInfo(
                path="frontend",
                modules=[
                    ModuleInfo(path="frontend/App.tsx", name="App.tsx", language="typescript"),
                ],
            ),
            "backend": LayerInfo(
                path="backend",
                modules=[
                    ModuleInfo(path="backend/server.py", name="server.py", language="python"),
                ],
            ),
        },
    )


# --- generic ---
def _generic_map() -> RepoMap:
    # Generic = no strong signals for any specific type.
    # - No web/cli/frontend/mobile/desktop/infra/ds signals in tech_stack
    # - Entry points that DON'T match web triggers ("main", "app", "server", "index")
    # - Enough files to avoid library_sdk (which triggers when total_files < 30 + no entries)
    return _make_repo_map(
        tech_stack=["c"],
        layers={
            "src": LayerInfo(
                path="src",
                modules=[
                    ModuleInfo(path="src/foo.c", name="foo.c", language="c"),
                    ModuleInfo(path="src/bar.c", name="bar.c", language="c"),
                ] + [
                    ModuleInfo(path=f"src/mod{i}.c", name=f"mod{i}.c", language="c")
                    for i in range(40)
                ],
            ),
        },
        entry_points=[],
        stats={"total_files": 42},
    )


# ── Mapping: project_type -> factory ──────────────────────────────────────────

PROJECT_TYPE_FACTORIES: dict[str, callable] = {
    "web_service": _web_service_map,
    "cli_tool": _cli_tool_map,
    "library_sdk": _library_sdk_map,
    "data_science": _data_science_map,
    "frontend_app": _frontend_app_map,
    "mobile_app": _mobile_app_map,
    "desktop_app": _desktop_app_map,
    "infra_devops": _infra_devops_map,
    "monorepo": _monorepo_map,
    "generic": _generic_map,
}


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestClassificationPreconditions:
    """Verify each mock RepoMap classifies to the intended project type."""

    @pytest.mark.parametrize("project_type", sorted(PROJECT_TYPE_FACTORIES))
    def test_mock_classifies_correctly(self, project_type: str):
        repo_map = PROJECT_TYPE_FACTORIES[project_type]()
        actual = classify_project(repo_map)
        assert actual == project_type, (
            f"Expected RepoMap to classify as '{project_type}', "
            f"got '{actual}'. Fix the mock signals."
        )


class TestYAMLTemplateSnapshots:
    """Snapshot tests: YAML templates produce the same chapter list as hardcoded data."""

    @pytest.mark.parametrize("project_type", sorted(PROJECT_TYPE_FACTORIES))
    def test_chapter_files_match(self, project_type: str):
        """Chapter file names from get_chapter_prompts match the expected list."""
        repo_map = PROJECT_TYPE_FACTORIES[project_type]()
        chapters = get_chapter_prompts(repo_map, "en", "TestProject")

        actual_files = [ch["file"] for ch in chapters]
        expected_files = [ft[0] for ft in _expected_files_and_titles(project_type)]

        assert actual_files == expected_files, (
            f"Chapter files mismatch for '{project_type}'.\n"
            f"Expected: {expected_files}\n"
            f"Actual:   {actual_files}"
        )

    @pytest.mark.parametrize("project_type", sorted(PROJECT_TYPE_FACTORIES))
    def test_chapter_titles_match(self, project_type: str):
        """Chapter titles from get_chapter_prompts match the expected list."""
        repo_map = PROJECT_TYPE_FACTORIES[project_type]()
        chapters = get_chapter_prompts(repo_map, "en", "TestProject")

        actual_titles = [ch["title"] for ch in chapters]
        expected_titles = [ft[1] for ft in _expected_files_and_titles(project_type)]

        assert actual_titles == expected_titles, (
            f"Chapter titles mismatch for '{project_type}'.\n"
            f"Expected: {expected_titles}\n"
            f"Actual:   {actual_titles}"
        )

    @pytest.mark.parametrize("project_type", sorted(PROJECT_TYPE_FACTORIES))
    def test_all_chapters_have_prompts(self, project_type: str):
        """Every chapter must have non-empty system and user prompts."""
        repo_map = PROJECT_TYPE_FACTORIES[project_type]()
        chapters = get_chapter_prompts(repo_map, "en", "TestProject")

        for ch in chapters:
            assert ch["system"], f"Empty system prompt for {ch['file']} ({project_type})"
            assert ch["user"], f"Empty user prompt for {ch['file']} ({project_type})"

    @pytest.mark.parametrize("project_type", sorted(PROJECT_TYPE_FACTORIES))
    def test_project_type_is_set(self, project_type: str):
        """Each chapter dict must include the correct project_type."""
        repo_map = PROJECT_TYPE_FACTORIES[project_type]()
        chapters = get_chapter_prompts(repo_map, "en", "TestProject")

        for ch in chapters:
            assert ch["project_type"] == project_type, (
                f"Chapter {ch['file']} has project_type='{ch['project_type']}', "
                f"expected '{project_type}'"
            )

    @pytest.mark.parametrize("project_type", sorted(PROJECT_TYPE_FACTORIES))
    def test_chapter_count_matches(self, project_type: str):
        """Total chapter count = universal + adaptive for that type."""
        repo_map = PROJECT_TYPE_FACTORIES[project_type]()
        chapters = get_chapter_prompts(repo_map, "en", "TestProject")

        expected = _expected_files_and_titles(project_type)
        assert len(chapters) == len(expected), (
            f"Chapter count mismatch for '{project_type}': "
            f"got {len(chapters)}, expected {len(expected)}"
        )


class TestUniversalChaptersPresent:
    """Verify that ALL project types include the universal chapters."""

    UNIVERSAL_FILES = {c["file"] for c in UNIVERSAL_CHAPTERS}

    @pytest.mark.parametrize("project_type", sorted(PROJECT_TYPE_FACTORIES))
    def test_universal_chapters_included(self, project_type: str):
        repo_map = PROJECT_TYPE_FACTORIES[project_type]()
        chapters = get_chapter_prompts(repo_map, "en", "TestProject")

        actual_files = {ch["file"] for ch in chapters}
        missing = self.UNIVERSAL_FILES - actual_files
        assert not missing, (
            f"Missing universal chapters for '{project_type}': {missing}"
        )


class TestChapterOrdering:
    """Verify chapters are in the correct order: index -> 01-03 -> adaptive -> 07."""

    @pytest.mark.parametrize("project_type", sorted(PROJECT_TYPE_FACTORIES))
    def test_ordering(self, project_type: str):
        repo_map = PROJECT_TYPE_FACTORIES[project_type]()
        chapters = get_chapter_prompts(repo_map, "en", "TestProject")
        files = [ch["file"] for ch in chapters]

        # index.md must be first
        assert files[0] == "index.md", f"First chapter should be index.md, got {files[0]}"

        # 07-dev-guide.md must be last
        assert files[-1] == "07-dev-guide.md", (
            f"Last chapter should be 07-dev-guide.md, got {files[-1]}"
        )

        # 01, 02, 03 must come before adaptive chapters
        pre_files = ["01-overview.md", "02-quickstart.md", "03-architecture.md"]
        for pf in pre_files:
            assert pf in files, f"{pf} missing from chapter list"
            assert files.index(pf) < files.index("07-dev-guide.md")
