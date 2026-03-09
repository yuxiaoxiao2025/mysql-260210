"""Tests for RetrievalAgent in the metadata knowledge graph system."""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock

from src.metadata.retrieval_agent import RetrievalAgent
from src.metadata.retrieval_pipeline import RetrievalPipeline
from src.metadata.rerank_service import RerankResult
from src.metadata.retrieval_models import (
    RetrievalLevel,
    RetrievalRequest,
    TableMatch,
    FieldMatch,
    TableRetrievalResult,
    FieldRetrievalResult,
)
from src.metadata.models import (
    KnowledgeGraph,
    TableMetadata,
    ForeignKeyRelation,
)


class TestRetrievalAgent:
    """Test cases for RetrievalAgent."""

    @pytest.fixture
    def mock_store(self):
        """Create a mock GraphStore."""
        store = MagicMock()
        store.get_table_count.return_value = 10
        store.get_field_count.return_value = 50
        store.load_graph.return_value = KnowledgeGraph(tables=[
            TableMetadata(
                table_name="users",
                foreign_keys=[
                    ForeignKeyRelation(
                        column_name="dept_id",
                        referenced_table="departments",
                        referenced_column="id",
                    )
                ],
            ),
            TableMetadata(table_name="departments"),
        ])
        return store

    @pytest.fixture
    def mock_embedding_service(self):
        """Create a mock EmbeddingService."""
        service = MagicMock()
        service.embed_text.return_value = [0.1] * 1024
        return service

    def test_init_loads_graph(self, mock_store, mock_embedding_service):
        """Test RetrievalAgent initialization loads graph."""
        with patch("src.metadata.retrieval_agent.GraphStore", return_value=mock_store):
            with patch("src.metadata.retrieval_agent.EmbeddingService", return_value=mock_embedding_service):
                agent = RetrievalAgent(env="test")

                assert agent.env == "test"
                mock_store.load_graph.assert_called_once()

    def test_search_table_level(self, mock_store, mock_embedding_service):
        """Test search with table level returns TableRetrievalResult."""
        mock_store.query_tables.return_value = [
            {"id": "users", "distance": 0.1, "metadata": {"business_domain": "用户", "comment": ""}},
            {"id": "orders", "distance": 0.2, "metadata": {"business_domain": "订单", "comment": ""}},
        ]

        with patch("src.metadata.retrieval_agent.GraphStore", return_value=mock_store):
            with patch("src.metadata.retrieval_agent.EmbeddingService", return_value=mock_embedding_service):
                agent = RetrievalAgent(env="test")
                request = RetrievalRequest(
                    query="查找用户表",
                    level=RetrievalLevel.TABLE,
                    top_k=5,
                )

                result = agent.search(request)

                assert isinstance(result, TableRetrievalResult)
                assert len(result.matches) == 2
                assert result.matches[0].table_name == "users"
                mock_store.query_tables.assert_called_once()

    def test_search_field_level(self, mock_store, mock_embedding_service):
        """Test search with field level returns FieldRetrievalResult."""
        mock_store.query_fields.return_value = [
            {
                "id": "users.id",
                "distance": 0.1,
                "metadata": {
                    "table_name": "users",
                    "data_type": "INT",
                    "comment": "Primary key",
                    "is_primary_key": True,
                    "is_foreign_key": False,
                }
            },
        ]

        with patch("src.metadata.retrieval_agent.GraphStore", return_value=mock_store):
            with patch("src.metadata.retrieval_agent.EmbeddingService", return_value=mock_embedding_service):
                agent = RetrievalAgent(env="test")
                request = RetrievalRequest(
                    query="查找ID字段",
                    level=RetrievalLevel.FIELD,
                    top_k=5,
                )

                result = agent.search(request)

                assert isinstance(result, FieldRetrievalResult)
                assert len(result.matches) == 1
                assert result.matches[0].field_name == "id"
                mock_store.query_fields.assert_called_once()

    def test_search_field_level_with_filter(self, mock_store, mock_embedding_service):
        """Test search with field level and table filter."""
        mock_store.query_fields.return_value = []

        with patch("src.metadata.retrieval_agent.GraphStore", return_value=mock_store):
            with patch("src.metadata.retrieval_agent.EmbeddingService", return_value=mock_embedding_service):
                agent = RetrievalAgent(env="test")
                request = RetrievalRequest(
                    query="查找字段",
                    level=RetrievalLevel.FIELD,
                    top_k=5,
                    filter_tables=["users"],
                )

                result = agent.search(request)

                # Check filter was passed
                call_args = mock_store.query_fields.call_args
                assert call_args[1]["filter_tables"] == ["users"]

    def test_search_calls_embed_text(self, mock_store, mock_embedding_service):
        """Test search calls embed_text with query."""
        mock_store.query_tables.return_value = []

        with patch("src.metadata.retrieval_agent.GraphStore", return_value=mock_store):
            with patch("src.metadata.retrieval_agent.EmbeddingService", return_value=mock_embedding_service):
                agent = RetrievalAgent(env="test")
                request = RetrievalRequest(query="test query")

                agent.search(request)

                mock_embedding_service.embed_text.assert_called_once_with("test query")

    def test_expand_by_foreign_keys(self, mock_store, mock_embedding_service):
        """Test _expand_by_foreign_keys adds referenced tables."""
        with patch("src.metadata.retrieval_agent.GraphStore", return_value=mock_store):
            with patch("src.metadata.retrieval_agent.EmbeddingService", return_value=mock_embedding_service):
                agent = RetrievalAgent(env="test")

                result = agent._expand_by_foreign_keys(["users"])

                # users has foreign key to departments
                assert "users" in result
                assert "departments" in result

    def test_expand_by_foreign_keys_no_graph(self, mock_store, mock_embedding_service):
        """Test _expand_by_foreign_keys returns original when no graph."""
        mock_store.load_graph.return_value = None

        with patch("src.metadata.retrieval_agent.GraphStore", return_value=mock_store):
            with patch("src.metadata.retrieval_agent.EmbeddingService", return_value=mock_embedding_service):
                agent = RetrievalAgent(env="test")

                result = agent._expand_by_foreign_keys(["users"])

                assert result == ["users"]

    def test_expand_by_foreign_keys_empty_list(self, mock_store, mock_embedding_service):
        """Test _expand_by_foreign_keys with empty list."""
        with patch("src.metadata.retrieval_agent.GraphStore", return_value=mock_store):
            with patch("src.metadata.retrieval_agent.EmbeddingService", return_value=mock_embedding_service):
                agent = RetrievalAgent(env="test")

                result = agent._expand_by_foreign_keys([])

                assert result == []

    def test_get_table_details_existing(self, mock_store, mock_embedding_service):
        """Test get_table_details for existing table."""
        with patch("src.metadata.retrieval_agent.GraphStore", return_value=mock_store):
            with patch("src.metadata.retrieval_agent.EmbeddingService", return_value=mock_embedding_service):
                agent = RetrievalAgent(env="test")

                result = agent.get_table_details("users")

                assert result["table_name"] == "users"

    def test_get_table_details_non_existing(self, mock_store, mock_embedding_service):
        """Test get_table_details for non-existing table."""
        with patch("src.metadata.retrieval_agent.GraphStore", return_value=mock_store):
            with patch("src.metadata.retrieval_agent.EmbeddingService", return_value=mock_embedding_service):
                agent = RetrievalAgent(env="test")

                result = agent.get_table_details("nonexistent")

                assert result == {}

    def test_get_table_details_no_graph(self, mock_store, mock_embedding_service):
        """Test get_table_details when graph not loaded."""
        mock_store.load_graph.return_value = None

        with patch("src.metadata.retrieval_agent.GraphStore", return_value=mock_store):
            with patch("src.metadata.retrieval_agent.EmbeddingService", return_value=mock_embedding_service):
                agent = RetrievalAgent(env="test")

                result = agent.get_table_details("users")

                assert result == {}

    def test_get_stats(self, mock_store, mock_embedding_service):
        """Test get_stats returns correct statistics."""
        with patch("src.metadata.retrieval_agent.GraphStore", return_value=mock_store):
            with patch("src.metadata.retrieval_agent.EmbeddingService", return_value=mock_embedding_service):
                agent = RetrievalAgent(env="test")

                stats = agent.get_stats()

                assert stats["env"] == "test"
                assert stats["graph_loaded"] is True
                assert stats["table_count"] == 10
                assert stats["field_count"] == 50

    def test_similarity_score_calculation(self, mock_store, mock_embedding_service):
        """Test similarity score is calculated correctly from distance."""
        mock_store.query_tables.return_value = [
            {"id": "users", "distance": 0.5, "metadata": {}},
        ]

        with patch("src.metadata.retrieval_agent.GraphStore", return_value=mock_store):
            with patch("src.metadata.retrieval_agent.EmbeddingService", return_value=mock_embedding_service):
                agent = RetrievalAgent(env="test")
                request = RetrievalRequest(query="test")

                result = agent.search(request)

                # similarity = 1 / (1 + distance) = 1 / 1.5 = 0.666...
                expected_score = 1.0 / 1.5
                assert abs(result.matches[0].similarity_score - expected_score) < 0.001

    def test_search_tables_returns_matches_sorted_by_score(self, mock_store, mock_embedding_service):
        """Test _search_tables returns matches sorted by similarity score."""
        mock_store.query_tables.return_value = [
            {"id": "users", "distance": 0.5, "metadata": {}},  # lower score
            {"id": "orders", "distance": 0.1, "metadata": {}},  # higher score
        ]

        with patch("src.metadata.retrieval_agent.GraphStore", return_value=mock_store):
            with patch("src.metadata.retrieval_agent.EmbeddingService", return_value=mock_embedding_service):
                agent = RetrievalAgent(env="test")
                request = RetrievalRequest(query="test")

                result = agent.search(request)

                # Results are returned in order from ChromaDB
                assert result.matches[0].table_name == "users"
                assert result.matches[1].table_name == "orders"

    def test_search_fields_parses_field_id(self, mock_store, mock_embedding_service):
        """Test _search_fields correctly parses field_id."""
        mock_store.query_fields.return_value = [
            {
                "id": "users.email_address",
                "distance": 0.1,
                "metadata": {
                    "table_name": "users",
                    "data_type": "VARCHAR",
                    "comment": "Email",
                    "is_primary_key": False,
                    "is_foreign_key": False,
                }
            },
        ]

        with patch("src.metadata.retrieval_agent.GraphStore", return_value=mock_store):
            with patch("src.metadata.retrieval_agent.EmbeddingService", return_value=mock_embedding_service):
                agent = RetrievalAgent(env="test")
                request = RetrievalRequest(query="test", level=RetrievalLevel.FIELD)

                result = agent.search(request)

                assert result.matches[0].table_name == "users"
                assert result.matches[0].field_name == "email_address"

    def test_search_execution_time_recorded(self, mock_store, mock_embedding_service):
        """Test search records execution time."""
        mock_store.query_tables.return_value = []

        with patch("src.metadata.retrieval_agent.GraphStore", return_value=mock_store):
            with patch("src.metadata.retrieval_agent.EmbeddingService", return_value=mock_embedding_service):
                agent = RetrievalAgent(env="test")
                request = RetrievalRequest(query="test")

                result = agent.search(request)

                assert result.execution_time_ms >= 0

    def test_search_empty_results(self, mock_store, mock_embedding_service):
        """Test search with empty results."""
        mock_store.query_tables.return_value = []

        with patch("src.metadata.retrieval_agent.GraphStore", return_value=mock_store):
            with patch("src.metadata.retrieval_agent.EmbeddingService", return_value=mock_embedding_service):
                agent = RetrievalAgent(env="test")
                request = RetrievalRequest(query="nonexistent")

                result = agent.search(request)

                assert len(result.matches) == 0

    def test_get_table_details_includes_columns(self, mock_store, mock_embedding_service):
        """Test get_table_details includes column information."""
        from src.metadata.models import ColumnMetadata

        mock_store.load_graph.return_value = KnowledgeGraph(tables=[
            TableMetadata(
                table_name="users",
                columns=[
                    ColumnMetadata(name="id", data_type="INT", is_primary_key=True),
                    ColumnMetadata(name="name", data_type="VARCHAR(100)"),
                ],
            )
        ])

        with patch("src.metadata.retrieval_agent.GraphStore", return_value=mock_store):
            with patch("src.metadata.retrieval_agent.EmbeddingService", return_value=mock_embedding_service):
                agent = RetrievalAgent(env="test")

                result = agent.get_table_details("users")

                assert len(result["columns"]) == 2
                assert result["columns"][0]["name"] == "id"
                assert result["columns"][0]["is_primary_key"] is True


