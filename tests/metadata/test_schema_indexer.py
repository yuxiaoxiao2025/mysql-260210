"""Tests for SchemaIndexer in the metadata knowledge graph system."""

import json
import pytest
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime

from src.metadata.schema_indexer import SchemaIndexer
from src.metadata.models import (
    ColumnMetadata,
    ForeignKeyRelation,
    TableMetadata,
    KnowledgeGraph,
    IndexProgress,
    IndexResult,
)


class TestSchemaIndexer:
    """Test cases for SchemaIndexer."""

    @pytest.fixture
    def mock_db_manager(self):
        """Create a mock DatabaseManager."""
        manager = MagicMock()
        manager.get_all_tables.return_value = ["users", "orders"]
        return manager

    @pytest.fixture
    def mock_embedding_service(self):
        """Create a mock EmbeddingService."""
        service = MagicMock()
        service.embed_text.return_value = [0.1] * 1024
        service.embed_batch.return_value = [[0.1] * 1024, [0.2] * 1024]
        return service

    @pytest.fixture
    def mock_graph_store(self):
        """Create a mock GraphStore."""
        store = MagicMock()
        store.load_graph.return_value = None
        return store

    @pytest.fixture
    def mock_domain_classifier(self):
        """Create a mock DomainClassifier."""
        classifier = MagicMock()
        classifier.classify.return_value = "用户"
        return classifier

    def test_init_with_dependencies(
        self, mock_db_manager, mock_embedding_service, mock_graph_store
    ):
        """Test SchemaIndexer initialization with injected dependencies."""
        indexer = SchemaIndexer(
            db_manager=mock_db_manager,
            embedding_service=mock_embedding_service,
            graph_store=mock_graph_store,
            env="test",
        )

        assert indexer.db_manager == mock_db_manager
        assert indexer.embedding_service == mock_embedding_service
        assert indexer.graph_store == mock_graph_store
        assert indexer.env == "test"

    def test_index_all_tables_success(
        self, mock_db_manager, mock_embedding_service, mock_graph_store
    ):
        """Test index_all_tables completes successfully."""
        # Mock database query results
        mock_conn = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.execute.return_value.scalar.return_value = "mydb"

        # Mock table info query
        mock_conn.execute.return_value.fetchone.return_value = ("mydb", "User table")
        mock_conn.execute.return_value.fetchall.return_value = [
            ("id", "INT", "Primary key", "PRI"),
            ("name", "VARCHAR(100)", "User name", ""),
        ]

        with patch.object(SchemaIndexer, "_extract_foreign_keys", return_value=[]):
            indexer = SchemaIndexer(
                db_manager=mock_db_manager,
                embedding_service=mock_embedding_service,
                graph_store=mock_graph_store,
                env="test",
            )

            result = indexer.index_all_tables(batch_size=1)

            assert result.success is True
            assert result.total_tables == 2
            mock_graph_store.save_graph.assert_called_once()

    def test_index_all_tables_empty_database(
        self, mock_db_manager, mock_embedding_service, mock_graph_store
    ):
        """Test index_all_tables with empty database."""
        mock_db_manager.get_all_tables.return_value = []
        mock_conn = MagicMock()
        mock_conn.execute.return_value.scalar.return_value = "mydb"
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn

        indexer = SchemaIndexer(
            db_manager=mock_db_manager,
            embedding_service=mock_embedding_service,
            graph_store=mock_graph_store,
            env="test",
        )

        result = indexer.index_all_tables()

        assert result.success is True
        assert result.total_tables == 0
        assert result.indexed_tables == 0

    def test_index_all_tables_db_error(
        self, mock_db_manager, mock_embedding_service, mock_graph_store
    ):
        """Test index_all_tables handles database error."""
        mock_db_manager.get_all_tables.side_effect = Exception("Connection failed")
        mock_conn = MagicMock()
        mock_conn.execute.return_value.scalar.return_value = "mydb"
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn

        indexer = SchemaIndexer(
            db_manager=mock_db_manager,
            embedding_service=mock_embedding_service,
            graph_store=mock_graph_store,
            env="test",
        )

        result = indexer.index_all_tables()

        assert result.success is False
        assert result.total_tables == 0

    def test_generate_schema_text(self, mock_db_manager, mock_embedding_service, mock_graph_store):
        """Test _generate_schema_text creates correct text."""
        indexer = SchemaIndexer(
            db_manager=mock_db_manager,
            embedding_service=mock_embedding_service,
            graph_store=mock_graph_store,
            env="test",
        )

        columns = [
            ColumnMetadata(name="id", data_type="INT", is_primary_key=True),
            ColumnMetadata(
                name="dept_id",
                data_type="INT",
                is_foreign_key=True,
                references_table="departments",
            ),
        ]

        result = indexer._generate_schema_text(
            table_name="users",
            comment="User table",
            columns=columns,
            business_domain="用户",
        )

        assert "表名：users" in result
        assert "描述：User table" in result
        assert "id(主键)" in result
        assert "dept_id(外键->departments)" in result
        assert "业务域：用户" in result

    def test_generate_schema_text_no_keys(self, mock_db_manager, mock_embedding_service, mock_graph_store):
        """Test _generate_schema_text with no key columns."""
        indexer = SchemaIndexer(
            db_manager=mock_db_manager,
            embedding_service=mock_embedding_service,
            graph_store=mock_graph_store,
            env="test",
        )

        columns = [
            ColumnMetadata(name="name", data_type="VARCHAR(100)"),
        ]

        result = indexer._generate_schema_text(
            table_name="logs",
            comment="",
            columns=columns,
            business_domain="其他",
        )

        assert "关键字段：无" in result

    def test_generate_field_schema_text(self, mock_db_manager, mock_embedding_service, mock_graph_store):
        """Test _generate_field_schema_text creates correct text."""
        indexer = SchemaIndexer(
            db_manager=mock_db_manager,
            embedding_service=mock_embedding_service,
            graph_store=mock_graph_store,
            env="test",
        )

        column = ColumnMetadata(name="email", data_type="VARCHAR(255)", comment="Email address")

        result = indexer._generate_field_schema_text("users", column)

        assert result == "users.email: Email address"

    def test_generate_field_schema_text_no_comment(self, mock_db_manager, mock_embedding_service, mock_graph_store):
        """Test _generate_field_schema_text with no comment."""
        indexer = SchemaIndexer(
            db_manager=mock_db_manager,
            embedding_service=mock_embedding_service,
            graph_store=mock_graph_store,
            env="test",
        )

        column = ColumnMetadata(name="created_at", data_type="DATETIME")

        result = indexer._generate_field_schema_text("users", column)

        assert result == "users.created_at: 无描述"

    def test_generate_tags(self, mock_db_manager, mock_embedding_service, mock_graph_store):
        """Test _generate_tags creates correct tags."""
        indexer = SchemaIndexer(
            db_manager=mock_db_manager,
            embedding_service=mock_embedding_service,
            graph_store=mock_graph_store,
            env="test",
        )

        columns = [
            ColumnMetadata(name="id", data_type="INT", is_primary_key=True),
            ColumnMetadata(name="created_time", data_type="DATETIME"),
            ColumnMetadata(name="status", data_type="INT"),
        ]

        result = indexer._generate_tags(
            table_name="users",
            comment="",
            columns=columns,
            business_domain="用户",
        )

        assert "用户" in result
        assert "有主键" in result
        assert "时间相关" in result
        assert "状态相关" in result

    def test_generate_tags_other_domain(self, mock_db_manager, mock_embedding_service, mock_graph_store):
        """Test _generate_tags for '其他' domain doesn't add domain tag."""
        indexer = SchemaIndexer(
            db_manager=mock_db_manager,
            embedding_service=mock_embedding_service,
            graph_store=mock_graph_store,
            env="test",
        )

        columns = [ColumnMetadata(name="data", data_type="TEXT")]

        result = indexer._generate_tags(
            table_name="temp",
            comment="",
            columns=columns,
            business_domain="其他",
        )

        assert "其他" not in result

    def test_save_progress(self, mock_db_manager, mock_embedding_service, mock_graph_store):
        """Test _save_progress writes to file."""
        temp_dir = Path(tempfile.mkdtemp(dir=str(Path(".pytest_tmp"))))
        progress_file = temp_dir / "progress.json"

        try:
            with patch.object(SchemaIndexer, "__init__", lambda self, **kwargs: None):
                indexer = SchemaIndexer.__new__(SchemaIndexer)
                indexer.progress_file = progress_file

                progress = IndexProgress(
                    status="in_progress",
                    total_tables=10,
                    indexed_tables=5,
                )

                indexer._save_progress(progress)

                assert progress_file.exists()
                with open(progress_file) as f:
                    data = json.load(f)
                assert data["status"] == "in_progress"
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_load_progress_existing_file(self, mock_db_manager, mock_embedding_service, mock_graph_store):
        """Test _load_progress reads from existing file."""
        temp_dir = Path(tempfile.mkdtemp(dir=str(Path(".pytest_tmp"))))
        progress_file = temp_dir / "progress.json"
        progress_data = {
            "status": "completed",
            "total_tables": 10,
            "indexed_tables": 10,
            "current_batch": 1,
            "errors": [],
            "statistics": {},
        }
        try:
            with open(progress_file, "w") as f:
                json.dump(progress_data, f)

            with patch.object(SchemaIndexer, "__init__", lambda self, **kwargs: None):
                indexer = SchemaIndexer.__new__(SchemaIndexer)
                indexer.progress_file = progress_file

                result = indexer._load_progress()

                assert result.status == "completed"
                assert result.total_tables == 10
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_load_progress_no_file(self, mock_db_manager, mock_embedding_service, mock_graph_store):
        """Test _load_progress creates new progress when no file exists."""
        temp_dir = Path(tempfile.mkdtemp(dir=str(Path(".pytest_tmp"))))
        progress_file = temp_dir / "nonexistent.json"

        try:
            with patch.object(SchemaIndexer, "__init__", lambda self, **kwargs: None):
                indexer = SchemaIndexer.__new__(SchemaIndexer)
                indexer.progress_file = progress_file

                result = indexer._load_progress()

                assert result.status == "pending"
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_load_progress_invalid_json(self, mock_db_manager, mock_embedding_service, mock_graph_store):
        """Test _load_progress handles invalid JSON."""
        temp_dir = Path(tempfile.mkdtemp(dir=str(Path(".pytest_tmp"))))
        progress_file = temp_dir / "invalid.json"
        try:
            with open(progress_file, "w") as f:
                f.write("invalid json {{{")

            with patch.object(SchemaIndexer, "__init__", lambda self, **kwargs: None):
                indexer = SchemaIndexer.__new__(SchemaIndexer)
                indexer.progress_file = progress_file

                result = indexer._load_progress()

                assert result.status == "pending"
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_get_progress(self, mock_db_manager, mock_embedding_service, mock_graph_store):
        """Test get_progress returns current progress."""
        indexer = SchemaIndexer(
            db_manager=mock_db_manager,
            embedding_service=mock_embedding_service,
            graph_store=mock_graph_store,
            env="test",
        )

        result = indexer.get_progress()

        assert isinstance(result, IndexProgress)

    def test_clear_progress(self, mock_db_manager, mock_embedding_service, mock_graph_store):
        """Test clear_progress removes progress file."""
        temp_dir = Path(tempfile.mkdtemp(dir=str(Path(".pytest_tmp"))))
        progress_file = temp_dir / "progress.json"
        progress_file.touch()

        try:
            with patch.object(SchemaIndexer, "__init__", lambda self, **kwargs: None):
                indexer = SchemaIndexer.__new__(SchemaIndexer)
                indexer.progress_file = progress_file

                indexer.clear_progress()

                assert not progress_file.exists()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_index_single_table_success(
        self, mock_db_manager, mock_embedding_service, mock_graph_store
    ):
        """Test index_single_table successfully indexes one table."""
        mock_conn = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.execute.return_value.scalar.return_value = "mydb"
        mock_conn.execute.return_value.fetchone.return_value = ("mydb", "User table")
        mock_conn.execute.return_value.fetchall.return_value = [
            ("id", "INT", "Primary key", "PRI"),
        ]

        with patch.object(SchemaIndexer, "_extract_foreign_keys", return_value=[]):
            indexer = SchemaIndexer(
                db_manager=mock_db_manager,
                embedding_service=mock_embedding_service,
                graph_store=mock_graph_store,
                env="test",
            )

            result = indexer.index_single_table("users")

            assert result is not None
            assert result.table_name == "users"
            mock_graph_store.add_table.assert_called_once()

    def test_index_single_table_failure(
        self, mock_db_manager, mock_embedding_service, mock_graph_store
    ):
        """Test index_single_table handles failure."""
        mock_db_manager.get_connection.side_effect = Exception("DB error")

        indexer = SchemaIndexer(
            db_manager=mock_db_manager,
            embedding_service=mock_embedding_service,
            graph_store=mock_graph_store,
            env="test",
        )

        result = indexer.index_single_table("users")

        assert result is None

    def test_extract_foreign_keys(self, mock_db_manager, mock_embedding_service, mock_graph_store):
        """Test _extract_foreign_keys extracts FK relations."""
        mock_conn = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.execute.return_value.fetchall.return_value = [
            ("user_id", "users", "id"),
            ("dept_id", "departments", "id"),
        ]

        indexer = SchemaIndexer(
            db_manager=mock_db_manager,
            embedding_service=mock_embedding_service,
            graph_store=mock_graph_store,
            env="test",
        )

        result = indexer._extract_foreign_keys("mydb", "orders")

        assert len(result) == 2
        assert result[0].column_name == "user_id"
        assert result[0].referenced_table == "users"

    def test_extract_foreign_keys_error(self, mock_db_manager, mock_embedding_service, mock_graph_store):
        """Test _extract_foreign_keys handles errors gracefully."""
        mock_db_manager.get_connection.side_effect = Exception("DB error")

        indexer = SchemaIndexer(
            db_manager=mock_db_manager,
            embedding_service=mock_embedding_service,
            graph_store=mock_graph_store,
            env="test",
        )

        result = indexer._extract_foreign_keys("mydb", "orders")

        assert result == []

    def test_index_batch_processes_tables(
        self, mock_db_manager, mock_embedding_service, mock_graph_store
    ):
        """Test _index_batch processes tables correctly."""
        mock_conn = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.execute.return_value.fetchone.return_value = ("mydb", "Table")
        mock_conn.execute.return_value.fetchall.return_value = [
            ("id", "INT", "Primary key", "PRI"),
        ]

        indexer = SchemaIndexer(
            db_manager=mock_db_manager,
            embedding_service=mock_embedding_service,
            graph_store=mock_graph_store,
            env="test",
        )

        graph = KnowledgeGraph()

        with patch.object(indexer, "_extract_foreign_keys", return_value=[]):
            result = indexer._index_batch("mydb", ["users"], graph)

        assert result["success_count"] == 1
        assert "users" in result["indexed"]
        assert len(result["failed"]) == 0

    def test_index_batch_handles_failure(
        self, mock_db_manager, mock_embedding_service, mock_graph_store
    ):
        """Test _index_batch handles extraction failure."""
        mock_db_manager.get_connection.side_effect = Exception("DB error")

        indexer = SchemaIndexer(
            db_manager=mock_db_manager,
            embedding_service=mock_embedding_service,
            graph_store=mock_graph_store,
            env="test",
        )

        graph = KnowledgeGraph()

        result = indexer._index_batch("mydb", ["users"], graph)

        assert result["success_count"] == 0
        assert "users" in result["failed"]

    def test_checkpoint_resume(
        self, mock_db_manager, mock_embedding_service, mock_graph_store
    ):
        """Test checkpoint/resume skips already indexed tables."""
        # Create progress file with indexed tables
        temp_dir = Path(tempfile.mkdtemp(dir=str(Path(".pytest_tmp"))))
        progress_file = temp_dir / "progress.json"
        progress_data = {
            "status": "in_progress",
            "total_tables": 3,
            "indexed_tables": 1,
            "current_batch": 1,
            "errors": [],
            "statistics": {"indexed_tables": ["users"]},
        }
        try:
            with open(progress_file, "w") as f:
                json.dump(progress_data, f)

            # Override get_all_tables to return 3 tables for this test
            mock_db_manager.get_all_tables.return_value = ["users", "orders", "products"]

            mock_conn = MagicMock()
            mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
            mock_conn.execute.return_value.scalar.return_value = "mydb"
            mock_conn.execute.return_value.fetchone.return_value = ("mydb", "Table")
            mock_conn.execute.return_value.fetchall.return_value = []

            indexer = SchemaIndexer(
                db_manager=mock_db_manager,
                embedding_service=mock_embedding_service,
                graph_store=mock_graph_store,
                env="test",
            )
            indexer.progress_file = progress_file

            with patch.object(indexer, "_extract_foreign_keys", return_value=[]):
                result = indexer.index_all_tables(batch_size=1)

            # Should have processed only the 2 remaining tables (orders, products)
            # since users was already indexed
            assert result.total_tables == 3
            assert result.indexed_tables == 3  # 1 already done + 2 newly indexed
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
