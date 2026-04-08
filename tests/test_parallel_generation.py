"""
tests/test_parallel_generation.py — Integration tests for parallel chapter generation.

Validates that:
  - parallel (max_workers=4) produces the same output as sequential (max_workers=1)
  - partial failures (one chapter LLM error) don't break other chapters
"""

import subprocess
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from repoforge.docs_generator import generate_docs

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def python_repo(tmp_path):
    """Minimal Python repo with git init — enough for the full pipeline."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "parallel-test"\nversion = "0.1.0"\n'
    )
    (tmp_path / "README.md").write_text("# Parallel Test\n\nA test project.\n")
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.py").write_text(
        '"""Entry point."""\ndef main():\n    print("hello")\n'
    )
    (src / "utils.py").write_text(
        '"""Utils."""\ndef helper(x: int) -> int:\n    return x + 1\n'
    )
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t.com"], cwd=tmp_path, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.name", "T"], cwd=tmp_path, capture_output=True
    )
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True)
    return tmp_path


def _deterministic_content(user_prompt: str, **kw) -> str:
    """Return deterministic markdown keyed on the user prompt prefix."""
    tag = user_prompt[:80].replace("\n", " ").strip()
    return f"# Chapter\n\nDeterministic content for: {tag}\n"


# ---------------------------------------------------------------------------
# 4.3 — Parallel vs sequential: same output
# ---------------------------------------------------------------------------


class TestParallelVsSequential:
    """Parallel (max_workers=4) must produce identical chapters as sequential (max_workers=1)."""

    @patch("repoforge.docs_generator.build_llm")
    def test_same_chapters_generated(self, mock_build_llm, python_repo):
        """Chapter files produced by parallel and sequential runs must match."""
        mock_llm = MagicMock()
        mock_llm.model = "test-model"
        mock_llm.complete.side_effect = _deterministic_content
        mock_build_llm.return_value = mock_llm

        seq_dir = python_repo / "docs_seq"
        par_dir = python_repo / "docs_par"

        result_seq = generate_docs(
            working_dir=str(python_repo),
            output_dir=str(seq_dir),
            verbose=False,
            no_verify_docs=True,
            max_workers=1,
        )
        result_par = generate_docs(
            working_dir=str(python_repo),
            output_dir=str(par_dir),
            verbose=False,
            no_verify_docs=True,
            max_workers=4,
        )

        # Same set of chapters generated (compare by filename, not full path)
        seq_names = sorted(Path(p).name for p in result_seq["chapters_generated"])
        par_names = sorted(Path(p).name for p in result_par["chapters_generated"])
        assert seq_names == par_names, (
            f"Chapter lists differ:\n  seq={seq_names}\n  par={par_names}"
        )

        # Same file contents
        for name in seq_names:
            seq_file = seq_dir / name
            par_file = par_dir / name
            assert seq_file.exists(), f"Missing in sequential: {name}"
            assert par_file.exists(), f"Missing in parallel: {name}"
            assert seq_file.read_text() == par_file.read_text(), (
                f"Content mismatch for {name}"
            )

    @patch("repoforge.docs_generator.build_llm")
    def test_no_errors_in_either_mode(self, mock_build_llm, python_repo):
        """Neither parallel nor sequential should produce errors with a healthy LLM."""
        mock_llm = MagicMock()
        mock_llm.model = "test-model"
        mock_llm.complete.return_value = "# Chapter\n\nContent.\n"
        mock_build_llm.return_value = mock_llm

        result_seq = generate_docs(
            working_dir=str(python_repo),
            output_dir=str(python_repo / "docs_s"),
            verbose=False,
            no_verify_docs=True,
            max_workers=1,
        )
        result_par = generate_docs(
            working_dir=str(python_repo),
            output_dir=str(python_repo / "docs_p"),
            verbose=False,
            no_verify_docs=True,
            max_workers=4,
        )

        assert result_seq["errors"] == [], f"Sequential errors: {result_seq['errors']}"
        assert result_par["errors"] == [], f"Parallel errors: {result_par['errors']}"


# ---------------------------------------------------------------------------
# 4.4 — Partial failure: one chapter fails, others succeed
# ---------------------------------------------------------------------------


class TestPartialFailure:
    """When one chapter's LLM call raises, the rest must still be generated."""

    @patch("repoforge.docs_generator.build_llm")
    def test_other_chapters_still_generated(self, mock_build_llm, python_repo):
        """If one chapter fails, the remaining chapters must still appear on disk."""
        call_count = 0
        lock = threading.Lock()

        def _sometimes_fail(user_prompt, **kw):
            nonlocal call_count
            with lock:
                call_count += 1
                current = call_count
            # Fail on the second LLM call
            if current == 2:
                raise RuntimeError("Simulated LLM timeout")
            return "# OK\n\nContent.\n"

        mock_llm = MagicMock()
        mock_llm.model = "test-model"
        mock_llm.complete.side_effect = _sometimes_fail
        mock_build_llm.return_value = mock_llm

        docs_dir = python_repo / "docs_partial"
        result = generate_docs(
            working_dir=str(python_repo),
            output_dir=str(docs_dir),
            verbose=False,
            no_verify_docs=True,
            max_workers=2,
        )

        # At least one error captured
        assert len(result["errors"]) >= 1, "Expected at least one error"
        assert any(
            "Simulated LLM timeout" in e["error"] for e in result["errors"]
        ), f"Expected 'Simulated LLM timeout' in errors: {result['errors']}"

        # Other chapters were still generated
        assert len(result["chapters_generated"]) >= 1, (
            "Expected at least one chapter to succeed despite the failure"
        )

        # Verify successful chapters exist on disk
        for rel_path in result["chapters_generated"]:
            full = docs_dir / Path(rel_path).name
            assert full.exists(), f"Generated chapter missing on disk: {rel_path}"

    @patch("repoforge.docs_generator.build_llm")
    def test_error_contains_chapter_file(self, mock_build_llm, python_repo):
        """Error entries must identify which chapter file failed."""
        mock_llm = MagicMock()
        mock_llm.model = "test-model"
        # Fail every call
        mock_llm.complete.side_effect = ValueError("total failure")
        mock_build_llm.return_value = mock_llm

        result = generate_docs(
            working_dir=str(python_repo),
            output_dir=str(python_repo / "docs_fail"),
            verbose=False,
            no_verify_docs=True,
            max_workers=4,
        )

        assert len(result["errors"]) > 0
        for err in result["errors"]:
            assert "file" in err, f"Error missing 'file' key: {err}"
            assert err["file"].endswith(".md"), f"Error file not .md: {err['file']}"
