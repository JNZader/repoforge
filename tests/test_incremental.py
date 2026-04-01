"""Tests for repoforge.incremental — manifest, diff, and staleness logic."""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from repoforge.incremental import (
    MANIFEST_FILENAME,
    ChapterEntry,
    Manifest,
    build_chapter_deps,
    content_hash,
    get_changed_files,
    get_stale_chapters,
    load_manifest,
    now_iso,
    save_manifest,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_out(tmp_path: Path) -> Path:
    """Return a temporary output directory."""
    return tmp_path / "docs"


@pytest.fixture
def sample_manifest() -> Manifest:
    return Manifest(
        git_sha="abc123",
        generated_at="2026-03-31T12:00:00+00:00",
        chapters={
            "01-overview.md": ChapterEntry(
                source_files=["src/main.py", "src/util.py"],
                content_hash="deadbeef",
                generated_at="2026-03-31T12:00:00+00:00",
            ),
            "03-architecture.md": ChapterEntry(
                source_files=["src/main.py", "src/util.py", "src/db.py"],
                content_hash="cafebabe",
                generated_at="2026-03-31T12:00:00+00:00",
            ),
        },
    )


@pytest.fixture
def sample_repo_map() -> dict:
    return {
        "layers": {
            "backend": {
                "path": "backend",
                "modules": [
                    {"path": "backend/api.py", "name": "api", "language": "python"},
                    {"path": "backend/models.py", "name": "models", "language": "python"},
                ],
            },
            "frontend": {
                "path": "frontend",
                "modules": [
                    {"path": "frontend/app.tsx", "name": "app", "language": "typescript"},
                ],
            },
        },
    }


@pytest.fixture
def sample_chapters() -> list[dict]:
    return [
        {"file": "index.md", "title": "Home", "description": "Navigation"},
        {"file": "01-overview.md", "title": "Overview", "description": "Tech stack"},
        {"file": "03-architecture.md", "title": "Architecture", "description": "Design"},
        {"file": "04-core-mechanisms.md", "title": "Core Mechanisms", "description": "API endpoints and handlers"},
        {"file": "07-dev-guide.md", "title": "Dev Guide", "description": "Development guide"},
    ]


# ---------------------------------------------------------------------------
# Manifest I/O
# ---------------------------------------------------------------------------


class TestManifestRoundTrip:
    def test_save_and_load(self, tmp_out: Path, sample_manifest: Manifest):
        tmp_out.mkdir(parents=True)
        save_manifest(tmp_out, sample_manifest)

        loaded = load_manifest(tmp_out)
        assert loaded is not None
        assert loaded.git_sha == sample_manifest.git_sha
        assert loaded.generated_at == sample_manifest.generated_at
        assert set(loaded.chapters.keys()) == set(sample_manifest.chapters.keys())

        entry = loaded.chapters["01-overview.md"]
        assert entry.source_files == ["src/main.py", "src/util.py"]
        assert entry.content_hash == "deadbeef"

    def test_load_missing_returns_none(self, tmp_out: Path):
        assert load_manifest(tmp_out) is None

    def test_load_corrupt_returns_none(self, tmp_out: Path):
        tmp_out.mkdir(parents=True)
        (tmp_out / MANIFEST_FILENAME).write_text("NOT JSON!!!", encoding="utf-8")
        assert load_manifest(tmp_out) is None

    def test_load_empty_json_returns_manifest(self, tmp_out: Path):
        tmp_out.mkdir(parents=True)
        (tmp_out / MANIFEST_FILENAME).write_text("{}", encoding="utf-8")
        loaded = load_manifest(tmp_out)
        assert loaded is not None
        assert loaded.git_sha == ""
        assert loaded.chapters == {}

    def test_save_creates_valid_json(self, tmp_out: Path, sample_manifest: Manifest):
        tmp_out.mkdir(parents=True)
        path = save_manifest(tmp_out, sample_manifest)
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        assert "git_sha" in data
        assert "chapters" in data
        assert "01-overview.md" in data["chapters"]


# ---------------------------------------------------------------------------
# Git diff
# ---------------------------------------------------------------------------


class TestGetChangedFiles:
    @patch("repoforge.incremental.subprocess.run")
    def test_returns_changed_files(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="src/main.py\nsrc/new.py\n",
        )
        result = get_changed_files(Path("/repo"), "abc123")
        assert result == ["src/main.py", "src/new.py"]
        mock_run.assert_called_once()

    @patch("repoforge.incremental.subprocess.run")
    def test_returns_empty_on_failure(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(returncode=128, stdout="")
        result = get_changed_files(Path("/repo"), "abc123")
        assert result == []

    def test_returns_empty_for_empty_sha(self):
        result = get_changed_files(Path("/repo"), "")
        assert result == []

    @patch("repoforge.incremental.subprocess.run", side_effect=FileNotFoundError)
    def test_handles_no_git(self, _mock: MagicMock):
        result = get_changed_files(Path("/repo"), "abc123")
        assert result == []


# ---------------------------------------------------------------------------
# Chapter dependency mapping
# ---------------------------------------------------------------------------


class TestBuildChapterDeps:
    def test_global_chapters_include_all_files(
        self, sample_repo_map: dict, sample_chapters: list[dict]
    ):
        deps = build_chapter_deps(sample_repo_map, sample_chapters)
        all_files = ["backend/api.py", "backend/models.py", "frontend/app.tsx"]
        # Global chapters should include all files
        for fname in ("index.md", "01-overview.md", "03-architecture.md", "07-dev-guide.md"):
            assert set(deps[fname]) == set(all_files), f"{fname} should depend on all files"

    def test_domain_chapter_matches_layer(
        self, sample_repo_map: dict, sample_chapters: list[dict]
    ):
        deps = build_chapter_deps(sample_repo_map, sample_chapters)
        # "Core Mechanisms" with "API endpoints and handlers" should match backend
        core_deps = deps["04-core-mechanisms.md"]
        assert "backend/api.py" in core_deps

    def test_empty_layers(self, sample_chapters: list[dict]):
        repo_map = {"layers": {}}
        deps = build_chapter_deps(repo_map, sample_chapters)
        # All chapters should have empty deps
        for fname in deps:
            assert deps[fname] == []


# ---------------------------------------------------------------------------
# Staleness detection
# ---------------------------------------------------------------------------


class TestGetStaleChapters:
    def test_all_stale_when_no_manifest(self, sample_chapters: list[dict]):
        deps = {"index.md": ["a.py"], "01-overview.md": ["b.py"]}
        stale = get_stale_chapters(sample_chapters, None, ["a.py"], deps)
        assert len(stale) == len(sample_chapters)

    def test_none_stale_when_no_changes(
        self, sample_chapters: list[dict], sample_manifest: Manifest
    ):
        deps = {c["file"]: ["src/main.py"] for c in sample_chapters}
        stale = get_stale_chapters(sample_chapters, sample_manifest, [], deps)
        assert stale == []

    def test_only_affected_chapters_stale(self, sample_manifest: Manifest):
        chapters = [
            {"file": "01-overview.md", "title": "Overview"},
            {"file": "03-architecture.md", "title": "Architecture"},
        ]
        deps = {
            "01-overview.md": ["src/main.py"],
            "03-architecture.md": ["src/db.py"],
        }
        changed = ["src/main.py"]
        stale = get_stale_chapters(chapters, sample_manifest, changed, deps)
        assert len(stale) == 1
        assert stale[0]["file"] == "01-overview.md"

    def test_new_chapter_always_stale(self, sample_manifest: Manifest):
        chapters = [
            {"file": "01-overview.md", "title": "Overview"},
            {"file": "99-new-chapter.md", "title": "New"},
        ]
        deps = {
            "01-overview.md": ["src/main.py"],
            "99-new-chapter.md": ["src/main.py"],
        }
        changed = ["something_unrelated.py"]
        stale = get_stale_chapters(chapters, sample_manifest, changed, deps)
        assert len(stale) == 1
        assert stale[0]["file"] == "99-new-chapter.md"


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


class TestContentHash:
    def test_deterministic(self):
        assert content_hash("hello") == content_hash("hello")

    def test_different_for_different_input(self):
        assert content_hash("a") != content_hash("b")

    def test_is_hex(self):
        h = content_hash("test")
        assert len(h) == 64
        int(h, 16)  # Should not raise


class TestNowIso:
    def test_returns_string(self):
        ts = now_iso()
        assert isinstance(ts, str)
        assert "T" in ts
