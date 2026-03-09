"""Tests for EmbeddingService in the metadata knowledge graph system."""

import os
import pytest
from unittest.mock import patch, MagicMock

from src.metadata.embedding_service import EmbeddingService, EmbeddingAPIError


class TestEmbeddingService:
    """Test cases for EmbeddingService."""

    def test_init_without_api_key_raises_error(self):
        """Test that initialization fails without API key."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(EmbeddingAPIError) as exc_info:
                EmbeddingService()

            assert "DASHSCOPE_API_KEY" in str(exc_info.value)

    def test_init_with_api_key_succeeds(self):
        """Test that initialization succeeds with API key."""
        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test_key"}):
            with patch("src.metadata.embedding_service.dashscope") as mock_dashscope:
                service = EmbeddingService()

                assert service.api_key == "test_key"
                assert service.model == "text-embedding-v4"
                assert service.dimension == 1024

    def test_init_with_custom_model_and_dimension(self):
        """Test initialization with custom model and dimension."""
        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test_key"}):
            with patch("src.metadata.embedding_service.dashscope"):
                service = EmbeddingService(model="custom-model", dimension=512)

                assert service.model == "custom-model"
                assert service.dimension == 512

    def test_embed_text_returns_embedding(self):
        """Test embed_text returns embedding vector."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.output = {
            "embeddings": [{"embedding": [0.1] * 1024}]
        }

        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test_key"}):
            with patch("src.metadata.embedding_service.dashscope"):
                with patch("src.metadata.embedding_service.TextEmbedding.call") as mock_call:
                    mock_call.return_value = mock_response

                    service = EmbeddingService()
                    result = service.embed_text("test query")

                    assert len(result) == 1024
                    assert all(v == 0.1 for v in result)

    def test_embed_text_uses_query_text_type_and_instruct(self, monkeypatch):
        """Test embed_text passes text_type and instruct to API."""
        calls = {}

        def fake_call(**kwargs):
            calls.update(kwargs)
            return type(
                "Resp",
                (),
                {
                    "status_code": 200,
                    "output": {"embeddings": [{"embedding": [0.0] * 1024}]},
                },
            )()

        monkeypatch.setattr(
            "src.metadata.embedding_service.TextEmbedding.call",
            fake_call,
        )

        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test_key"}):
            with patch("src.metadata.embedding_service.dashscope"):
                service = EmbeddingService(model="text-embedding-v4", dimension=1024)
                service.embed_text(
                    "查询车牌",
                    text_type="query",
                    instruct="Given a DB query, retrieve schema",
                )

        assert calls["text_type"] == "query"
        assert calls["instruct"] == "Given a DB query, retrieve schema"

    def test_embed_text_empty_raises_error(self):
        """Test embed_text raises error for empty text."""
        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test_key"}):
            with patch("src.metadata.embedding_service.dashscope"):
                service = EmbeddingService()

                with pytest.raises(EmbeddingAPIError) as exc_info:
                    service.embed_text("")

                assert "empty" in str(exc_info.value).lower()

    def test_embed_text_whitespace_raises_error(self):
        """Test embed_text raises error for whitespace-only text."""
        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test_key"}):
            with patch("src.metadata.embedding_service.dashscope"):
                service = EmbeddingService()

                with pytest.raises(EmbeddingAPIError):
                    service.embed_text("   ")

    def test_embed_text_api_error(self):
        """Test embed_text handles API error."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.message = "Internal server error"

        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test_key"}):
            with patch("src.metadata.embedding_service.dashscope"):
                with patch("src.metadata.embedding_service.TextEmbedding.call") as mock_call:
                    mock_call.return_value = mock_response

                    service = EmbeddingService()

                    with pytest.raises(EmbeddingAPIError) as exc_info:
                        service.embed_text("test query")

                    assert exc_info.value.status_code == 500

    def test_embed_text_rate_limit_error(self):
        """Test embed_text handles rate limit error."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.message = "Rate limit exceeded"

        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test_key"}):
            with patch("src.metadata.embedding_service.dashscope"):
                with patch("src.metadata.embedding_service.TextEmbedding.call") as mock_call:
                    mock_call.return_value = mock_response

                    service = EmbeddingService()

                    with pytest.raises(EmbeddingAPIError) as exc_info:
                        service.embed_text("test query")

                    assert exc_info.value.status_code == 429

    def test_embed_batch_returns_embeddings(self):
        """Test embed_batch returns embeddings for multiple texts."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.output = {
            "embeddings": [
                {"embedding": [0.1] * 1024},
                {"embedding": [0.2] * 1024},
            ]
        }

        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test_key"}):
            with patch("src.metadata.embedding_service.dashscope"):
                with patch("src.metadata.embedding_service.TextEmbedding.call") as mock_call:
                    mock_call.return_value = mock_response

                    service = EmbeddingService()
                    result = service.embed_batch(["text1", "text2"])

                    assert len(result) == 2
                    assert len(result[0]) == 1024
                    assert len(result[1]) == 1024

    def test_embed_batch_empty_list(self):
        """Test embed_batch with empty list returns empty list."""
        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test_key"}):
            with patch("src.metadata.embedding_service.dashscope"):
                service = EmbeddingService()

                result = service.embed_batch([])

                assert result == []

    def test_embed_batch_exceeds_max_size(self):
        """Test embed_batch raises error when batch_size exceeds max."""
        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test_key"}):
            with patch("src.metadata.embedding_service.dashscope"):
                service = EmbeddingService()

                with pytest.raises(ValueError) as exc_info:
                    service.embed_batch(["text"] * 5, batch_size=15)

                assert "batch_size" in str(exc_info.value)

    def test_embed_batch_handles_empty_texts(self):
        """Test embed_batch handles empty texts in batch."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.output = {
            "embeddings": [
                {"embedding": [0.1] * 1024},
            ]
        }

        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test_key"}):
            with patch("src.metadata.embedding_service.dashscope"):
                with patch("src.metadata.embedding_service.TextEmbedding.call") as mock_call:
                    mock_call.return_value = mock_response

                    service = EmbeddingService()
                    # Empty string should get zero vector
                    result = service.embed_batch(["", "valid text"])

                    assert len(result) == 2
                    assert result[0] == [0.0] * 1024  # Empty text gets zero vector
                    assert result[1] == [0.1] * 1024  # Valid text gets embedding

    def test_embed_batch_processes_in_batches(self):
        """Test embed_batch processes texts in correct batch sizes."""
        # Create a side effect function that returns appropriate embeddings for each batch
        def mock_call_side_effect(*args, **kwargs):
            mock_response = MagicMock()
            mock_response.status_code = 200
            # Return embeddings matching the number of texts in the input
            input_texts = kwargs.get("input", [])
            mock_response.output = {
                "embeddings": [{"embedding": [0.1] * 1024} for _ in input_texts]
            }
            return mock_response

        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test_key"}):
            with patch("src.metadata.embedding_service.dashscope"):
                with patch("src.metadata.embedding_service.TextEmbedding.call") as mock_call:
                    mock_call.side_effect = mock_call_side_effect

                    service = EmbeddingService()
                    # 3 texts with batch_size=2 should result in 2 API calls
                    result = service.embed_batch(["a", "b", "c"], batch_size=2)

                    assert len(result) == 3
                    assert mock_call.call_count == 2

    def test_get_embedding_dimension(self):
        """Test get_embedding_dimension returns correct dimension."""
        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test_key"}):
            with patch("src.metadata.embedding_service.dashscope"):
                service = EmbeddingService(dimension=512)

                assert service.get_embedding_dimension() == 512

    def test_get_model_name(self):
        """Test get_model_name returns correct model name."""
        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test_key"}):
            with patch("src.metadata.embedding_service.dashscope"):
                service = EmbeddingService(model="custom-model")

                assert service.get_model_name() == "custom-model"

    def test_handle_api_error_rate_limit(self):
        """Test _handle_api_error for rate limit."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.code = "RateLimitExceeded"
        mock_response.message = "Too many requests"

        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test_key"}):
            with patch("src.metadata.embedding_service.dashscope"):
                service = EmbeddingService()

                with pytest.raises(EmbeddingAPIError) as exc_info:
                    service._handle_api_error(mock_response)

                assert "rate limit" in str(exc_info.value).lower()

    def test_embedding_api_error_attributes(self):
        """Test EmbeddingAPIError stores status_code and error_code."""
        error = EmbeddingAPIError(
            message="Test error",
            status_code=500,
            error_code="InternalServerError"
        )

        assert str(error) == "Test error"
        assert error.status_code == 500
        assert error.error_code == "InternalServerError"

    def test_embedding_api_error_without_codes(self):
        """Test EmbeddingAPIError without status_code and error_code."""
        error = EmbeddingAPIError(message="Test error")

        assert str(error) == "Test error"
        assert error.status_code is None
        assert error.error_code is None

    def test_embed_text_unexpected_exception(self):
        """Test embed_text handles unexpected exceptions."""
        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test_key"}):
            with patch("src.metadata.embedding_service.dashscope"):
                with patch("src.metadata.embedding_service.TextEmbedding.call") as mock_call:
                    mock_call.side_effect = RuntimeError("Unexpected error")

                    service = EmbeddingService()

                    with pytest.raises(EmbeddingAPIError) as exc_info:
                        service.embed_text("test query")

                    assert "Unexpected error" in str(exc_info.value)

    def test_embed_batch_unexpected_exception(self):
        """Test embed_batch handles unexpected exceptions."""
        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test_key"}):
            with patch("src.metadata.embedding_service.dashscope"):
                with patch("src.metadata.embedding_service.TextEmbedding.call") as mock_call:
                    mock_call.side_effect = RuntimeError("Unexpected error")

                    service = EmbeddingService()

                    with pytest.raises(EmbeddingAPIError):
                        service.embed_batch(["test"])

    def test_embed_batch_all_empty_texts(self):
        """Test embed_batch with all empty texts returns zero vectors."""
        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test_key"}):
            with patch("src.metadata.embedding_service.dashscope"):
                service = EmbeddingService()

                # All empty strings should return zero vectors
                result = service.embed_batch(["", "  ", ""])

                assert len(result) == 3
                assert all(len(emb) == 1024 for emb in result)
                # All should be zero vectors
                assert all(all(v == 0.0 for v in emb) for emb in result)
