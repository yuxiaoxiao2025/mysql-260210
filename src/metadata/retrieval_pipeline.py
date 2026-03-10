"""
Two-layer retrieval pipeline with budget control.

This module implements a retrieval pipeline that performs:
1. Vector similarity search for initial candidates
2. Table-level reranking using qwen3-rerank
3. Field-level reranking (when budget allows)

Budget control ensures the pipeline completes within the specified time limit,
with fallback to vector-only results when budget is exhausted.
"""

import logging
import time
from typing import List, Optional, Tuple

from src.metadata.graph_store import GraphStore
from src.metadata.rerank_service import RerankService
from src.metadata.retrieval_agent import RetrievalAgent
from src.metadata.retrieval_models import (
    RetrievalRequest,
    RetrievalLevel,
    TableMatch,
    TableRetrievalResult,
    FieldMatch,
)

logger = logging.getLogger(__name__)

# Threshold for field rerank (requires at least 180ms remaining)
FIELD_RERANK_THRESHOLD_MS = 180


class RetrievalPipeline:
    """
    Two-layer retrieval pipeline with budget control.

    Implements a budget-aware retrieval pipeline that:
    1. Performs vector similarity search
    2. Applies table-level reranking
    3. Optionally applies field-level reranking if budget allows

    The pipeline monitors execution time and skips optional steps
    when the budget is exhausted to ensure timely responses.

    Attributes:
        budget_ms: Maximum allowed execution time in milliseconds.
        agent: RetrievalAgent for vector similarity search.
        rerank_service: RerankService for relevance scoring.

    Example:
        >>> pipeline = RetrievalPipeline(budget_ms=500)
        >>> result = pipeline.search("查询车牌")
        >>> print(result.matches[0].table_name)
    """

    def __init__(
        self,
        budget_ms: int = 1000,  # 从 500 改为 1000
        env: str = "dev",
        agent: Optional[RetrievalAgent] = None,
        rerank_service: Optional[RerankService] = None,
    ):
        """
        Initialize the RetrievalPipeline.

        Args:
            budget_ms: Maximum execution time budget in milliseconds.
            env: Environment name for RetrievalAgent.
            agent: Optional RetrievalAgent instance (created if not provided).
            rerank_service: Optional RerankService instance (created if not provided).
        """
        self.budget_ms = budget_ms
        self.agent = agent or RetrievalAgent(env=env)
        self.rerank_service = rerank_service or RerankService()

        logger.info(
            f"RetrievalPipeline initialized with budget={budget_ms}ms"
        )

    def search(
        self,
        query: str,
        top_k: int = 10,
        **kwargs,
    ) -> TableRetrievalResult:
        """
        Execute the two-layer retrieval pipeline.

        Args:
            query: Search query string.
            top_k: Number of top results to return.
            **kwargs: Additional arguments passed to RetrievalAgent.

        Returns:
            TableRetrievalResult with reranked matches and metadata.
        """
        start_time = time.time()
        metadata = {
            "field_rerank_skipped": False,
            "table_rerank_time_ms": 0,
            "field_rerank_time_ms": 0,
            "vector_search_time_ms": 0,
        }

        # Step 1: Vector similarity search
        vector_start = time.time()
        request = RetrievalRequest(
            query=query,
            level=RetrievalLevel.TABLE,
            top_k=top_k * 2,  # Get more candidates for reranking
        )
        vector_result = self.agent.search(request)
        vector_time_ms = int((time.time() - vector_start) * 1000)
        metadata["vector_search_time_ms"] = vector_time_ms

        # Extract candidate table names
        candidates = [m.table_name for m in vector_result.matches]

        if not candidates:
            return TableRetrievalResult(
                query=query,
                matches=[],
                execution_time_ms=int((time.time() - start_time) * 1000),
                metadata=metadata,
            )

        # Step 2: Table-level reranking
        reranked_tables, table_rerank_time_ms = self._rerank_tables(
            query, candidates
        )
        metadata["table_rerank_time_ms"] = table_rerank_time_ms

        # Check remaining budget for field-level reranking
        elapsed_ms = int((time.time() - start_time) * 1000)
        remaining_budget = self.budget_ms - elapsed_ms

        # Step 3: Field-level reranking (if budget allows)
        field_rerank_skipped = remaining_budget < FIELD_RERANK_THRESHOLD_MS
        metadata["field_rerank_skipped"] = field_rerank_skipped

        if not field_rerank_skipped and reranked_tables:
            field_matches, field_rerank_time_ms = self._rerank_fields(
                query, reranked_tables[:top_k]
            )
            metadata["field_rerank_time_ms"] = field_rerank_time_ms
        else:
            field_matches = []
            if field_rerank_skipped:
                logger.info(
                    f"Skipping field rerank due to budget constraint "
                    f"(remaining: {remaining_budget}ms < threshold: {FIELD_RERANK_THRESHOLD_MS}ms)"
                )

        # Build final result
        total_time_ms = int((time.time() - start_time) * 1000)

        # Convert reranked table names back to TableMatch objects
        matches = []
        for table_name in reranked_tables[:top_k]:
            # Find original match for similarity score
            original_match = next(
                (m for m in vector_result.matches if m.table_name == table_name),
                None
            )
            if original_match:
                matches.append(original_match)
            else:
                # Create new match with default score
                matches.append(TableMatch(
                    table_name=table_name,
                    similarity_score=0.5,
                    description="",
                ))

        return TableRetrievalResult(
            query=query,
            matches=matches,
            execution_time_ms=total_time_ms,
            metadata=metadata,
        )

    def _rerank_tables(
        self,
        query: str,
        candidates: List[str],
    ) -> Tuple[List[str], int]:
        """
        Rerank table candidates using qwen3-rerank.

        Args:
            query: Search query.
            candidates: List of table names to rerank.

        Returns:
            Tuple of (reranked table names, execution time in ms).
        """
        start_time = time.time()

        try:
            # Get table descriptions for reranking context
            table_contexts = self._build_table_contexts(candidates)

            # Call rerank service
            results = self.rerank_service.rerank(
                query=query,
                candidates=table_contexts,
                top_n=len(candidates),
            )

            # Map reranked indices back to table names
            reranked = [candidates[r.index] for r in results]

            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.debug(
                f"Table rerank completed in {elapsed_ms}ms for {len(candidates)} candidates"
            )

            return reranked, elapsed_ms

        except Exception as e:
            logger.warning(f"Table rerank failed, using original order: {e}")
            elapsed_ms = int((time.time() - start_time) * 1000)
            return candidates, elapsed_ms

    def _rerank_fields(
        self,
        query: str,
        table_names: List[str],
    ) -> Tuple[List[FieldMatch], int]:
        """
        Rerank fields within selected tables.

        Args:
            query: Search query.
            table_names: List of table names to search fields in.

        Returns:
            Tuple of (field matches, execution time in ms).
        """
        start_time = time.time()

        try:
            # Build field context for each table
            field_contexts = self._build_field_contexts(table_names)

            if not field_contexts:
                return [], int((time.time() - start_time) * 1000)

            # Call rerank service
            results = self.rerank_service.rerank(
                query=query,
                candidates=field_contexts,
                top_n=20,  # Limit field results
            )

            # Map results to FieldMatch objects
            matches = []
            for r in results:
                context = field_contexts[r.index]
                # Parse table.field from context
                parts = context.split(".", 1)
                if len(parts) == 2:
                    table_name, field_name = parts
                    matches.append(FieldMatch(
                        table_name=table_name,
                        field_name=field_name,
                        data_type="",
                        description="",
                        similarity_score=r.relevance_score,
                    ))

            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.debug(
                f"Field rerank completed in {elapsed_ms}ms, found {len(matches)} fields"
            )

            return matches, elapsed_ms

        except Exception as e:
            logger.warning(f"Field rerank failed: {e}")
            elapsed_ms = int((time.time() - start_time) * 1000)
            return [], elapsed_ms

    def _build_table_contexts(self, table_names: List[str]) -> List[str]:
        """
        Build context strings for table reranking.

        Args:
            table_names: List of table names.

        Returns:
            List of context strings combining table name and description.
        """
        contexts = []
        for name in table_names:
            details = self.agent.get_table_details(name)
            comment = details.get("comment", "")
            domain = details.get("business_domain", "")

            # Combine table name, domain, and comment for context
            context = f"{name}"
            if domain:
                context += f" ({domain})"
            if comment:
                context += f": {comment}"

            contexts.append(context)

        return contexts

    def _build_field_contexts(self, table_names: List[str]) -> List[str]:
        """
        Build context strings for field reranking.

        Args:
            table_names: List of table names.

        Returns:
            List of context strings in format "table.field: description".
        """
        contexts = []

        for table_name in table_names:
            details = self.agent.get_table_details(table_name)
            columns = details.get("columns", [])

            for col in columns:
                field_name = col.get("name", "")
                comment = col.get("comment", "")
                data_type = col.get("data_type", "")

                # Build context: table.field (type): description
                context = f"{table_name}.{field_name}"
                if data_type:
                    context += f" ({data_type})"
                if comment:
                    context += f": {comment}"

                contexts.append(context)

        return contexts
