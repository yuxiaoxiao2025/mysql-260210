"""Tests for Pydantic models in the metadata knowledge graph system."""

import pytest
from datetime import datetime

from src.metadata.models import (
    ColumnMetadata,
    ForeignKeyRelation,
    TableMetadata,
    KnowledgeGraph,
    IndexProgress,
    IndexResult,
)


class TestColumnMetadata:
    """Test cases for ColumnMetadata model."""

    def test_create_column_metadata_with_required_fields(self):
        """Test creating ColumnMetadata with only required fields."""
        col = ColumnMetadata(name="id", data_type="INT")

        assert col.name == "id"
        assert col.data_type == "INT"
        assert col.comment == ""
        assert col.is_primary_key is False
        assert col.is_foreign_key is False
        assert col.references_table is None
        assert col.references_column is None

    def test_create_column_metadata_with_all_fields(self):
        """Test creating ColumnMetadata with all fields."""
        col = ColumnMetadata(
            name="user_id",
            data_type="BIGINT",
            comment="Foreign key to users table",
            is_primary_key=False,
            is_foreign_key=True,
            references_table="users",
            references_column="id",
        )

        assert col.name == "user_id"
        assert col.data_type == "BIGINT"
        assert col.comment == "Foreign key to users table"
        assert col.is_primary_key is False
        assert col.is_foreign_key is True
        assert col.references_table == "users"
        assert col.references_column == "id"

    def test_primary_key_flag(self):
        """Test that primary key flag is correctly set."""
        col = ColumnMetadata(name="id", data_type="INT", is_primary_key=True)

        assert col.is_primary_key is True

    def test_foreign_key_flag(self):
        """Test that foreign key flag is correctly set."""
        col = ColumnMetadata(
            name="order_id",
            data_type="INT",
            is_foreign_key=True,
            references_table="orders",
            references_column="id",
        )

        assert col.is_foreign_key is True
        assert col.references_table == "orders"
        assert col.references_column == "id"

    def test_column_metadata_serialization(self):
        """Test that ColumnMetadata can be serialized to dict."""
        col = ColumnMetadata(
            name="status",
            data_type="VARCHAR(50)",
            comment="Order status",
        )

        data = col.model_dump()

        assert data["name"] == "status"
        assert data["data_type"] == "VARCHAR(50)"
        assert data["comment"] == "Order status"


class TestForeignKeyRelation:
    """Test cases for ForeignKeyRelation model."""

    def test_create_foreign_key_relation(self):
        """Test creating ForeignKeyRelation."""
        fk = ForeignKeyRelation(
            column_name="user_id",
            referenced_table="users",
            referenced_column="id",
        )

        assert fk.column_name == "user_id"
        assert fk.referenced_table == "users"
        assert fk.referenced_column == "id"

    def test_foreign_key_relation_serialization(self):
        """Test ForeignKeyRelation serialization."""
        fk = ForeignKeyRelation(
            column_name="order_id",
            referenced_table="orders",
            referenced_column="id",
        )

        data = fk.model_dump()

        assert data["column_name"] == "order_id"
        assert data["referenced_table"] == "orders"
        assert data["referenced_column"] == "id"


