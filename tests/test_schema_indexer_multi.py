from unittest.mock import ANY, MagicMock, patch

from src.metadata.schema_indexer import SchemaIndexer
from src.metadata.models import IndexResult


def test_index_all_databases_clones_template():
    db_manager = MagicMock()
    db_manager.get_all_databases.return_value = [
        "primarydb",
        "park_template",
        "park_a",
        "park_b",
    ]

    graph_store = MagicMock()
    embedding_service = MagicMock()

    indexer = SchemaIndexer(
        db_manager=db_manager,
        embedding_service=embedding_service,
        graph_store=graph_store,
    )

    with patch.object(
        SchemaIndexer,
        "index_database",
        return_value=IndexResult(success=True, total_tables=0, indexed_tables=0)
    ) as index_database:
        indexer.index_all_databases()

        index_database.assert_any_call(
            "primarydb",
            batch_size=10,
            knowledge_graph=ANY,
        )
        index_database.assert_any_call(
            "park_template",
            batch_size=10,
            knowledge_graph=ANY,
        )
        graph_store.clone_namespace.assert_any_call("park_template", "park_a")
        graph_store.clone_namespace.assert_any_call("park_template", "park_b")

        graph_store.save_graph.assert_called_once()
        saved_graph = graph_store.save_graph.call_args[0][0]
        assert saved_graph.template_mapping["park_a"] == "park_template"
        assert saved_graph.template_mapping["park_b"] == "park_template"
        assert "park_a" in saved_graph.park_instances
        assert "park_b" in saved_graph.park_instances


def test_index_all_databases_without_template_indexes_instances():
    db_manager = MagicMock()
    db_manager.get_all_databases.return_value = ["park_a", "park_b"]

    graph_store = MagicMock()
    embedding_service = MagicMock()

    indexer = SchemaIndexer(
        db_manager=db_manager,
        embedding_service=embedding_service,
        graph_store=graph_store,
    )

    with patch.object(
        SchemaIndexer,
        "index_database",
        return_value=IndexResult(success=True, total_tables=0, indexed_tables=0)
    ) as index_database:
        indexer.index_all_databases()

        index_database.assert_any_call(
            "park_a",
            batch_size=10,
            knowledge_graph=ANY,
        )
        index_database.assert_any_call(
            "park_b",
            batch_size=10,
            knowledge_graph=ANY,
        )
        graph_store.clone_namespace.assert_not_called()
