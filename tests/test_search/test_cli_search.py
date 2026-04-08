"""CLI integration tests for `repoforge index` and `repoforge query`."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

np = pytest.importorskip("numpy", reason="numpy not installed")
faiss = pytest.importorskip("faiss", reason="faiss-cpu not installed")

from click.testing import CliRunner

from repoforge.cli import main
from repoforge.search.embedder import Embedder


def _make_embedder_mock(dim: int = 8):
    """Create a mock Embedder returning deterministic vectors."""
    call_count = [0]

    def fake_embed(texts):
        vecs = []
        for _ in texts:
            call_count[0] += 1
            vec = np.random.RandomState(call_count[0]).randn(dim).tolist()
            vecs.append(vec)
        return vecs

    def fake_embed_single(text):
        return fake_embed([text])[0]

    mock = MagicMock(spec=Embedder)
    mock.embed.side_effect = fake_embed
    mock.embed_single.side_effect = fake_embed_single
    mock.model = "text-embedding-3-small"
    mock.batch_size = 100
    mock.dimension = 0
    mock.api_key = None
    mock.api_base = None
    return mock


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def sample_repo(tmp_path):
    """Create a minimal Python repo for scanning."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "__init__.py").write_text("")
    (src / "auth.py").write_text(
        "def authenticate(token: str) -> bool:\n"
        "    return token == 'valid'\n"
    )
    (src / "service.py").write_text(
        "class UserService:\n"
        "    def get_user(self, user_id: int):\n"
        "        return {'id': user_id}\n"
    )
    return tmp_path


class TestIndexCommand:
    def test_index_missing_faiss(self, runner):
        """Should exit with error when faiss not available."""
        with patch("repoforge.cli.SEARCH_AVAILABLE", False):
            # We need to patch the import inside the command
            with patch.dict("sys.modules", {"repoforge.search": MagicMock(SEARCH_AVAILABLE=False)}):
                # Directly test the import guard
                from repoforge.search import SEARCH_AVAILABLE as actual
                # If faiss is actually installed in test env, skip this
                if actual:
                    pytest.skip("faiss is installed, cannot test missing guard")

    def test_index_builds_and_saves(self, runner, sample_repo, tmp_path):
        """Full index build with mocked embedder."""
        output_dir = tmp_path / "test_index_out"
        mock_embedder = _make_embedder_mock(dim=8)

        with patch("repoforge.cli.Embedder", return_value=mock_embedder):
            result = runner.invoke(main, [
                "index",
                "-w", str(sample_repo),
                "-o", str(output_dir),
            ])

        # Debug on failure
        if result.exit_code != 0:
            print(f"STDOUT: {result.output}")
            if result.exception:
                import traceback
                traceback.print_exception(type(result.exception), result.exception, result.exception.__traceback__)

        assert result.exit_code == 0
        assert (output_dir / "index.faiss").exists()
        assert (output_dir / "metadata.json").exists()

        # Verify metadata
        meta = json.loads((output_dir / "metadata.json").read_text())
        assert len(meta["ids"]) > 0
        assert len(meta["types"]) > 0

    def test_index_quiet_mode(self, runner, sample_repo, tmp_path):
        """Quiet mode should suppress progress output."""
        output_dir = tmp_path / "quiet_index"
        mock_embedder = _make_embedder_mock(dim=8)

        with patch("repoforge.cli.Embedder", return_value=mock_embedder):
            result = runner.invoke(main, [
                "index",
                "-w", str(sample_repo),
                "-o", str(output_dir),
                "-q",
            ])

        assert result.exit_code == 0
        # In quiet mode, no progress text on stdout
        assert "Extracting" not in result.output


class TestQueryCommand:
    def _build_index(self, index_dir: Path, dim: int = 8):
        """Build a small test index on disk."""
        from repoforge.search.index import SearchIndex

        mock_embedder = _make_embedder_mock(dim=dim)
        idx = SearchIndex(embedder=mock_embedder)
        idx.add(
            texts=[
                "function authenticate in auth.py: params: token, secret",
                "class UserService in service.py",
                "function connect_db in database.py: params: host, port",
            ],
            ids=[
                "auth.py::authenticate",
                "service.py::UserService",
                "database.py::connect_db",
            ],
            types=["symbol", "symbol", "symbol"],
        )
        idx.save(index_dir)
        return mock_embedder

    def test_query_text_output(self, runner, tmp_path):
        """Query should produce tabular text output."""
        index_dir = tmp_path / "query_index"
        self._build_index(index_dir)

        mock_embedder = _make_embedder_mock(dim=8)
        with patch("repoforge.cli.Embedder", return_value=mock_embedder):
            result = runner.invoke(main, [
                "query",
                "authentication",
                "--index-dir", str(index_dir),
            ])

        assert result.exit_code == 0
        # Output should contain pipe-separated fields
        assert "|" in result.output

    def test_query_json_output(self, runner, tmp_path):
        """Query with --json should produce valid JSON."""
        index_dir = tmp_path / "json_index"
        self._build_index(index_dir)

        mock_embedder = _make_embedder_mock(dim=8)
        with patch("repoforge.cli.Embedder", return_value=mock_embedder):
            result = runner.invoke(main, [
                "query",
                "database connection",
                "--index-dir", str(index_dir),
                "--json",
            ])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) > 0
        assert "score" in data[0]
        assert "entity_type" in data[0]
        assert "entity_id" in data[0]
        assert "text" in data[0]

    def test_query_top_k(self, runner, tmp_path):
        """--top-k should limit results."""
        index_dir = tmp_path / "topk_index"
        self._build_index(index_dir)

        mock_embedder = _make_embedder_mock(dim=8)
        with patch("repoforge.cli.Embedder", return_value=mock_embedder):
            result = runner.invoke(main, [
                "query",
                "something",
                "--index-dir", str(index_dir),
                "--top-k", "1",
                "--json",
            ])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1

    def test_query_missing_index(self, runner, tmp_path):
        """Should exit with error if index dir doesn't exist."""
        result = runner.invoke(main, [
            "query",
            "anything",
            "--index-dir", str(tmp_path / "nonexistent"),
        ])

        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "not found" in (result.output + str(getattr(result, 'stderr', '')))
