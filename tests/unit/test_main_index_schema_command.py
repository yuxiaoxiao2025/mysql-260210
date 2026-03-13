import sys
import types
from unittest.mock import MagicMock

import main


def test_parse_index_schema_options_supports_prune_and_include_empty():
    options, error = main._parse_index_schema_options(
        ["index", "schema", "--env", "prod", "--batch-size", "5", "--prune", "--include-empty"]
    )

    assert error is None
    assert options == {
        "env": "prod",
        "batch_size": 5,
        "force": False,
        "prune": True,
        "include_empty": True,
    }


def test_parse_index_schema_options_rejects_invalid_batch_size():
    options, error = main._parse_index_schema_options(
        ["index", "schema", "--batch-size", "abc"]
    )

    assert options is None
    assert error == "[ERR] --batch-size 必须是整数"


def test_handle_index_schema_command_passes_schema_indexer_flags(monkeypatch):
    class _Result:
        success = True
        total_tables = 2
        indexed_tables = 2
        elapsed_seconds = 0.2
        failed_tables = []

    class _FakeIndexer:
        last_instance = None

        def __init__(self, db_manager, env):
            self.db_manager = db_manager
            self.env = env
            self.clear_progress_called = False
            self.index_args = None
            _FakeIndexer.last_instance = self

        def clear_progress(self):
            self.clear_progress_called = True

        def index_all_databases(self, **kwargs):
            self.index_args = kwargs
            return _Result()

    class _FakeGraphStore:
        last_instance = None

        def __init__(self, env):
            self.env = env
            self.cleared = False
            _FakeGraphStore.last_instance = self

        def clear_all(self):
            self.cleared = True

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

    db = MagicMock()
    consumed = main._handle_index_schema_command(
        "index schema --env dev --batch-size 8 --force --prune --include-empty",
        db,
    )

    assert consumed is True
    assert _FakeIndexer.last_instance is not None
    assert _FakeIndexer.last_instance.db_manager is db
    assert _FakeIndexer.last_instance.env == "dev"
    assert _FakeIndexer.last_instance.clear_progress_called is True
    assert _FakeIndexer.last_instance.index_args == {
        "batch_size": 8,
        "skip_empty_tables": False,
        "prune": True,
    }
    assert _FakeGraphStore.last_instance is not None
    assert _FakeGraphStore.last_instance.env == "dev"
    assert _FakeGraphStore.last_instance.cleared is True
