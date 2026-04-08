"""Tests for repoforge.search.types."""

from repoforge.search.types import SearchResult


class TestSearchResult:
    def test_basic_creation(self):
        result = SearchResult(
            entity_id="src/auth.py::authenticate",
            entity_type="symbol",
            text="function authenticate in src/auth.py",
            score=0.95,
        )
        assert result.entity_id == "src/auth.py::authenticate"
        assert result.entity_type == "symbol"
        assert result.score == 0.95
        assert result.metadata == {}

    def test_with_metadata(self):
        result = SearchResult(
            entity_id="src/auth.py",
            entity_type="module",
            text="module auth",
            score=0.8,
            metadata={"language": "python", "line": 42},
        )
        assert result.metadata["language"] == "python"
        assert result.metadata["line"] == 42

    def test_frozen(self):
        result = SearchResult(
            entity_id="x", entity_type="symbol", text="t", score=0.5,
        )
        try:
            result.score = 1.0  # type: ignore[misc]
            assert False, "Should have raised FrozenInstanceError"
        except AttributeError:
            pass
