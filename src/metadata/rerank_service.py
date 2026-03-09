"""
Rerank service using qwen3-rerank model.

This module provides reranking functionality to sort candidates
by relevance to a query using the DashScope OpenAI-compatible Rerank API.
"""

import logging
import os
import time
from dataclasses import dataclass
from typing import List, Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class RerankResult:
    """Result from reranking operation.

    Attributes:
        index: Original index of the document in the input list.
        relevance_score: Relevance score (0-1) indicating match quality.
    """

    index: int
    relevance_score: float


class RerankService:
    """Service for reranking documents by relevance to a query.

    Uses the qwen3-rerank model via DashScope OpenAI-compatible Rerank API
    to score and sort candidate documents by their relevance to a query.

    Example:
        >>> service = RerankService()
        >>> results = service.rerank("查询车牌", ["车牌表", "用户表", "订单表"])
        >>> print(results[0].index)  # Index of most relevant document
    """

    MODEL_NAME = "qwen3-rerank"
    # OpenAI-compatible Rerank API for qwen3-rerank
    API_URL = "https://dashscope.aliyuncs.com/compatible-api/v1/reranks"
    DEFAULT_TIMEOUT = 30  # seconds
    DEFAULT_MAX_RETRIES = 2
    # Default instruction for database schema retrieval
    DEFAULT_INSTRUCT = "Given a database query, retrieve relevant schema tables and fields."

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        instruct: Optional[str] = None,
    ):
        """Initialize the RerankService.

        Args:
            api_key: DashScope API key. If not provided, reads from
                     DASHSCOPE_API_KEY environment variable.
            timeout: API request timeout in seconds. Default is 30 seconds.
            max_retries: Maximum number of retry attempts on failure. Default is 2.
            instruct: Custom instruction for reranking. If not provided, uses default.
        """
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "DASHSCOPE_API_KEY not found. Set it as environment variable "
                "or pass api_key parameter."
            )
        self.timeout = timeout
        self.max_retries = max_retries
        self.instruct = instruct or self.DEFAULT_INSTRUCT

    def rerank(
        self,
        query: str,
        candidates: List[str],
        top_n: Optional[int] = None,
    ) -> List[RerankResult]:
        """Rerank candidates by relevance to the query.

        Args:
            query: The search query to compare against.
            candidates: List of candidate document strings to rank.
            top_n: Optional limit on number of results to return.

        Returns:
            List of RerankResult sorted by relevance_score in descending order.

        Raises:
            RuntimeError: If the API call fails after all retries.
            ValueError: If query is empty.
        """
        if not query:
            raise ValueError("Query cannot be empty")
        if not candidates:
            return []

        # Build request payload for OpenAI-compatible API
        # Reference: https://help.aliyun.com/zh/model-studio/text-rerank-api
        payload = {
            "model": self.MODEL_NAME,
            "query": query,
            "documents": candidates,
            "instruct": self.instruct,
        }
        if top_n is not None:
            payload["top_n"] = top_n

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Retry loop with exponential backoff
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                response = requests.post(
                    self.API_URL,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout,
                )
                response.raise_for_status()

                data = response.json()

                # Parse results from OpenAI-compatible response format
                # Response format: {"results": [{"index": 0, "relevance_score": 0.9}, ...]}
                results = []
                rerank_results = data.get("results", [])

                for item in rerank_results:
                    results.append(
                        RerankResult(
                            index=item.get("index", 0),
                            relevance_score=item.get("relevance_score", 0.0),
                        )
                    )

                # Results are already sorted by relevance score descending
                return results

            except requests.exceptions.RequestException as e:
                last_error = e
                if attempt < self.max_retries:
                    # Exponential backoff: 0.5s, 1s, 2s, ...
                    backoff = 0.5 * (2 ** attempt)
                    logger.warning(
                        f"Rerank API call failed (attempt {attempt + 1}/{self.max_retries + 1}): {e}. "
                        f"Retrying in {backoff}s..."
                    )
                    time.sleep(backoff)
                else:
                    logger.error(
                        f"Rerank API call failed after {self.max_retries + 1} attempts: {e}"
                    )
            except (KeyError, ValueError) as e:
                last_error = e
                logger.error(f"Failed to parse Rerank API response: {e}")
                break

        raise RuntimeError(f"Rerank API error after {self.max_retries + 1} attempts: {last_error}") from last_error
