import sys
import types
from unittest.mock import MagicMock

import main
from src.metadata.models import IndexProgress
from src.metadata.schema_indexer import SchemaIndexer


def test_index_all_tables_with_prune_and_skip_empty():
    indexer = SchemaIndexer.__new__(SchemaIndexer)
    indexer.db_manager = MagicMock()
    indexer.graph_store = MagicMock()
    indexer.embedding_service = MagicMock()
    indexer.domain_classifier = MagicMock()

    indexer._get_current_database_name = MagicMock(return_value="parkcloud")
    indexer.db_manager.get_all_tables.return_value = ["users", "empty_logs"]
    indexer.db_manager.get_tables_in_database.return_value = ["users", "empty_logs"]
    indexer.db_manager.is_table_empty.side_effect = (
        lambda _db, table_name: table_name == "empty_logs"
    )
    indexer.graph_store.get_all_table_ids.return_value = [
        "parkcloud.users",
        "parkcloud.empty_logs",
        "parkcloud.ghost_table",
    ]
    indexer.graph_store.delete_tables_with_fields_batch.return_value = {
        "tables_deleted": 2,
        "fields_deleted": 4,
    }
    indexer._load_progress = MagicMock(return_value=IndexProgress())
    indexer._save_progress = MagicMock()
    indexer._index_batch = MagicMock(
        return_value={"success_count": 1, "indexed": ["users"], "failed": []}
    )
    indexer.graph_store.save_graph = MagicMock()

    result = indexer.index_all_tables(batch_size=10, skip_empty_tables=True, prune=True)

    assert result.success is True
    assert result.total_tables == 2
    assert result.indexed_tables == 1
    indexer.graph_store.delete_tables_with_fields_batch.assert_called_once_with(
        ["parkcloud.empty_logs", "parkcloud.ghost_table"]
    )
    indexer._index_batch.assert_called_once()


def test_index_schema_command_prune_uses_default_skip_empty(monkeypatch):
    class _Result:
        success = True
        total_tables = 2
        indexed_tables = 1
        elapsed_seconds = 0.1
        failed_tables = []

    class _FakeIndexer:
        last_instance = None

        def __init__(self, db_manager, env):
            self.db_manager = db_manager
            self.env = env
            self.index_kwargs = None
            _FakeIndexer.last_instance = self

        def clear_progress(self):
            return None

        def index_all_databases(self, **kwargs):
            self.index_kwargs = kwargs
            return _Result()

    class _FakeGraphStore:
        def __init__(self, env):
            self.env = env

        def clear_all(self):
            return None

    monkeypatch.setattr(main, "SchemaIndexer", _FakeIndexer, raising=False)
    monkeypatch.setattr(main, "GraphStore", _FakeGraphStore, raising=False)
    monkeypatch.setitem(
        sys.modules,
        "src.metadata.schema_indexer",
        types.SimpleNamespace(SchemaIndexer=_FakeIndexer),
    )
    monkeypatch.setitem(
        sys.modules,
        "src.metadata.graph_store",
        types.SimpleNamespace(GraphStore=_FakeGraphStore),
    )

    consumed = main._handle_index_schema_command("index schema --env dev --prune", MagicMock())

    assert consumed is True
    assert _FakeIndexer.last_instance is not None
    assert _FakeIndexer.last_instance.index_kwargs == {
        "batch_size": 10,
        "skip_empty_tables": True,
        "prune": True,
    }
