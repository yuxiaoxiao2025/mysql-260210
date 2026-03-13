from unittest.mock import MagicMock

import pytest

from src.metadata.graph_store import GraphStore


@pytest.fixture
def graph_store():
    store = GraphStore.__new__(GraphStore)
    store.table_collection = MagicMock()
    store.field_collection = MagicMock()
    return store


def test_get_all_table_ids_supports_namespace_filter(graph_store):
    graph_store.table_collection.get.return_value = {"ids": ["ns.users", "ns.orders"]}

    table_ids = graph_store.get_all_table_ids(namespace="ns")

    assert table_ids == ["ns.users", "ns.orders"]
    graph_store.table_collection.get.assert_called_once_with(
        where={"namespace": "ns"},
        include=[]
    )


def test_delete_tables_batch_normalizes_and_deduplicates_ids(graph_store):
    deleted = graph_store.delete_tables_batch(["ns.users", " ns.users ", "", "ns.orders"])

    assert deleted == 2
    graph_store.table_collection.delete.assert_called_once_with(
        ids=["ns.users", "ns.orders"]
    )


def test_delete_tables_with_fields_batch_deletes_related_fields(graph_store):
    graph_store.field_collection.get.side_effect = [
        {"ids": ["ns.users.id", "ns.users.name"]},
        {"ids": ["orders.id"]},
    ]

    result = graph_store.delete_tables_with_fields_batch(["ns.users", "orders"])

    assert result == {"tables_deleted": 2, "fields_deleted": 3}
    graph_store.table_collection.delete.assert_called_once_with(ids=["ns.users", "orders"])
    graph_store.field_collection.delete.assert_called_once_with(
        ids=["ns.users.id", "ns.users.name", "orders.id"]
    )


def test_delete_tables_with_fields_batch_is_idempotent(graph_store):
    graph_store.field_collection.get.return_value = {"ids": []}

    first = graph_store.delete_tables_with_fields_batch(["ns.users"])
    second = graph_store.delete_tables_with_fields_batch(["ns.users"])

    assert first == {"tables_deleted": 1, "fields_deleted": 0}
    assert second == {"tables_deleted": 1, "fields_deleted": 0}
    graph_store.field_collection.delete.assert_not_called()


def test_delete_table_uses_namespace_and_deletes_fields(graph_store):
    graph_store.field_collection.get.return_value = {"ids": ["ns.users.id"]}

    graph_store.delete_table(table_name="users", namespace="ns")

    graph_store.table_collection.delete.assert_called_once_with(ids=["ns.users"])
    graph_store.field_collection.delete.assert_called_once_with(ids=["ns.users.id"])


def test_delete_table_rejects_empty_table_name(graph_store):
    with pytest.raises(ValueError):
        graph_store.delete_table(table_name="  ")


def test_delete_field_uses_namespaced_field_id(graph_store):
    graph_store.delete_field(table_name="users", column_name="id", namespace="ns")

    graph_store.field_collection.delete.assert_called_once_with(ids=["ns.users.id"])


def test_delete_table_fields_rejects_empty_table_name(graph_store):
    with pytest.raises(ValueError):
        graph_store.delete_table_fields(table_name="")