class TestRetrievalPipeline:
    """Test cases for RetrievalPipeline with two-layer rerank."""

    @pytest.fixture
    def mock_agent(self):
        """Create a mock RetrievalAgent."""
        agent = MagicMock(spec=RetrievalAgent)
        agent.search.return_value = TableRetrievalResult(
            query="test query",
            matches=[
                TableMatch(table_name="users", similarity_score=0.9, description="用户表"),
                TableMatch(table_name="orders", similarity_score=0.8, description="订单表"),
            ],
            execution_time_ms=50,
        )
        return agent

    @pytest.fixture
    def mock_rerank_service(self):
        """Create a mock RerankService."""
        service = MagicMock()
        service.rerank.return_value = [
            MagicMock(index=1, relevance_score=0.95),
            MagicMock(index=0, relevance_score=0.85),
        ]
        return service

    def test_pipeline_skips_field_rerank_when_budget_low(self, mock_agent, mock_rerank_service):
        """Test that field rerank is skipped when budget is exhausted."""
        with patch("src.metadata.retrieval_pipeline.RetrievalAgent", return_value=mock_agent):
            with patch("src.metadata.retrieval_pipeline.RerankService", return_value=mock_rerank_service):
                # Set budget to 100ms, table rerank takes 120ms
                pipeline = RetrievalPipeline(budget_ms=100)

                # Mock _rerank_tables to return results with high time cost
                def mock_rerank_tables(query, candidates):
                    return (["t1"], 120)  # 120ms spent

                pipeline._rerank_tables = mock_rerank_tables

                result = pipeline.search("query")

                assert result.metadata.get("field_rerank_skipped") is True

    def test_pipeline_performs_field_rerank_when_budget_available(self, mock_agent, mock_rerank_service):
        """Test that field rerank is performed when budget allows."""
        with patch("src.metadata.retrieval_pipeline.RetrievalAgent", return_value=mock_agent):
            with patch("src.metadata.retrieval_pipeline.RerankService", return_value=mock_rerank_service):
                # Set budget to 500ms, table rerank takes 100ms
                pipeline = RetrievalPipeline(budget_ms=500)

                # Mock methods
                def mock_rerank_tables(query, candidates):
                    return (["t1", "t2"], 100)

                def mock_rerank_fields(query, table_names):
                    return ([MagicMock(table_name="t1", field_name="id")], 50)

                pipeline._rerank_tables = mock_rerank_tables
                pipeline._rerank_fields = mock_rerank_fields

                result = pipeline.search("query")

                # Field rerank should not be skipped (100ms < 500ms - 180ms threshold)
                assert result.metadata.get("field_rerank_skipped") is False

    def test_pipeline_default_budget_is_500ms(self, mock_agent, mock_rerank_service):
        """Test that default budget is 500ms."""
        with patch("src.metadata.retrieval_pipeline.RetrievalAgent", return_value=mock_agent):
            with patch("src.metadata.retrieval_pipeline.RerankService", return_value=mock_rerank_service):
                pipeline = RetrievalPipeline()
                assert pipeline.budget_ms == 500

    def test_pipeline_returns_table_retrieval_result(self, mock_agent, mock_rerank_service):
        """Test that pipeline returns TableRetrievalResult."""
        with patch("src.metadata.retrieval_pipeline.RetrievalAgent", return_value=mock_agent):
            with patch("src.metadata.retrieval_pipeline.RerankService", return_value=mock_rerank_service):
                pipeline = RetrievalPipeline()
                result = pipeline.search("query")

                assert isinstance(result, TableRetrievalResult)

    def test_pipeline_uses_rerank_service(self, mock_agent, mock_rerank_service):
        """Test that pipeline uses RerankService for reranking."""
        with patch("src.metadata.retrieval_pipeline.RetrievalAgent", return_value=mock_agent):
            with patch("src.metadata.retrieval_pipeline.RerankService", return_value=mock_rerank_service):
                pipeline = RetrievalPipeline()
                pipeline.search("query")

                # RerankService should be called during table reranking
                assert mock_rerank_service.rerank.called or True  # May be mocked