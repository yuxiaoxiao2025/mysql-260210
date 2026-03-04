"""
Retrieval Agent for semantic search over database schema metadata.

Provides table-level and field-level retrieval using vector similarity
search with ChromaDB and the EmbeddingService.
"""

import logging
import time
from typing import List, Union

from src.metadata.models import KnowledgeGraph
from src.metadata.retrieval_models import (
    FieldMatch,
    FieldRetrievalResult,
    RetrievalLevel,
    RetrievalRequest,
    RetrievalResult,
    TableMatch,
    TableRetrievalResult,
)
from src.metadata.embedding_service import EmbeddingService
from src.metadata.graph_store import GraphStore

logger = logging.getLogger(__name__)


class RetrievalAgent:
    """
    Semantic retrieval agent for database schema metadata.

    Provides intelligent search capabilities over table and field metadata
    using vector embeddings for semantic similarity matching.

    Attributes:
        env: Environment name (e.g., 'dev', 'prod').
        store: GraphStore instance for vector storage.
        embedding_service: EmbeddingService for generating embeddings.
        graph: Knowledge graph loaded from storage.
    """

    def __init__(self, env: str = "dev"):
        """
        Initialize RetrievalAgent with environment-specific configuration.

        Args:
            env: Environment name ("dev" or "prod").
        """
        self.env = env
        self.store = GraphStore(env=env)
        self.embedding_service = EmbeddingService()
        self.graph = self.store.load_graph()

        logger.info(
            f"RetrievalAgent initialized for env='{env}' "
            f"(tables indexed: {self.store.get_table_count()}, "
            f"fields indexed: {self.store.get_field_count()})"
        )

    def search(self, request: RetrievalRequest) -> RetrievalResult:
        """
        Unified retrieval entry point.

        Routes the search request to the appropriate level-specific method
        (table or field) based on the request configuration.

        Args:
            request: Retrieval request containing query, level, top_k, and optional filters.

        Returns:
            TableRetrievalResult if level is TABLE, FieldRetrievalResult if level is FIELD.
        """
        start_time = time.time()

        logger.info(
            f"Processing search request: query='{request.query}', "
            f"level={request.level.value}, top_k={request.top_k}"
        )

        # 1. Embed the query
        query_embedding = self.embedding_service.embed_text(request.query)

        # 2. Route to appropriate search method
        if request.level == RetrievalLevel.TABLE:
            matches = self._search_tables(request, query_embedding)

            # 3. Expand by foreign keys for table-level results
            expanded = self._expand_by_foreign_keys([m.table_name for m in matches])

            result = TableRetrievalResult(
                query=request.query,
                matches=matches,
                execution_time_ms=int((time.time() - start_time) * 1000),
                metadata={
                    "expanded_tables": expanded,
                    "total_matches": len(matches),
                }
            )
        else:  # FIELD level
            matches = self._search_fields(request, query_embedding)

            result = FieldRetrievalResult(
                query=request.query,
                matches=matches,
                execution_time_ms=int((time.time() - start_time) * 1000),
                metadata={
                    "filter_tables": request.filter_tables,
                    "total_matches": len(matches),
                }
            )

        logger.info(
            f"Search completed in {result.execution_time_ms}ms, "
            f"found {len(matches)} matches"
        )

        return result

    def _search_tables(
        self,
        request: RetrievalRequest,
        embedding: List[float]
    ) -> List[TableMatch]:
        """
        Perform table-level semantic search.

        Queries ChromaDB for tables matching the embedding vector and
        converts the results to TableMatch objects.

        Args:
            request: Retrieval request with query and top_k.
            embedding: Query embedding vector (1024 dimensions).

        Returns:
            List of TableMatch objects sorted by similarity score (descending).
        """
        logger.debug(f"Searching tables with top_k={request.top_k}")

        # Query ChromaDB
        results = self.store.query_tables(embedding, top_k=request.top_k)

        # Convert to TableMatch
        matches = []
        for result in results:
            table_id = result["id"]
            distance = result["distance"]
            metadata = result["metadata"]

            # Convert distance to similarity score
            # ChromaDB returns cosine distance (range 0-2)
            # Convert to normalized similarity: 1/(1+distance), range 0.33-1.0
            similarity_score = 1.0 / (1.0 + distance)

            match = TableMatch(
                table_name=table_id,
                similarity_score=similarity_score,
                description=metadata.get("comment", ""),
                business_tags=[metadata.get("business_domain", "其他")],
                database_name=metadata.get("database_name", "")
            )
            matches.append(match)

        logger.debug(f"Found {len(matches)} table matches")
        return matches

    def _search_fields(
        self,
        request: RetrievalRequest,
        embedding: List[float]
    ) -> List[FieldMatch]:
        """
        Perform field-level semantic search with optional table filtering.

        Queries ChromaDB for fields matching the embedding vector and
        converts the results to FieldMatch objects.

        Args:
            request: Retrieval request with query, top_k, and optional filter_tables.
            embedding: Query embedding vector (1024 dimensions).

        Returns:
            List of FieldMatch objects sorted by similarity score (descending).
        """
        filter_info = f" (filtered by {len(request.filter_tables)} tables)" if request.filter_tables else ""
        logger.debug(f"Searching fields with top_k={request.top_k}{filter_info}")

        # Query ChromaDB with optional table filter
        results = self.store.query_fields(
            embedding,
            filter_tables=request.filter_tables,
            top_k=request.top_k
        )

        # Convert to FieldMatch
        matches = []
        for result in results:
            field_id = result["id"]
            distance = result["distance"]
            metadata = result["metadata"]

            # Convert distance to similarity score
            similarity_score = 1.0 / (1.0 + distance)

            # Parse table_name.field_name from field_id
            parts = field_id.split(".", 1)
            table_name = parts[0] if len(parts) > 0 else ""
            field_name = parts[1] if len(parts) > 1 else field_id

            match = FieldMatch(
                table_name=metadata.get("table_name", table_name),
                field_name=field_name,
                data_type=metadata.get("data_type", ""),
                description=metadata.get("comment", ""),
                similarity_score=similarity_score,
                is_primary_key=metadata.get("is_primary_key", False),
                is_foreign_key=metadata.get("is_foreign_key", False),
            )
            matches.append(match)

        logger.debug(f"Found {len(matches)} field matches")
        return matches

    def _expand_by_foreign_keys(self, table_names: List[str]) -> List[str]:
        """
        Expand table list by following foreign key relationships.

        If a table has foreign keys to other tables, include those tables too.
        This helps provide context for SQL generation by including related tables.

        Args:
            table_names: Initial list of table names.

        Returns:
            List of unique table names including original tables and
            all tables referenced via foreign keys.
        """
        if not self.graph:
            logger.warning("Knowledge graph not loaded, cannot expand by foreign keys")
            return table_names

        expanded = set(table_names)

        for table_name in table_names:
            # Get foreign keys from this table
            foreign_keys = self.graph.get_foreign_keys_from(table_name)

            for fk in foreign_keys:
                referenced_table = fk.referenced_table
                if referenced_table:
                    expanded.add(referenced_table)
                    logger.debug(
                        f"Added referenced table '{referenced_table}' "
                        f"via foreign key from '{table_name}.{fk.column_name}'"
                    )

        logger.info(
            f"Expanded tables: {len(table_names)} -> {len(expanded)} "
            f"(added {len(expanded) - len(table_names)} via foreign keys)"
        )

        return list(expanded)

    def get_table_details(self, table_name: str) -> dict:
        """
        Get detailed metadata for a specific table.

        Args:
            table_name: Name of the table to retrieve details for.

        Returns:
            Dictionary with table metadata, or empty dict if not found.
        """
        if not self.graph:
            logger.warning("Knowledge graph not loaded")
            return {}

        table = self.graph.get_table(table_name)
        if not table:
            logger.warning(f"Table not found in knowledge graph: {table_name}")
            return {}

        return {
            "table_name": table.table_name,
            "database_name": table.database_name,
            "comment": table.comment,
            "business_domain": table.business_domain,
            "columns": [
                {
                    "name": col.name,
                    "data_type": col.data_type,
                    "comment": col.comment,
                    "is_primary_key": col.is_primary_key,
                    "is_foreign_key": col.is_foreign_key,
                    "references_table": col.references_table,
                }
                for col in table.columns
            ],
            "foreign_keys": [
                {
                    "column_name": fk.column_name,
                    "referenced_table": fk.referenced_table,
                    "referenced_column": fk.referenced_column,
                }
                for fk in table.foreign_keys
            ],
            "tags": table.tags,
        }

    def get_stats(self) -> dict:
        """
        Get statistics about the retrieval agent.

        Returns:
            Dictionary with storage statistics and graph status.
        """
        return {
            "env": self.env,
            "graph_loaded": self.graph is not None,
            "table_count": self.store.get_table_count(),
            "field_count": self.store.get_field_count(),
            "graph_tables": len(self.graph.tables) if self.graph else 0,
        }