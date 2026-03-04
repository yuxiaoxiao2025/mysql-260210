"""
Embedding Service for DashScope Text Embedding API.

Provides text embedding functionality for semantic similarity search
in the metadata knowledge graph system.
"""

import logging
import os
from typing import List

import dashscope
from dashscope import TextEmbedding
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)


class EmbeddingAPIError(Exception):
    """Custom exception for embedding API errors."""

    def __init__(self, message: str, status_code: int = None, error_code: str = None):
        """
        Initialize EmbeddingAPIError.

        Args:
            message: Error message
            status_code: HTTP status code from API response
            error_code: DashScope error code
        """
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


class EmbeddingService:
    """
    Service for generating text embeddings using DashScope API.

    Supports single and batch embedding operations with automatic retry
    on transient failures.
    """

    # API rate limit status code
    RATE_LIMIT_STATUS_CODE = 429

    def __init__(self, model: str = "text-embedding-v3", dimension: int = 1024):
        """
        Initialize EmbeddingService.

        Args:
            model: DashScope embedding model name (default: text-embedding-v3)
            dimension: Embedding vector dimension (default: 1024)

        Raises:
            EmbeddingAPIError: If DASHSCOPE_API_KEY is not set in environment
        """
        self.model = model
        self.dimension = dimension
        self.api_key = os.getenv("DASHSCOPE_API_KEY")

        if not self.api_key:
            error_msg = "DASHSCOPE_API_KEY not found in environment variables"
            logger.error(error_msg)
            raise EmbeddingAPIError(error_msg)

        dashscope.api_key = self.api_key
        logger.info(f"EmbeddingService initialized with model={model}, dimension={dimension}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(EmbeddingAPIError),
        reraise=True
    )
    def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding vector (1024 dimensions)

        Raises:
            EmbeddingAPIError: If API call fails after retries
        """
        if not text or not text.strip():
            raise EmbeddingAPIError("Text cannot be empty")

        logger.debug(f"Generating embedding for text (length={len(text)})")

        try:
            response = TextEmbedding.call(
                model=self.model,
                input=text,
                dimension=self.dimension
            )

            if response.status_code == 200:
                embedding = response.output['embeddings'][0]['embedding']
                logger.debug(f"Successfully generated embedding (dim={len(embedding)})")
                return embedding
            else:
                return self._handle_api_error(response)

        except EmbeddingAPIError:
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            error_msg = f"Unexpected error during embedding: {str(e)}"
            logger.error(error_msg)
            raise EmbeddingAPIError(error_msg)

    def embed_batch(self, texts: List[str], batch_size: int = 10) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batches.

        Args:
            texts: List of texts to embed
            batch_size: Number of texts per API call (max 10, default: 10)

        Returns:
            List of embedding vectors, one per input text

        Raises:
            EmbeddingAPIError: If API call fails after retries
            ValueError: If batch_size exceeds maximum allowed
        """
        if not texts:
            return []

        if batch_size > 10:
            raise ValueError(f"batch_size cannot exceed 10, got {batch_size}")

        logger.info(f"Generating embeddings for {len(texts)} texts in batches of {batch_size}")

        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_embeddings = self._embed_batch_internal(batch)
            all_embeddings.extend(batch_embeddings)

        logger.info(f"Successfully generated {len(all_embeddings)} embeddings")
        return all_embeddings

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(EmbeddingAPIError),
        reraise=True
    )
    def _embed_batch_internal(self, texts: List[str]) -> List[List[float]]:
        """
        Internal method to generate embeddings for a batch of texts.

        Args:
            texts: List of texts to embed (max 10)

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        # Filter empty texts and track indices
        valid_texts = []
        valid_indices = []
        for idx, text in enumerate(texts):
            if text and text.strip():
                valid_texts.append(text)
                valid_indices.append(idx)

        if not valid_texts:
            # All texts were empty, return zero vectors
            return [[0.0] * self.dimension for _ in texts]

        logger.debug(f"Batch embedding {len(valid_texts)} texts")

        try:
            response = TextEmbedding.call(
                model=self.model,
                input=valid_texts,
                dimension=self.dimension
            )

            if response.status_code == 200:
                embeddings = response.output['embeddings']

                # Build result list maintaining original order
                result = []
                embedding_idx = 0
                for idx in range(len(texts)):
                    if idx in valid_indices:
                        # Get embedding for this valid text
                        emb_data = embeddings[embedding_idx]
                        result.append(emb_data['embedding'])
                        embedding_idx += 1
                    else:
                        # Empty text, return zero vector
                        result.append([0.0] * self.dimension)

                return result
            else:
                return self._handle_api_error(response)

        except EmbeddingAPIError:
            raise
        except Exception as e:
            error_msg = f"Unexpected error during batch embedding: {str(e)}"
            logger.error(error_msg)
            raise EmbeddingAPIError(error_msg)

    def _handle_api_error(self, response) -> None:
        """
        Handle API error responses.

        Args:
            response: DashScope API response object

        Raises:
            EmbeddingAPIError: Always raises with appropriate error details
        """
        status_code = response.status_code
        error_code = getattr(response, 'code', None)
        error_message = getattr(response, 'message', str(response))

        # Log the error
        logger.error(f"Embedding API error: status_code={status_code}, "
                    f"code={error_code}, message={error_message}")

        # Handle rate limiting specially
        if status_code == self.RATE_LIMIT_STATUS_CODE:
            raise EmbeddingAPIError(
                f"API rate limit exceeded. Please try again later.",
                status_code=status_code,
                error_code=error_code
            )

        # Handle other API errors
        raise EmbeddingAPIError(
            f"Embedding API error: {error_message}",
            status_code=status_code,
            error_code=error_code
        )

    def get_embedding_dimension(self) -> int:
        """
        Get the dimension of embeddings produced by this service.

        Returns:
            Embedding dimension (default: 1024)
        """
        return self.dimension

    def get_model_name(self) -> str:
        """
        Get the model name used for embeddings.

        Returns:
            Model name string
        """
        return self.model