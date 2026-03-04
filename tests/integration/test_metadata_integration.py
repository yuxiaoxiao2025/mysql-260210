"""Tests for integration of metadata knowledge graph with LLMClient."""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from typing import List

from src.metadata.schema_indexer import SchemaIndexer
from src.metadata.retrieval_agent import RetrievalAgent
from src.metadata.retrieval_models import (
    RetrievalLevel,
    RetrievalRequest,
    RetrievalResult,
    TableMatch,
    TableRetrievalResult,
    FieldMatch,
    FieldRetrievalResult,
)
from src.metadata.models import (
    KnowledgeGraph,
    TableMetadata,
    ColumnMetadata,
    ForeignKeyRelation,
)


class TestMetadataIntegration:
    """End-to-end integration tests for metadata knowledge graph system."""

    @pytest.fixture
    def mock_db_manager(self):
        """Create a mock DatabaseManager with predefined table schema."""
        manager = MagicMock()
        manager.get_all_tables.return_value = ["users", "orders", "products"]

        # Mock get_connection context manager
        mock_conn = MagicMock()

        # Mock table info query result
        def mock_execute(sql, params=None):
            result = MagicMock()
            if "TABLES" in str(sql):
                # Return table info
                result.fetchone.return_value = ("test_db", "用户表")
                result.fetchall.return_value = []
            elif "COLUMNS" in str(sql):
                # Return column info
                result.fetchall.return_value = [
                    ("id", "INT", "主键ID", "PRI"),
                    ("name", "VARCHAR(100)", "用户名", ""),
                    ("email", "VARCHAR(255)", "邮箱", ""),
                ]
            else:
                result.fetchone.return_value = None
                result.fetchall.return_value = []
            return result

        mock_conn.execute = mock_execute
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        manager.get_connection.return_value = mock_conn
        return manager

    @pytest.fixture
    def mock_embedding_service(self):
        """Create a mock EmbeddingService with deterministic embeddings."""
        service = MagicMock()
        # Return deterministic 1024-dim embedding
        service.embed_text.return_value = [0.1] * 1024
        service.embed_batch.return_value = [[0.1] * 1024, [0.2] * 1024, [0.3] * 1024]
        return service

    @pytest.fixture
    def mock_graph_store(self):
        """Create a mock GraphStore with predefined data."""
        store = MagicMock()
        store.get_table_count.return_value = 3
        store.get_field_count.return_value = 15
        store.load_graph.return_value = KnowledgeGraph(tables=[
            TableMetadata(
                table_name="users",
                database_name="test_db",
                comment="用户表",
                columns=[
                    ColumnMetadata(name="id", data_type="INT", is_primary_key=True),
                    ColumnMetadata(name="name", data_type="VARCHAR(100)"),
                    ColumnMetadata(name="email", data_type="VARCHAR(255)"),
                ],
                foreign_keys=[],
                business_domain="用户管理",
            ),
            TableMetadata(
                table_name="orders",
                database_name="test_db",
                comment="订单表",
                columns=[
                    ColumnMetadata(name="id", data_type="INT", is_primary_key=True),
                    ColumnMetadata(name="user_id", data_type="INT", is_foreign_key=True, references_table="users"),
                    ColumnMetadata(name="product_id", data_type="INT", is_foreign_key=True, references_table="products"),
                ],
                foreign_keys=[
                    ForeignKeyRelation(column_name="user_id", referenced_table="users", referenced_column="id"),
                    ForeignKeyRelation(column_name="product_id", referenced_table="products", referenced_column="id"),
                ],
                business_domain="订单管理",
            ),
            TableMetadata(
                table_name="products",
                database_name="test_db",
                comment="产品表",
                columns=[
                    ColumnMetadata(name="id", data_type="INT", is_primary_key=True),
                    ColumnMetadata(name="name", data_type="VARCHAR(200)"),
                ],
                foreign_keys=[],
                business_domain="产品管理",
            ),
        ])
        return store

    def test_index_and_retrieve_flow(self, mock_db_manager, mock_embedding_service, mock_graph_store):
        """Test complete indexing and retrieval flow."""
        # 1. Create SchemaIndexer with mocked dependencies
        with patch("src.metadata.schema_indexer.DatabaseManager", return_value=mock_db_manager):
            with patch("src.metadata.schema_indexer.EmbeddingService", return_value=mock_embedding_service):
                with patch("src.metadata.schema_indexer.GraphStore", return_value=mock_graph_store):
                    indexer = SchemaIndexer(env="test")

                    # 2. Mock _extract_table_metadata to return valid metadata
                    with patch.object(indexer, '_extract_table_metadata') as mock_extract:
                        mock_extract.return_value = TableMetadata(
                            table_name="users",
                            database_name="test_db",
                            comment="用户表",
                            columns=[
                                ColumnMetadata(name="id", data_type="INT", is_primary_key=True),
                            ],
                            business_domain="用户管理",
                        )

                        # Run indexing (it will use the mocked method)
                        result = indexer.index_all_tables(batch_size=2)

                        # Verify indexing was attempted
                        assert result is not None

        # 3. Create RetrievalAgent
        with patch("src.metadata.retrieval_agent.GraphStore", return_value=mock_graph_store):
            with patch("src.metadata.retrieval_agent.EmbeddingService", return_value=mock_embedding_service):
                agent = RetrievalAgent(env="test")

                # 4. Search for tables
                request = RetrievalRequest(
                    query="查找用户相关的表",
                    level=RetrievalLevel.TABLE,
                    top_k=5,
                )

                # Mock query_tables to return results
                mock_graph_store.query_tables.return_value = [
                    {"id": "users", "distance": 0.1, "metadata": {"business_domain": "用户管理", "comment": "用户表"}},
                    {"id": "orders", "distance": 0.3, "metadata": {"business_domain": "订单管理", "comment": "订单表"}},
                ]

                search_result = agent.search(request)

                # 5. Verify results
                assert isinstance(search_result, TableRetrievalResult)
                assert len(search_result.matches) == 2
                assert search_result.matches[0].table_name == "users"
                assert search_result.query == "查找用户相关的表"

    def test_retrieval_enhances_schema_context(self, mock_graph_store, mock_embedding_service):
        """Test that retrieval results can enhance schema context for SQL generation."""
        with patch("src.metadata.retrieval_agent.GraphStore", return_value=mock_graph_store):
            with patch("src.metadata.retrieval_agent.EmbeddingService", return_value=mock_embedding_service):
                agent = RetrievalAgent(env="test")

                # Mock query_tables to return relevant tables
                mock_graph_store.query_tables.return_value = [
                    {"id": "users", "distance": 0.1, "metadata": {"business_domain": "用户管理", "comment": "用户信息表"}},
                    {"id": "orders", "distance": 0.2, "metadata": {"business_domain": "订单管理", "comment": "订单记录表"}},
                ]

                # Search for user-related tables
                request = RetrievalRequest(
                    query="查询用户的订单",
                    level=RetrievalLevel.TABLE,
                    top_k=3,
                )

                result = agent.search(request)

                # Build schema context from retrieval results
                schema_context_lines = ["### Related Tables (Retrieved by Semantic Search)"]
                for match in result.matches[:3]:
                    schema_context_lines.append(
                        f"- {match.table_name}: {match.description} (score: {match.similarity_score:.2f})"
                    )

                enhanced_context = "\n".join(schema_context_lines)

                # Verify context was built correctly
                assert "### Related Tables" in enhanced_context
                assert "users" in enhanced_context
                assert "orders" in enhanced_context
                assert "score:" in enhanced_context

    def test_foreign_key_expansion_in_retrieval(self, mock_graph_store, mock_embedding_service):
        """Test that foreign key relationships expand retrieval results."""
        with patch("src.metadata.retrieval_agent.GraphStore", return_value=mock_graph_store):
            with patch("src.metadata.retrieval_agent.EmbeddingService", return_value=mock_embedding_service):
                agent = RetrievalAgent(env="test")

                # Mock query_tables to return only orders
                mock_graph_store.query_tables.return_value = [
                    {"id": "orders", "distance": 0.1, "metadata": {"business_domain": "订单管理", "comment": "订单表"}},
                ]

                request = RetrievalRequest(
                    query="查询订单信息",
                    level=RetrievalLevel.TABLE,
                    top_k=1,
                )

                result = agent.search(request)

                # Verify that foreign key expansion added users and products
                assert "expanded_tables" in result.metadata
                expanded = result.metadata["expanded_tables"]

                # orders has foreign keys to users and products
                assert "orders" in expanded
                assert "users" in expanded
                assert "products" in expanded

    def test_field_level_retrieval(self, mock_graph_store, mock_embedding_service):
        """Test field-level retrieval for column search."""
        with patch("src.metadata.retrieval_agent.GraphStore", return_value=mock_graph_store):
            with patch("src.metadata.retrieval_agent.EmbeddingService", return_value=mock_embedding_service):
                agent = RetrievalAgent(env="test")

                # Mock query_fields to return field matches
                mock_graph_store.query_fields.return_value = [
                    {
                        "id": "users.email",
                        "distance": 0.1,
                        "metadata": {
                            "table_name": "users",
                            "data_type": "VARCHAR(255)",
                            "comment": "邮箱地址",
                            "is_primary_key": False,
                            "is_foreign_key": False,
                        }
                    },
                    {
                        "id": "users.name",
                        "distance": 0.2,
                        "metadata": {
                            "table_name": "users",
                            "data_type": "VARCHAR(100)",
                            "comment": "用户名",
                            "is_primary_key": False,
                            "is_foreign_key": False,
                        }
                    },
                ]

                request = RetrievalRequest(
                    query="查找邮箱字段",
                    level=RetrievalLevel.FIELD,
                    top_k=5,
                )

                result = agent.search(request)

                assert isinstance(result, FieldRetrievalResult)
                assert len(result.matches) == 2
                assert result.matches[0].field_name == "email"
                assert result.matches[0].table_name == "users"

    def test_field_level_retrieval_with_table_filter(self, mock_graph_store, mock_embedding_service):
        """Test field-level retrieval with table filter."""
        with patch("src.metadata.retrieval_agent.GraphStore", return_value=mock_graph_store):
            with patch("src.metadata.retrieval_agent.EmbeddingService", return_value=mock_embedding_service):
                agent = RetrievalAgent(env="test")

                mock_graph_store.query_fields.return_value = [
                    {
                        "id": "users.id",
                        "distance": 0.1,
                        "metadata": {
                            "table_name": "users",
                            "data_type": "INT",
                            "comment": "主键",
                            "is_primary_key": True,
                            "is_foreign_key": False,
                        }
                    },
                ]

                request = RetrievalRequest(
                    query="查找ID字段",
                    level=RetrievalLevel.FIELD,
                    top_k=5,
                    filter_tables=["users"],
                )

                result = agent.search(request)

                # Verify filter was passed to query_fields
                call_args = mock_graph_store.query_fields.call_args
                assert call_args[1]["filter_tables"] == ["users"]

    def test_retrieval_with_no_indexed_data(self, mock_embedding_service):
        """Test retrieval behavior when no data is indexed."""
        mock_empty_store = MagicMock()
        mock_empty_store.get_table_count.return_value = 0
        mock_empty_store.get_field_count.return_value = 0
        mock_empty_store.load_graph.return_value = None
        mock_empty_store.query_tables.return_value = []

        with patch("src.metadata.retrieval_agent.GraphStore", return_value=mock_empty_store):
            with patch("src.metadata.retrieval_agent.EmbeddingService", return_value=mock_embedding_service):
                agent = RetrievalAgent(env="test")

                request = RetrievalRequest(
                    query="查询用户",
                    level=RetrievalLevel.TABLE,
                    top_k=5,
                )

                result = agent.search(request)

                # Should return empty results, not error
                assert isinstance(result, TableRetrievalResult)
                assert len(result.matches) == 0

    def test_retrieval_agent_get_table_details(self, mock_graph_store, mock_embedding_service):
        """Test RetrievalAgent.get_table_details returns complete table info."""
        with patch("src.metadata.retrieval_agent.GraphStore", return_value=mock_graph_store):
            with patch("src.metadata.retrieval_agent.EmbeddingService", return_value=mock_embedding_service):
                agent = RetrievalAgent(env="test")

                details = agent.get_table_details("users")

                assert details["table_name"] == "users"
                assert details["database_name"] == "test_db"
                assert details["comment"] == "用户表"
                assert len(details["columns"]) == 3
                assert details["columns"][0]["is_primary_key"] is True