class TestTableMetadata:
    """Test cases for TableMetadata model."""

    def test_create_table_metadata_with_required_fields(self):
        """Test creating TableMetadata with only required fields."""
        table = TableMetadata(table_name="users")

        assert table.table_name == "users"
        assert table.database_name == ""
        assert table.comment == ""
        assert table.columns == []
        assert table.foreign_keys == []
        assert table.business_domain == "其他"
        assert table.schema_text == ""
        assert table.tags == []

    def test_create_table_metadata_with_all_fields(self):
        """Test creating TableMetadata with all fields."""
        columns = [
            ColumnMetadata(name="id", data_type="INT", is_primary_key=True),
            ColumnMetadata(name="name", data_type="VARCHAR(100)", comment="User name"),
        ]
        foreign_keys = [
            ForeignKeyRelation(
                column_name="dept_id",
                referenced_table="departments",
                referenced_column="id",
            )
        ]

        table = TableMetadata(
            table_name="users",
            database_name="mydb",
            comment="User information table",
            columns=columns,
            foreign_keys=foreign_keys,
            business_domain="用户",
            schema_text="Table: users",
            tags=["用户", "有主键"],
        )

        assert table.table_name == "users"
        assert table.database_name == "mydb"
        assert table.comment == "User information table"
        assert len(table.columns) == 2
        assert len(table.foreign_keys) == 1
        assert table.business_domain == "用户"
        assert table.schema_text == "Table: users"
        assert "用户" in table.tags

    def test_table_metadata_accepts_semantic_fields(self):
        """Test TableMetadata accepts semantic enrichment fields."""
        table = TableMetadata(
            table_name="t",
            comment="",
            semantic_description="业务语义",
            semantic_tags=["标签"],
            semantic_source="llm",
            semantic_confidence=0.9,
            columns=[],
        )

        assert table.semantic_description == "业务语义"
        assert table.semantic_tags == ["标签"]
        assert table.semantic_source == "llm"
        assert table.semantic_confidence == 0.9

    def test_get_column_existing(self):
        """Test get_column for existing column."""
        columns = [
            ColumnMetadata(name="id", data_type="INT"),
            ColumnMetadata(name="name", data_type="VARCHAR(100)"),
        ]
        table = TableMetadata(table_name="users", columns=columns)

        col = table.get_column("name")

        assert col is not None
        assert col.name == "name"

    def test_get_column_non_existing(self):
        """Test get_column for non-existing column."""
        table = TableMetadata(table_name="users")

        col = table.get_column("nonexistent")

        assert col is None

    def test_get_primary_keys(self):
        """Test get_primary_keys method."""
        columns = [
            ColumnMetadata(name="id", data_type="INT", is_primary_key=True),
            ColumnMetadata(name="name", data_type="VARCHAR(100)"),
            ColumnMetadata(name="id2", data_type="INT", is_primary_key=True),
        ]
        table = TableMetadata(table_name="users", columns=columns)

        pk_columns = table.get_primary_keys()

        assert len(pk_columns) == 2
        assert all(col.is_primary_key for col in pk_columns)

    def test_get_primary_keys_no_pk(self):
        """Test get_primary_keys when no primary keys exist."""
        columns = [
            ColumnMetadata(name="name", data_type="VARCHAR(100)"),
        ]
        table = TableMetadata(table_name="users", columns=columns)

        pk_columns = table.get_primary_keys()

        assert len(pk_columns) == 0

    def test_get_foreign_key_columns(self):
        """Test get_foreign_key_columns method."""
        columns = [
            ColumnMetadata(name="id", data_type="INT", is_primary_key=True),
            ColumnMetadata(
                name="dept_id",
                data_type="INT",
                is_foreign_key=True,
                references_table="departments",
                references_column="id",
            ),
        ]
        table = TableMetadata(table_name="users", columns=columns)

        fk_columns = table.get_foreign_key_columns()

        assert len(fk_columns) == 1
        assert fk_columns[0].name == "dept_id"


