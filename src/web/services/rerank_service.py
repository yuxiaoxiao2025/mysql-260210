"""
Search and Rerank Service for web layer.

Provides search and ranking functionality combining vector similarity
with domain keyword matching for intelligent table retrieval.
"""

import logging
from typing import List, Tuple, Optional, Any, Dict

from src.metadata.embedding_service import EmbeddingService
from src.metadata.graph_store import GraphStore

logger = logging.getLogger(__name__)


class RerankService:
    """
    Search and rank service for table retrieval.

    Combines vector similarity search with domain keyword matching
    to provide ranked table recommendations.

    Attributes:
        VECTOR_WEIGHT: Weight for vector similarity (0.7).
        DOMAIN_WEIGHT: Weight for domain match (0.3).
        RECALL_TOP_K: Number of candidates to recall (50).
    """

    VECTOR_WEIGHT = 0.7
    DOMAIN_WEIGHT = 0.3
    RECALL_TOP_K = 50

    # Domain keyword mappings (Chinese query keywords -> business domain)
    DOMAIN_KEYWORDS = {
        "vehicle": ["车", "车辆", "车牌"],
        "user": ["用户", "会员", "客户"],
        "order": ["订单", "订购"],
        "product": ["产品", "商品", "货物"],
        "warehouse": ["仓库", "库存", "仓储"],
        "finance": ["财务", "账", "资金", "支付"],
        "employee": ["员工", "职员", "人员"],
        "department": ["部门", "组织"],
        "log": ["日志", "记录", "操作记录"],
    }

    def __init__(
        self,
        graph_store: GraphStore,
        embedding_service: EmbeddingService,
    ):
        """
        Initialize RerankService.

        Args:
            graph_store: GraphStore instance for vector search.
            embedding_service: EmbeddingService instance for text embedding.
        """
        self.graph_store = graph_store
        self.embedding_service = embedding_service
        logger.info("RerankService initialized")

    def search_and_rank(
        self,
        query: str,
        top_k: Optional[int] = None,
    ) -> List[Tuple[str, float, str]]:
        """
        Search and rank tables by query.

        Two-stage retrieval:
        1. Recall: Vector search to get top 50 candidates
        2. Rerank: Score = 0.7 * vector_sim + 0.3 * domain_match

        Args:
            query: Search query string.
            top_k: Optional limit for final results. If None, uses all recalled results.

        Returns:
            List of tuples (table_name, score, reason), sorted by score descending.

        Raises:
            ValueError: If query is empty.
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        # Stage 1: Recall - vector search
        query_embedding = self.embedding_service.embed_text(query)
        recall_k = self.RECALL_TOP_K

        candidates = self.graph_store.query_tables(
            embedding=query_embedding,
            top_k=recall_k,
        )

        if not candidates:
            logger.info(f"No candidates found for query: {query}")
            return []

        # Stage 2: Rerank with vector_sim + domain_match
        results = []
        for candidate in candidates:
            table_id = candidate["id"]
            distance = candidate["distance"]
            metadata = candidate.get("metadata", {})

            # Calculate vector similarity (1 - distance for cosine)
            vector_sim = 1.0 - distance

            # Calculate domain match score
            business_domain = metadata.get("business_domain", "")
            domain_match = self._calculate_domain_match(query, business_domain)

            # Calculate final score
            final_score = (
                self.VECTOR_WEIGHT * vector_sim
                + self.DOMAIN_WEIGHT * domain_match
            )

            # Generate reason
            reason = self._generate_reason(
                query=query,
                table_id=table_id,
                metadata=metadata,
                vector_sim=vector_sim,
                domain_match=domain_match,
            )

            results.append((table_id, final_score, reason))

        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)

        # Apply top_k limit if specified
        if top_k is not None:
            results = results[:top_k]

        logger.info(f"Search completed: query='{query}', candidates={len(candidates)}, results={len(results)}")
        return results

    def _calculate_domain_match(self, query: str, business_domain: str) -> float:
        """
        Calculate domain match score based on keyword presence in query.

        Args:
            query: User query string.
            business_domain: Business domain of the table.

        Returns:
            1.0 if domain keyword found in query, 0.0 otherwise.
        """
        if not business_domain:
            return 0.0

        domain_lower = business_domain.lower()

        # Get keywords for this domain
        keywords = self.DOMAIN_KEYWORDS.get(domain_lower, [])

        # Check if any keyword is in the query
        for keyword in keywords:
            if keyword in query:
                return 1.0

        return 0.0

    def _generate_reason(
        self,
        query: str,
        table_id: str,
        metadata: Dict[str, Any],
        vector_sim: float,
        domain_match: float,
    ) -> str:
        """
        Generate human-readable reason for the ranking.

        Args:
            query: Original query.
            table_id: Table identifier.
            metadata: Table metadata.
            vector_sim: Vector similarity score.
            domain_match: Domain match score.

        Returns:
            Reason string explaining the ranking.
        """
        reason_parts = []

        # Add vector similarity info
        reason_parts.append(f"向量相似度: {vector_sim:.2f}")

        # Add domain match info
        if domain_match > 0:
            business_domain = metadata.get("business_domain", "")
            reason_parts.append(f"领域匹配: {business_domain}")
        else:
            reason_parts.append("领域匹配: 无")

        # Add comment if available
        comment = metadata.get("comment")
        if comment:
            reason_parts.append(f"表描述: {comment[:30]}...")

        return " | ".join(reason_parts)