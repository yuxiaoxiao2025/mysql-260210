"""Tests for GraphStore in the metadata knowledge graph system."""

import json
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock

from src.metadata.graph_store import GraphStore
from src.metadata.models import (
    ColumnMetadata,
    ForeignKeyRelation,
    TableMetadata,
    KnowledgeGraph,
)


class TestGraphStore:
    """Test cases for GraphStore."""

    @pytest.fixture
    def temp_data_dir(self, tmp_path):
        """Create a temporary data directory for testing."""
        data_dir = tmp_path / "data" / "test"
        data_dir.mkdir(parents=True, exist_ok=True)
        yield data_dir
        # Cleanup
        if data_dir.exists():
            shutil.rmtree(data_dir, ignore_errors=True)

    @pytest.fixture
    def mock_chroma_client(self):
        """Create a mock ChromaDB client."""
        mock_client = MagicMock()

        # Mock table collection
        mock_table_collection = MagicMock()
        mock_table_collection.count.return_value = 0

        # Mock field collection
        mock_field_collection = MagicMock()
        mock_field_collection.count.return_value = 0

        # Setup get_or_create_collection
        def get_or_create_collection(name, metadata=None):
            if name == "table_metadata":
                return mock_table_collection
            elif name == "field_metadata":
                return mock_field_collection
            return MagicMock()

        mock_client.get_or_create_collection.side_effect = get_or_create_collection
        mock_client.delete_collection.return_value = None

        return mock_client, mock_table_collection, mock_field_collection

    def test_init_creates_collections(self, temp_data_dir, mock_chroma_client):
        """Test GraphStore initialization creates collections."""
        mock_client, mock_table, mock_field = mock_chroma_client

        with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
            mock_chromadb.return_value = mock_client

            store = GraphStore(env="test")

            assert store.env == "test"
            mock_chromadb.assert_called_once()

    def test_add_table_calls_upsert(self, temp_data_dir, mock_chroma_client):
        """Test add_table calls collection.upsert with correct parameters."""
        mock_client, mock_table, mock_field = mock_chroma_client

        with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
            mock_chromadb.return_value = mock_client

            store = GraphStore(env="test")
            table = TableMetadata(
                table_name="users",
                database_name="mydb",
                comment="User table",
                business_domain="用户",
            )
            embedding = [0.1] * 1024

            store.add_table(table, embedding)

            mock_table.upsert.assert_called_once()
            call_args = mock_table.upsert.call_args
            assert call_args[1]["ids"] == ["users"]
            assert len(call_args[1]["embeddings"]) == 1
            assert len(call_args[1]["embeddings"][0]) == 1024

    def test_add_table_wrong_dimension_raises_error(self, temp_data_dir, mock_chroma_client):
        """Test add_table raises error for wrong embedding dimension."""
        mock_client, mock_table, mock_field = mock_chroma_client

        with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
            mock_chromadb.return_value = mock_client

            store = GraphStore(env="test")
            table = TableMetadata(table_name="users")
            wrong_embedding = [0.1] * 512  # Wrong dimension

            with pytest.raises(ValueError) as exc_info:
                store.add_table(table, wrong_embedding)

            assert "1024" in str(exc_info.value)

    def test_add_field_calls_upsert(self, temp_data_dir, mock_chroma_client):
        """Test add_field calls collection.upsert with correct parameters."""
        mock_client, mock_table, mock_field = mock_chroma_client

        with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
            mock_chromadb.return_value = mock_client

            store = GraphStore(env="test")
            column = ColumnMetadata(
                name="user_id",
                data_type="INT",
                comment="User ID",
                is_primary_key=True,
            )
            embedding = [0.1] * 1024

            store.add_field("users", column, embedding)

            mock_field.upsert.assert_called_once()
            call_args = mock_field.upsert.call_args
            assert call_args[1]["ids"] == ["users.user_id"]

    def test_add_field_with_foreign_key(self, temp_data_dir, mock_chroma_client):
        """Test add_field includes foreign key metadata."""
        mock_client, mock_table, mock_field = mock_chroma_client

        with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
            mock_chromadb.return_value = mock_client

            store = GraphStore(env="test")
            column = ColumnMetadata(
                name="dept_id",
                data_type="INT",
                is_foreign_key=True,
                references_table="departments",
                references_column="id",
            )
            embedding = [0.1] * 1024

            store.add_field("users", column, embedding)

            call_args = mock_field.upsert.call_args
            metadata = call_args[1]["metadatas"][0]
            assert metadata["is_foreign_key"] is True
            assert metadata["references_table"] == "departments"

    def test_add_field_wrong_dimension_raises_error(self, temp_data_dir, mock_chroma_client):
        """Test add_field raises error for wrong embedding dimension."""
        mock_client, mock_table, mock_field = mock_chroma_client

        with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
            mock_chromadb.return_value = mock_client

            store = GraphStore(env="test")
            column = ColumnMetadata(name="id", data_type="INT")
            wrong_embedding = [0.1] * 512

            with pytest.raises(ValueError):
                store.add_field("users", column, wrong_embedding)

    def test_add_tables_batch(self, temp_data_dir, mock_chroma_client):
        """Test add_tables_batch processes multiple tables."""
        mock_client, mock_table, mock_field = mock_chroma_client

        with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
            mock_chromadb.return_value = mock_client

            store = GraphStore(env="test")
            tables = [
                TableMetadata(table_name="users", business_domain="用户"),
                TableMetadata(table_name="orders", business_domain="订单"),
            ]
            embeddings = [[0.1] * 1024, [0.2] * 1024]

            store.add_tables_batch(tables, embeddings)

            mock_table.upsert.assert_called_once()
            call_args = mock_table.upsert.call_args
            assert call_args[1]["ids"] == ["users", "orders"]

    def test_add_tables_batch_mismatched_lengths(self, temp_data_dir, mock_chroma_client):
        """Test add_tables_batch raises error for mismatched lengths."""
        mock_client, mock_table, mock_field = mock_chroma_client

        with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
            mock_chromadb.return_value = mock_client

            store = GraphStore(env="test")
            tables = [TableMetadata(table_name="users")]
            embeddings = [[0.1] * 1024, [0.2] * 1024]  # 2 embeddings for 1 table

            with pytest.raises(ValueError):
                store.add_tables_batch(tables, embeddings)

    def test_add_tables_batch_empty_list(self, temp_data_dir, mock_chroma_client):
        """Test add_tables_batch with empty list does nothing."""
        mock_client, mock_table, mock_field = mock_chroma_client

        with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
            mock_chromadb.return_value = mock_client

            store = GraphStore(env="test")

            store.add_tables_batch([], [])

            mock_table.upsert.assert_not_called()

    def test_add_fields_batch(self, temp_data_dir, mock_chroma_client):
        """Test add_fields_batch processes multiple fields."""
        mock_client, mock_table, mock_field = mock_chroma_client

        with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
            mock_chromadb.return_value = mock_client

            store = GraphStore(env="test")
            columns = [
                ColumnMetadata(name="id", data_type="INT"),
                ColumnMetadata(name="name", data_type="VARCHAR(100)"),
            ]
            embeddings = [[0.1] * 1024, [0.2] * 1024]

            store.add_fields_batch("users", columns, embeddings)

            mock_field.upsert.assert_called_once()
            call_args = mock_field.upsert.call_args
            assert call_args[1]["ids"] == ["users.id", "users.name"]

    def test_save_graph_creates_file(self, temp_data_dir, mock_chroma_client):
        """Test save_graph creates JSON file."""
        mock_client, mock_table, mock_field = mock_chroma_client

        with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
            mock_chromadb.return_value = mock_client

            store = GraphStore(env="test")
            graph = KnowledgeGraph(
                tables=[
                    TableMetadata(table_name="users"),
                ]
            )

            store.save_graph(graph)

            assert store.json_path.exists()

    def test_save_graph_creates_backup(self, temp_data_dir, mock_chroma_client):
        """Test save_graph creates backup of existing file."""
        mock_client, mock_table, mock_field = mock_chroma_client

        with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
            mock_chromadb.return_value = mock_client

            store = GraphStore(env="test")

            # Create initial file
            store.json_path.parent.mkdir(parents=True, exist_ok=True)
            with open(store.json_path, "w") as f:
                json.dump({"version": "1.0"}, f)

            graph = KnowledgeGraph(tables=[TableMetadata(table_name="users")])

            store.save_graph(graph)

            # Check backup was created
            backup_files = list(store.backup_path.glob("table_graph_*.json"))
            assert len(backup_files) > 0

    def test_load_graph_returns_graph(self, temp_data_dir, mock_chroma_client):
        """Test load_graph returns KnowledgeGraph from file."""
        mock_client, mock_table, mock_field = mock_chroma_client

        with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
            mock_chromadb.return_value = mock_client

            store = GraphStore(env="test")

            # Create a valid graph file
            graph_data = {
                "version": "1.0",
                "tables": [
                    {
                        "table_name": "users",
                        "columns": [],
                        "foreign_keys": [],
                    }
                ]
            }
            store.json_path.parent.mkdir(parents=True, exist_ok=True)
            with open(store.json_path, "w") as f:
                json.dump(graph_data, f)

            result = store.load_graph()

            assert result is not None
            assert len(result.tables) == 1
            assert result.tables[0].table_name == "users"

    def test_load_graph_nonexistent_file(self, temp_data_dir, mock_chroma_client):
        """Test load_graph returns None for nonexistent file."""
        mock_client, mock_table, mock_field = mock_chroma_client

        with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
            mock_chromadb.return_value = mock_client

            store = GraphStore(env="test_nonexistent")  # Use different env to avoid conflicts

            # Ensure the file doesn't exist
            if store.json_path.exists():
                store.json_path.unlink()

            result = store.load_graph()

            assert result is None

    def test_load_graph_invalid_json(self, temp_data_dir, mock_chroma_client):
        """Test load_graph returns None for invalid JSON."""
        mock_client, mock_table, mock_field = mock_chroma_client

        with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
            mock_chromadb.return_value = mock_client

            store = GraphStore(env="test")
            store.json_path.parent.mkdir(parents=True, exist_ok=True)
            with open(store.json_path, "w") as f:
                f.write("invalid json {{{")

            result = store.load_graph()

            assert result is None

    def test_clear_all(self, temp_data_dir, mock_chroma_client):
        """Test clear_all deletes and recreates collections."""
        mock_client, mock_table, mock_field = mock_chroma_client

        with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
            mock_chromadb.return_value = mock_client

            store = GraphStore(env="test")

            store.clear_all()

            # Should delete and recreate both collections
            assert mock_client.delete_collection.call_count == 2

    def test_query_tables(self, temp_data_dir, mock_chroma_client):
        """Test query_tables returns formatted results."""
        mock_client, mock_table, mock_field = mock_chroma_client

        mock_table.query.return_value = {
            "ids": [["users", "orders"]],
            "distances": [[0.1, 0.2]],
            "metadatas": [[
                {"business_domain": "用户"},
                {"business_domain": "订单"},
            ]]
        }

        with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
            mock_chromadb.return_value = mock_client

            store = GraphStore(env="test")
            embedding = [0.1] * 1024

            results = store.query_tables(embedding, top_k=2)

            assert len(results) == 2
            assert results[0]["id"] == "users"
            assert results[0]["distance"] == 0.1

    def test_query_tables_wrong_dimension(self, temp_data_dir, mock_chroma_client):
        """Test query_tables raises error for wrong dimension."""
        mock_client, mock_table, mock_field = mock_chroma_client

        with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
            mock_chromadb.return_value = mock_client

            store = GraphStore(env="test")
            wrong_embedding = [0.1] * 512

            with pytest.raises(ValueError):
                store.query_tables(wrong_embedding)

    def test_query_fields(self, temp_data_dir, mock_chroma_client):
        """Test query_fields returns formatted results."""
        mock_client, mock_table, mock_field = mock_chroma_client

        mock_field.query.return_value = {
            "ids": [["users.id", "users.name"]],
            "distances": [[0.1, 0.2]],
            "metadatas": [[
                {"data_type": "INT", "is_primary_key": True},
                {"data_type": "VARCHAR", "is_primary_key": False},
            ]]
        }

        with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
            mock_chromadb.return_value = mock_client

            store = GraphStore(env="test")
            embedding = [0.1] * 1024

            results = store.query_fields(embedding, top_k=2)

            assert len(results) == 2
            assert results[0]["id"] == "users.id"

    def test_query_fields_with_filter(self, temp_data_dir, mock_chroma_client):
        """Test query_fields with table filter."""
        mock_client, mock_table, mock_field = mock_chroma_client

        mock_field.query.return_value = {
            "ids": [["users.id"]],
            "distances": [[0.1]],
            "metadatas": [[{"data_type": "INT"}]]
        }

        with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
            mock_chromadb.return_value = mock_client

            store = GraphStore(env="test")
            embedding = [0.1] * 1024

            results = store.query_fields(
                embedding,
                filter_tables=["users"],
                top_k=5
            )

            # Check that filter was passed
            call_args = mock_field.query.call_args
            assert call_args[1]["where"] == {"table_name": {"$in": ["users"]}}

    def test_get_table_count(self, temp_data_dir, mock_chroma_client):
        """Test get_table_count returns collection count."""
        mock_client, mock_table, mock_field = mock_chroma_client
        mock_table.count.return_value = 10

        with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
            mock_chromadb.return_value = mock_client

            store = GraphStore(env="test")

            assert store.get_table_count() == 10

    def test_get_field_count(self, temp_data_dir, mock_chroma_client):
        """Test get_field_count returns collection count."""
        mock_client, mock_table, mock_field = mock_chroma_client
        mock_field.count.return_value = 50

        with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
            mock_chromadb.return_value = mock_client

            store = GraphStore(env="test")

            assert store.get_field_count() == 50

    def test_delete_table(self, temp_data_dir, mock_chroma_client):
        """Test delete_table calls collection.delete."""
        mock_client, mock_table, mock_field = mock_chroma_client

        with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
            mock_chromadb.return_value = mock_client

            store = GraphStore(env="test")

            store.delete_table("users")

            mock_table.delete.assert_called_once_with(ids=["users"])

    def test_delete_field(self, temp_data_dir, mock_chroma_client):
        """Test delete_field calls collection.delete."""
        mock_client, mock_table, mock_field = mock_chroma_client

        with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
            mock_chromadb.return_value = mock_client

            store = GraphStore(env="test")

            store.delete_field("users", "id")

            mock_field.delete.assert_called_once_with(ids=["users.id"])

    def test_delete_table_fields(self, temp_data_dir, mock_chroma_client):
        """Test delete_table_fields deletes all fields for a table."""
        mock_client, mock_table, mock_field = mock_chroma_client

        mock_field.get.return_value = {
            "ids": ["users.id", "users.name"]
        }

        with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
            mock_chromadb.return_value = mock_client

            store = GraphStore(env="test")

            store.delete_table_fields("users")

            mock_field.get.assert_called_once_with(where={"table_name": "users"})
            mock_field.delete.assert_called_once_with(ids=["users.id", "users.name"])

    def test_delete_table_fields_no_fields(self, temp_data_dir, mock_chroma_client):
        """Test delete_table_fields when no fields exist."""
        mock_client, mock_table, mock_field = mock_chroma_client

        mock_field.get.return_value = {"ids": []}

        with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
            mock_chromadb.return_value = mock_client

            store = GraphStore(env="test")

            store.delete_table_fields("nonexistent")

            mock_field.delete.assert_not_called()

    def test_get_stats(self, temp_data_dir, mock_chroma_client):
        """Test get_stats returns correct statistics."""
        mock_client, mock_table, mock_field = mock_chroma_client
        mock_table.count.return_value = 10
        mock_field.count.return_value = 50

        with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
            mock_chromadb.return_value = mock_client

            store = GraphStore(env="test")

            stats = store.get_stats()

            assert stats["env"] == "test"
            assert stats["table_count"] == 10
            assert stats["field_count"] == 50

    def test_add_table_truncates_long_comment(self, temp_data_dir, mock_chroma_client):
        """Test add_table truncates comments longer than 500 chars."""
        mock_client, mock_table, mock_field = mock_chroma_client

        with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
            mock_chromadb.return_value = mock_client

            store = GraphStore(env="test")
            long_comment = "x" * 600
            table = TableMetadata(table_name="users", comment=long_comment)
            embedding = [0.1] * 1024

            store.add_table(table, embedding)

            call_args = mock_table.upsert.call_args
            metadata = call_args[1]["metadatas"][0]
            assert len(metadata["comment"]) == 500

    def test_add_field_truncates_long_comment(self, temp_data_dir, mock_chroma_client):
        """Test add_field truncates comments longer than 200 chars."""
        mock_client, mock_table, mock_field = mock_chroma_client

        with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
            mock_chromadb.return_value = mock_client

            store = GraphStore(env="test")
            long_comment = "x" * 300
            column = ColumnMetadata(name="id", data_type="INT", comment=long_comment)
            embedding = [0.1] * 1024

            store.add_field("users", column, embedding)

            call_args = mock_field.upsert.call_args
            metadata = call_args[1]["metadatas"][0]
            assert len(metadata["comment"]) == 200

    def test_add_table_exception_propagates(self, temp_data_dir, mock_chroma_client):
        """Test add_table propagates exceptions from collection.upsert."""
        mock_client, mock_table, mock_field = mock_chroma_client
        mock_table.upsert.side_effect = RuntimeError("Database error")

        with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
            mock_chromadb.return_value = mock_client

            store = GraphStore(env="test")
            table = TableMetadata(table_name="users")
            embedding = [0.1] * 1024

            with pytest.raises(RuntimeError):
                store.add_table(table, embedding)

    def test_add_field_exception_propagates(self, temp_data_dir, mock_chroma_client):
        """Test add_field propagates exceptions from collection.upsert."""
        mock_client, mock_table, mock_field = mock_chroma_client
        mock_field.upsert.side_effect = RuntimeError("Database error")

        with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
            mock_chromadb.return_value = mock_client

            store = GraphStore(env="test")
            column = ColumnMetadata(name="id", data_type="INT")
            embedding = [0.1] * 1024

            with pytest.raises(RuntimeError):
                store.add_field("users", column, embedding)

    def test_add_tables_batch_wrong_dimension_single(self, temp_data_dir, mock_chroma_client):
        """Test add_tables_batch raises error for single wrong dimension."""
        mock_client, mock_table, mock_field = mock_chroma_client

        with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
            mock_chromadb.return_value = mock_client

            store = GraphStore(env="test")
            tables = [TableMetadata(table_name="users")]
            embeddings = [[0.1] * 512]  # Wrong dimension

            with pytest.raises(ValueError) as exc_info:
                store.add_tables_batch(tables, embeddings)

            assert "wrong dimension" in str(exc_info.value).lower()

    def test_add_fields_batch_wrong_dimension_single(self, temp_data_dir, mock_chroma_client):
        """Test add_fields_batch raises error for single wrong dimension."""
        mock_client, mock_table, mock_field = mock_chroma_client

        with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
            mock_chromadb.return_value = mock_client

            store = GraphStore(env="test")
            columns = [ColumnMetadata(name="id", data_type="INT")]
            embeddings = [[0.1] * 512]  # Wrong dimension

            with pytest.raises(ValueError) as exc_info:
                store.add_fields_batch("users", columns, embeddings)

            assert "wrong dimension" in str(exc_info.value).lower()

    def test_add_tables_batch_exception_propagates(self, temp_data_dir, mock_chroma_client):
        """Test add_tables_batch propagates exceptions."""
        mock_client, mock_table, mock_field = mock_chroma_client
        mock_table.upsert.side_effect = RuntimeError("Database error")

        with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
            mock_chromadb.return_value = mock_client

            store = GraphStore(env="test")
            tables = [TableMetadata(table_name="users")]
            embeddings = [[0.1] * 1024]

            with pytest.raises(RuntimeError):
                store.add_tables_batch(tables, embeddings)

    def test_add_fields_batch_exception_propagates(self, temp_data_dir, mock_chroma_client):
        """Test add_fields_batch propagates exceptions."""
        mock_client, mock_table, mock_field = mock_chroma_client
        mock_field.upsert.side_effect = RuntimeError("Database error")

        with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
            mock_chromadb.return_value = mock_client

            store = GraphStore(env="test")
            columns = [ColumnMetadata(name="id", data_type="INT")]
            embeddings = [[0.1] * 1024]

            with pytest.raises(RuntimeError):
                store.add_fields_batch("users", columns, embeddings)

    def test_save_graph_handles_write_error(self, temp_data_dir, mock_chroma_client):
        """Test save_graph handles write errors."""
        mock_client, mock_table, mock_field = mock_chroma_client

        with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
            mock_chromadb.return_value = mock_client

            store = GraphStore(env="test")
            graph = KnowledgeGraph()

            # Mock open to raise an error
            with patch("builtins.open", side_effect=PermissionError("Write denied")):
                with pytest.raises(PermissionError):
                    store.save_graph(graph)

    def test_clear_all_exception_propagates(self, temp_data_dir, mock_chroma_client):
        """Test clear_all propagates exceptions."""
        mock_client, mock_table, mock_field = mock_chroma_client
        mock_client.delete_collection.side_effect = RuntimeError("Delete failed")

        with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
            mock_chromadb.return_value = mock_client

            store = GraphStore(env="test")

            with pytest.raises(RuntimeError):
                store.clear_all()

    def test_query_tables_exception_propagates(self, temp_data_dir, mock_chroma_client):
        """Test query_tables propagates exceptions."""
        mock_client, mock_table, mock_field = mock_chroma_client
        mock_table.query.side_effect = RuntimeError("Query failed")

        with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
            mock_chromadb.return_value = mock_client

            store = GraphStore(env="test")
            embedding = [0.1] * 1024

            with pytest.raises(RuntimeError):
                store.query_tables(embedding)

    def test_query_fields_exception_propagates(self, temp_data_dir, mock_chroma_client):
        """Test query_fields propagates exceptions."""
        mock_client, mock_table, mock_field = mock_chroma_client
        mock_field.query.side_effect = RuntimeError("Query failed")

        with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
            mock_chromadb.return_value = mock_client

            store = GraphStore(env="test")
            embedding = [0.1] * 1024

            with pytest.raises(RuntimeError):
                store.query_fields(embedding)

    def test_delete_table_exception_propagates(self, temp_data_dir, mock_chroma_client):
        """Test delete_table propagates exceptions."""
        mock_client, mock_table, mock_field = mock_chroma_client
        mock_table.delete.side_effect = RuntimeError("Delete failed")

        with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
            mock_chromadb.return_value = mock_client

            store = GraphStore(env="test")

            with pytest.raises(RuntimeError):
                store.delete_table("users")

    def test_delete_field_exception_propagates(self, temp_data_dir, mock_chroma_client):
        """Test delete_field propagates exceptions."""
        mock_client, mock_table, mock_field = mock_chroma_client
        mock_field.delete.side_effect = RuntimeError("Delete failed")

        with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
            mock_chromadb.return_value = mock_client

            store = GraphStore(env="test")

            with pytest.raises(RuntimeError):
                store.delete_field("users", "id")

    def test_delete_table_fields_exception_propagates(self, temp_data_dir, mock_chroma_client):
        """Test delete_table_fields propagates exceptions."""
        mock_client, mock_table, mock_field = mock_chroma_client
        mock_field.get.side_effect = RuntimeError("Query failed")

        with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
            mock_chromadb.return_value = mock_client

            store = GraphStore(env="test")

            with pytest.raises(RuntimeError):
                store.delete_table_fields("users")

    def test_query_fields_without_results(self, temp_data_dir, mock_chroma_client):
        """Test query_fields handles empty results."""
        mock_client, mock_table, mock_field = mock_chroma_client
        mock_field.query.return_value = {"ids": [[]], "distances": [[]], "metadatas": [[]]}

        with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
            mock_chromadb.return_value = mock_client

            store = GraphStore(env="test")
            embedding = [0.1] * 1024

            results = store.query_fields(embedding)

            assert results == []

    def test_query_tables_without_results(self, temp_data_dir, mock_chroma_client):
        """Test query_tables handles empty results."""
        mock_client, mock_table, mock_field = mock_chroma_client
        mock_table.query.return_value = {"ids": [[]], "distances": [[]], "metadatas": [[]]}

        with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
            mock_chromadb.return_value = mock_client

            store = GraphStore(env="test")
            embedding = [0.1] * 1024

            results = store.query_tables(embedding)

            assert results == []

    def test_save_graph_creates_parent_directory(self, temp_data_dir, mock_chroma_client):
        """Test save_graph creates parent directory if needed."""
        mock_client, mock_table, mock_field = mock_chroma_client

        with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
            mock_chromadb.return_value = mock_client

            store = GraphStore(env="new_env_test")
            # Ensure directory doesn't exist
            if store.json_path.exists():
                store.json_path.unlink()

            graph = KnowledgeGraph()
            store.save_graph(graph)

            assert store.json_path.parent.exists()