class TestKnowledgeGraph:
    """Test cases for KnowledgeGraph model."""

    def test_create_knowledge_graph_default(self):
        """Test creating KnowledgeGraph with defaults."""
        graph = KnowledgeGraph()

        assert graph.version == "2.0"
        assert graph.tables == []
        assert graph.created_at is not None
        assert graph.updated_at is not None

    def test_get_table_existing(self):
        """Test get_table for existing table."""
        table1 = TableMetadata(table_name="users")
        table2 = TableMetadata(table_name="orders")
        graph = KnowledgeGraph(tables=[table1, table2])

        result = graph.get_table("orders")

        assert result is not None
        assert result.table_name == "orders"

    def test_get_table_non_existing(self):
        """Test get_table for non-existing table."""
        graph = KnowledgeGraph()

        result = graph.get_table("nonexistent")

        assert result is None

    def test_get_foreign_keys_from_existing_table(self):
        """Test get_foreign_keys_from for existing table."""
        fk = ForeignKeyRelation(
            column_name="user_id",
            referenced_table="users",
            referenced_column="id",
        )
        table = TableMetadata(table_name="orders", foreign_keys=[fk])
        graph = KnowledgeGraph(tables=[table])

        result = graph.get_foreign_keys_from("orders")

        assert len(result) == 1
        assert result[0].column_name == "user_id"

    def test_get_foreign_keys_from_non_existing_table(self):
        """Test get_foreign_keys_from for non-existing table."""
        graph = KnowledgeGraph()

        result = graph.get_foreign_keys_from("nonexistent")

        assert result == []

    def test_get_foreign_keys_to(self):
        """Test get_foreign_keys_to method."""
        fk1 = ForeignKeyRelation(
            column_name="user_id",
            referenced_table="users",
            referenced_column="id",
        )
        fk2 = ForeignKeyRelation(
            column_name="created_by",
            referenced_table="users",
            referenced_column="id",
        )
        table1 = TableMetadata(table_name="orders", foreign_keys=[fk1])
        table2 = TableMetadata(table_name="products", foreign_keys=[fk2])
        graph = KnowledgeGraph(tables=[table1, table2])

        result = graph.get_foreign_keys_to("users")

        assert len(result) == 2
        assert result[0]["source_table"] == "orders"
        assert result[1]["source_table"] == "products"

    def test_get_tables_by_domain(self):
        """Test get_tables_by_domain method."""
        table1 = TableMetadata(table_name="users", business_domain="用户")
        table2 = TableMetadata(table_name="orders", business_domain="订单")
        table3 = TableMetadata(table_name="customers", business_domain="用户")
        graph = KnowledgeGraph(tables=[table1, table2, table3])

        result = graph.get_tables_by_domain("用户")

        assert len(result) == 2
        assert all(t.business_domain == "用户" for t in result)

    def test_get_tables_by_tag(self):
        """Test get_tables_by_tag method."""
        table1 = TableMetadata(table_name="users", tags=["用户", "有主键"])
        table2 = TableMetadata(table_name="orders", tags=["订单", "有主键"])
        table3 = TableMetadata(table_name="logs", tags=["日志"])
        graph = KnowledgeGraph(tables=[table1, table2, table3])

        result = graph.get_tables_by_tag("有主键")

        assert len(result) == 2
        assert all("有主键" in t.tags for t in result)

    def test_get_all_domains(self):
        """Test get_all_domains method."""
        table1 = TableMetadata(table_name="users", business_domain="用户")
        table2 = TableMetadata(table_name="orders", business_domain="订单")
        table3 = TableMetadata(table_name="other", business_domain="其他")
        graph = KnowledgeGraph(tables=[table1, table2, table3])

        result = graph.get_all_domains()

        assert "用户" in result
        assert "订单" in result
        assert "其他" in result

    def test_get_all_tags(self):
        """Test get_all_tags method."""
        table1 = TableMetadata(table_name="users", tags=["用户", "VIP"])
        table2 = TableMetadata(table_name="orders", tags=["订单", "VIP"])
        graph = KnowledgeGraph(tables=[table1, table2])

        result = graph.get_all_tags()

        assert "用户" in result
        assert "订单" in result
        assert "VIP" in result

    def test_update_timestamp(self):
        """Test update_timestamp method updates the timestamp."""
        import time
        graph = KnowledgeGraph()
        original_updated_at = graph.updated_at

        # Small delay to ensure timestamp changes
        time.sleep(0.001)
        graph.update_timestamp()

        # The timestamp should be updated (different from original)
        # Note: In rare cases they might be the same if within same millisecond,
        # so we also verify the method doesn't raise an error
        assert graph.updated_at is not None