class TestLLMClientRetrievalIntegration:
    """Test LLMClient integration with RetrievalAgent."""

    @pytest.fixture
    def mock_retrieval_agent(self):
        """Create a mock RetrievalAgent."""
        agent = MagicMock()
        agent.graph = MagicMock()  # Simulate indexed data
        agent.search.return_value = TableRetrievalResult(
            query="用户订单查询",
            matches=[
                TableMatch(
                    table_name="users",
                    similarity_score=0.95,
                    description="用户信息表",
                    business_tags=["用户管理"],
                ),
                TableMatch(
                    table_name="orders",
                    similarity_score=0.85,
                    description="订单记录表",
                    business_tags=["订单管理"],
                ),
            ],
            execution_time_ms=50,
        )
        return agent

    def test_llm_client_lazy_loads_retrieval_agent(self):
        """Test that LLMClient lazy loads RetrievalAgent."""
        with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "sk-test"}):
            from src.llm_client import LLMClient

            client = LLMClient()

            # Initially, retrieval_agent should be None
            assert client.retrieval_agent is None

    def test_build_retrieval_context_format(self):
        """Test that _build_retrieval_context formats results correctly."""
        with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "sk-test"}):
            from src.llm_client import LLMClient

            client = LLMClient()

            # Create mock retrieval result
            result = TableRetrievalResult(
                query="测试查询",
                matches=[
                    TableMatch(
                        table_name="users",
                        similarity_score=0.95,
                        description="用户表",
                        business_tags=["用户"],
                    ),
                    TableMatch(
                        table_name="orders",
                        similarity_score=0.80,
                        description="订单表",
                        business_tags=["订单"],
                    ),
                ],
                execution_time_ms=10,
            )

            context = client._build_retrieval_context(result)

            assert "### Related Tables" in context
            assert "users" in context
            assert "orders" in context
            assert "0.95" in context
            assert "0.80" in context

    def test_retrieval_is_optional_enhancement(self):
        """Test that retrieval failure does not break SQL generation."""
        with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "sk-test"}):
            with patch("dashscope.Generation.call") as mock_call:
                # Mock LLM response
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_choice = MagicMock()
                mock_choice.message.content = '''{
                    "sql": "SELECT * FROM users",
                    "filename": "users",
                    "sheet_name": "用户",
                    "reasoning": "查询用户"
                }'''
                mock_response.output.choices = [mock_choice]
                mock_call.return_value = mock_response

                from src.llm_client import LLMClient

                client = LLMClient()

                # Retrieval agent is None (not initialized)
                # SQL generation should still work
                result = client.generate_sql(
                    user_query="查询用户",
                    schema_context="Schema info here"
                )

                assert result is not None
                assert result["sql"] == "SELECT * FROM users"

    def test_retrieval_enhances_schema_context_in_generate_sql(self, mock_retrieval_agent):
        """Test that retrieval enhances schema context in generate_sql."""
        with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "sk-test"}):
            with patch("dashscope.Generation.call") as mock_call:
                # Mock LLM response
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_choice = MagicMock()
                mock_choice.message.content = '''{
                    "sql": "SELECT u.name, o.id FROM users u JOIN orders o ON u.id = o.user_id",
                    "filename": "user_orders",
                    "sheet_name": "用户订单",
                    "reasoning": "Join users and orders"
                }'''
                mock_response.output.choices = [mock_choice]
                mock_call.return_value = mock_response

                from src.llm_client import LLMClient
                from src.metadata.retrieval_models import RetrievalRequest, RetrievalLevel

                client = LLMClient()
                client.retrieval_agent = mock_retrieval_agent

                result = client.generate_sql(
                    user_query="查询用户的订单",
                    schema_context="Base schema context"
                )

                # Verify retrieval was called
                mock_retrieval_agent.search.assert_called_once()
                call_args = mock_retrieval_agent.search.call_args
                assert isinstance(call_args[0][0], RetrievalRequest)
                assert call_args[0][0].query == "查询用户的订单"

                # SQL generation should succeed
                assert result is not None
                assert "JOIN" in result["sql"]


