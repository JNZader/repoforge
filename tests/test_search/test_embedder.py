"""Tests for repoforge.search.embedder."""

from unittest.mock import MagicMock, patch

from repoforge.search.embedder import Embedder


class TestEmbedder:
    def _mock_response(self, embeddings: list[list[float]]):
        """Create a mock litellm.embedding() response."""
        response = MagicMock()
        response.data = [{"embedding": emb} for emb in embeddings]
        return response

    @patch("repoforge.search.embedder.litellm.embedding")
    def test_embed_single(self, mock_embedding):
        mock_embedding.return_value = self._mock_response([[0.1, 0.2, 0.3]])

        embedder = Embedder(model="text-embedding-3-small")
        result = embedder.embed_single("hello world")

        assert result == [0.1, 0.2, 0.3]
        mock_embedding.assert_called_once()

    @patch("repoforge.search.embedder.litellm.embedding")
    def test_embed_batch(self, mock_embedding):
        mock_embedding.return_value = self._mock_response([
            [0.1, 0.2],
            [0.3, 0.4],
            [0.5, 0.6],
        ])

        embedder = Embedder(model="test-model")
        results = embedder.embed(["a", "b", "c"])

        assert len(results) == 3
        assert results[0] == [0.1, 0.2]
        assert results[2] == [0.5, 0.6]

    @patch("repoforge.search.embedder.litellm.embedding")
    def test_auto_detect_dimension(self, mock_embedding):
        mock_embedding.return_value = self._mock_response([[0.1, 0.2, 0.3]])

        embedder = Embedder()
        assert embedder.dimension == 0

        embedder.embed(["test"])
        assert embedder.dimension == 3

    @patch("repoforge.search.embedder.litellm.embedding")
    def test_batching(self, mock_embedding):
        """Verify that large inputs are split into batches."""
        mock_embedding.return_value = self._mock_response([[0.1, 0.2]])

        embedder = Embedder(batch_size=2)
        texts = ["a", "b", "c", "d", "e"]
        embedder.embed(texts)

        # 5 texts with batch_size=2 → 3 API calls (2+2+1)
        assert mock_embedding.call_count == 3

    def test_empty_raises(self):
        embedder = Embedder()
        try:
            embedder.embed([])
            assert False, "Should have raised ValueError"
        except ValueError:
            pass

    @patch("repoforge.search.embedder.litellm.embedding")
    def test_api_key_passed(self, mock_embedding):
        mock_embedding.return_value = self._mock_response([[0.1]])

        embedder = Embedder(api_key="sk-test", api_base="http://localhost:8080")
        embedder.embed(["test"])

        call_kwargs = mock_embedding.call_args[1]
        assert call_kwargs["api_key"] == "sk-test"
        assert call_kwargs["api_base"] == "http://localhost:8080"