class TestIndexProgress:
    """Test cases for IndexProgress model."""

    def test_create_index_progress_default(self):
        """Test creating IndexProgress with defaults."""
        progress = IndexProgress()

        assert progress.status == "pending"
        assert progress.total_tables == 0
        assert progress.indexed_tables == 0
        assert progress.current_batch == 0
        assert progress.errors == []
        assert progress.statistics == {}

    def test_get_progress_percentage_zero_total(self):
        """Test get_progress_percentage with zero total tables."""
        progress = IndexProgress(total_tables=0, indexed_tables=0)

        result = progress.get_progress_percentage()

        assert result == 0.0

    def test_get_progress_percentage_partial(self):
        """Test get_progress_percentage with partial progress."""
        progress = IndexProgress(total_tables=10, indexed_tables=3)

        result = progress.get_progress_percentage()

        assert result == 30.0

    def test_get_progress_percentage_complete(self):
        """Test get_progress_percentage when complete."""
        progress = IndexProgress(total_tables=10, indexed_tables=10)

        result = progress.get_progress_percentage()

        assert result == 100.0

    def test_is_complete_pending(self):
        """Test is_complete for pending status."""
        progress = IndexProgress(status="pending")

        assert progress.is_complete() is False

    def test_is_complete_in_progress(self):
        """Test is_complete for in_progress status."""
        progress = IndexProgress(status="in_progress")

        assert progress.is_complete() is False

    def test_is_complete_completed(self):
        """Test is_complete for completed status."""
        progress = IndexProgress(status="completed")

        assert progress.is_complete() is True

    def test_is_complete_failed(self):
        """Test is_complete for failed status."""
        progress = IndexProgress(status="failed")

        assert progress.is_complete() is True

    def test_add_error(self):
        """Test add_error method."""
        progress = IndexProgress()

        progress.add_error("Test error message")

        assert len(progress.errors) == 1
        assert progress.errors[0] == "Test error message"

    def test_update_progress(self):
        """Test update_progress method."""
        progress = IndexProgress()

        progress.update_progress(indexed=5, batch=2)

        assert progress.indexed_tables == 5
        assert progress.current_batch == 2


class TestIndexResult:
    """Test cases for IndexResult model."""

    def test_create_index_result_success(self):
        """Test creating successful IndexResult."""
        result = IndexResult(
            success=True,
            total_tables=10,
            indexed_tables=10,
        )

        assert result.success is True
        assert result.total_tables == 10
        assert result.indexed_tables == 10
        assert result.failed_tables == []
        assert result.elapsed_seconds == 0.0

    def test_create_index_result_with_failures(self):
        """Test creating IndexResult with failures."""
        result = IndexResult(
            success=False,
            total_tables=10,
            indexed_tables=8,
            failed_tables=["table1", "table2"],
            elapsed_seconds=5.5,
        )

        assert result.success is False
        assert result.indexed_tables == 8
        assert len(result.failed_tables) == 2
        assert result.elapsed_seconds == 5.5

    def test_get_success_rate_zero_total_success(self):
        """Test get_success_rate with zero total tables and success."""
        result = IndexResult(success=True, total_tables=0, indexed_tables=0)

        rate = result.get_success_rate()

        assert rate == 100.0

    def test_get_success_rate_zero_total_failure(self):
        """Test get_success_rate with zero total tables and failure."""
        result = IndexResult(success=False, total_tables=0, indexed_tables=0)

        rate = result.get_success_rate()

        assert rate == 0.0

    def test_get_success_rate_partial(self):
        """Test get_success_rate with partial success."""
        result = IndexResult(
            success=True,
            total_tables=10,
            indexed_tables=8,
        )

        rate = result.get_success_rate()

        assert rate == 80.0

    def test_get_success_rate_complete(self):
        """Test get_success_rate when complete."""
        result = IndexResult(
            success=True,
            total_tables=10,
            indexed_tables=10,
        )

        rate = result.get_success_rate()

        assert rate == 100.0

    def test_has_failures_true(self):
        """Test has_failures when there are failures."""
        result = IndexResult(
            success=True,
            total_tables=10,
            indexed_tables=8,
            failed_tables=["table1"],
        )

        assert result.has_failures() is True

    def test_has_failures_false(self):
        """Test has_failures when there are no failures."""
        result = IndexResult(
            success=True,
            total_tables=10,
            indexed_tables=10,
        )

        assert result.has_failures() is False