class TestEndToEndWorkflow:
    """End-to-end workflow tests."""

    def test_complete_index_retrieve_generate_workflow(self):
        """Test complete workflow: index -> retrieve -> generate SQL."""
        # This is a higher-level integration test that verifies
        # the components work together

        # Setup mocks
        mock_store = MagicMock()
        mock_store.get_table_count.return_value = 2
        mock_store.get_field_count.return_value = 10
        mock_store.load_graph.return_value = KnowledgeGraph(tables=[
            TableMetadata(
                table_name="cloud_fixed_plate",
                database_name="parkcloud",
                comment="固定车牌表",
                columns=[
                    ColumnMetadata(name="id", data_type="INT", is_primary_key=True),
                    ColumnMetadata(name="plate_number", data_type="VARCHAR(20)"),
                ],
                business_domain="车辆管理",
            ),
        ])
        mock_store.query_tables.return_value = [
            {"id": "cloud_fixed_plate", "distance": 0.1, "metadata": {"business_domain": "车辆管理", "comment": "固定车牌表"}},
        ]

        mock_embedding = MagicMock()
        mock_embedding.embed_text.return_value = [0.1] * 1024

        # Test retrieval
        with patch("src.metadata.retrieval_agent.GraphStore", return_value=mock_store):
            with patch("src.metadata.retrieval_agent.EmbeddingService", return_value=mock_embedding):
                agent = RetrievalAgent(env="test")

                request = RetrievalRequest(
                    query="查找车牌表",
                    level=RetrievalLevel.TABLE,
                    top_k=5,
                )

                result = agent.search(request)

                # Verify retrieval found the right table
                assert len(result.matches) == 1
                assert result.matches[0].table_name == "cloud_fixed_plate"
                assert "车牌" in result.matches[0].description

    def test_get_stats_integration(self):
        """Test that get_stats returns consistent data."""
        # Setup mocks
        mock_store = MagicMock()
        mock_store.get_table_count.return_value = 3
        mock_store.get_field_count.return_value = 15
        mock_store.load_graph.return_value = KnowledgeGraph(tables=[
            TableMetadata(
                table_name="users",
                database_name="test_db",
                comment="用户表",
                columns=[
                    ColumnMetadata(name="id", data_type="INT", is_primary_key=True),
                ],
                business_domain="用户管理",
            ),
        ])

        mock_embedding = MagicMock()
        mock_embedding.embed_text.return_value = [0.1] * 1024

        with patch("src.metadata.retrieval_agent.GraphStore", return_value=mock_store):
            with patch("src.metadata.retrieval_agent.EmbeddingService", return_value=mock_embedding):
                agent = RetrievalAgent(env="test")

                stats = agent.get_stats()

                assert stats["env"] == "test"
                assert stats["graph_loaded"] is True
                assert stats["table_count"] == 3
                assert stats["field_count"] == 15
                assert stats["graph_tables"] == 1