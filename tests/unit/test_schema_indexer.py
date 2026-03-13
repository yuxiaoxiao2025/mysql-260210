from unittest.mock import MagicMock

from src.metadata.models import IndexProgress, KnowledgeGraph
from src.metadata.schema_indexer import SchemaIndexer


def _build_indexer() -> SchemaIndexer:
    indexer = SchemaIndexer.__new__(SchemaIndexer)
    indexer.db_manager = MagicMock()
    indexer.graph_store = MagicMock()
    indexer.embedding_service = MagicMock()
    indexer.domain_classifier = MagicMock()
    return indexer


def test_index_database_default_skips_empty_tables():
    indexer = _build_indexer()
    graph = KnowledgeGraph()

    indexer.db_manager.get_tables_in_database.return_value = ["users", "empty_logs"]
    indexer.db_manager.is_table_empty.side_effect = lambda _db, table: table == "empty_logs"
    indexer._index_batch = MagicMock(return_value={"success_count": 1, "failed": []})

    result = indexer.index_database("parkcloud", batch_size=10, knowledge_graph=graph)

    assert result.total_tables == 2
    assert result.indexed_tables == 1
    indexer._index_batch.assert_called_once_with("parkcloud", ["users"], graph)


def test_index_database_can_include_empty_tables():
    indexer = _build_indexer()
    graph = KnowledgeGraph()

    indexer.db_manager.get_tables_in_database.return_value = ["users", "empty_logs"]
    indexer._index_batch = MagicMock(return_value={"success_count": 2, "failed": []})

    result = indexer.index_database(
        "parkcloud",
        batch_size=10,
        knowledge_graph=graph,
        skip_empty_tables=False,
    )

    assert result.total_tables == 2
    assert result.indexed_tables == 2
    indexer.db_manager.is_table_empty.assert_not_called()
    indexer._index_batch.assert_called_once_with(
        "parkcloud", ["users", "empty_logs"], graph
    )


def test_filter_empty_tables_logs_skipped_table(caplog):
    indexer = _build_indexer()
    indexer.db_manager.is_table_empty.side_effect = lambda _db, table: table == "empty_logs"

    with caplog.at_level("INFO"):
        non_empty, skipped = indexer._filter_empty_tables(
            "parkcloud", ["users", "empty_logs"]
        )

    assert non_empty == ["users"]
    assert skipped == ["empty_logs"]
    assert "Skipping empty table: parkcloud.empty_logs" in caplog.text


def test_prune_invalid_entries_returns_summary():
    indexer = _build_indexer()
    indexer.db_manager.get_tables_in_database.return_value = ["users", "orders"]
    indexer.graph_store.get_all_table_ids.return_value = [
        "parkcloud.users",
        "parkcloud.ghost_table",
    ]
    indexer.graph_store.delete_tables_with_fields_batch.return_value = {
        "tables_deleted": 1,
        "fields_deleted": 2,
    }

    summary = indexer.prune_invalid_entries("parkcloud")

    assert summary["success"] is True
    assert summary["database"] == "parkcloud"
    assert summary["scanned_table_ids"] == 2
    assert summary["invalid_table_ids"] == 1
    assert summary["tables_deleted"] == 1
    assert summary["fields_deleted"] == 2
    indexer.graph_store.delete_tables_with_fields_batch.assert_called_once_with(
        ["parkcloud.ghost_table"]
    )


def test_prune_invalid_entries_can_remove_empty_tables():
    indexer = _build_indexer()
    indexer.db_manager.get_tables_in_database.return_value = ["users", "empty_logs"]
    indexer.db_manager.is_table_empty.side_effect = (
        lambda _db, table_name: table_name == "empty_logs"
    )
    indexer.graph_store.get_all_table_ids.return_value = [
        "parkcloud.users",
        "parkcloud.empty_logs",
    ]
    indexer.graph_store.delete_tables_with_fields_batch.return_value = {
        "tables_deleted": 1,
        "fields_deleted": 3,
    }

    summary = indexer.prune_invalid_entries("parkcloud", prune_empty_tables=True)

    assert summary["success"] is True
    assert summary["invalid_table_ids"] == 1
    assert summary["empty_table_ids"] == 1
    indexer.graph_store.delete_tables_with_fields_batch.assert_called_once_with(
        ["parkcloud.empty_logs"]
    )


def test_index_all_tables_default_uses_skip_empty_tables():
    indexer = _build_indexer()
    indexer._get_current_database_name = MagicMock(return_value="parkcloud")
    indexer.db_manager.get_all_tables.return_value = ["users"]
    indexer._load_progress = MagicMock(return_value=IndexProgress())
    indexer._save_progress = MagicMock()
    indexer._filter_empty_tables = MagicMock(return_value=(["users"], []))
    indexer._index_batch = MagicMock(
        return_value={"success_count": 1, "indexed": ["users"], "failed": []}
    )

    result = indexer.index_all_tables(batch_size=10)

    assert result.success is True
    indexer._filter_empty_tables.assert_called_once_with("parkcloud", ["users"])


def test_index_all_tables_logs_batch_failure_reason(caplog):
    indexer = _build_indexer()
    indexer._get_current_database_name = MagicMock(return_value="parkcloud")
    indexer.db_manager.get_all_tables.return_value = ["users"]
    indexer._load_progress = MagicMock(return_value=IndexProgress())
    indexer._save_progress = MagicMock()
    indexer._filter_empty_tables = MagicMock(return_value=(["users"], []))
    indexer._index_batch = MagicMock(side_effect=RuntimeError("mock batch failure reason"))
    indexer.graph_store.save_graph = MagicMock()

    with caplog.at_level("ERROR"):
        result = indexer.index_all_tables(batch_size=10, prune=False)

    assert result.success is False
    assert result.failed_tables == ["users"]
    assert "Batch 1 failed: mock batch failure reason" in caplog.text
