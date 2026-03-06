import pytest
from unittest.mock import MagicMock, patch

from src.metadata.graph_store import GraphStore
from src.metadata.models import TableMetadata


@pytest.fixture
def mock_chroma_client():
    mock_client = MagicMock()

    mock_table_collection = MagicMock()
    mock_table_collection.count.return_value = 0

    mock_field_collection = MagicMock()
    mock_field_collection.count.return_value = 0

    def get_or_create_collection(name, metadata=None):
        if name == "table_metadata":
            return mock_table_collection
        if name == "field_metadata":
            return mock_field_collection
        return MagicMock()

    mock_client.get_or_create_collection.side_effect = get_or_create_collection
    return mock_client, mock_table_collection, mock_field_collection


def test_add_table_with_namespace_sets_id_and_metadata(mock_chroma_client):
    mock_client, mock_table, _mock_field = mock_chroma_client

    with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
        mock_chromadb.return_value = mock_client
        store = GraphStore(env="test")
        table = TableMetadata(
            table_name="users",
            namespace="ns1",
            comment="User table"
        )
        embedding = [0.1] * 1024

        store.add_table(table, embedding)

        call_args = mock_table.upsert.call_args
        assert call_args[1]["ids"] == ["ns1.users"]
        metadata = call_args[1]["metadatas"][0]
        assert metadata["namespace"] == "ns1"


def test_query_tables_with_namespace_filters(mock_chroma_client):
    mock_client, mock_table, _mock_field = mock_chroma_client
    mock_table.query.return_value = {"ids": [[]], "distances": [[]], "metadatas": [[]]}

    with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
        mock_chromadb.return_value = mock_client
        store = GraphStore(env="test")
        embedding = [0.1] * 1024

        store.query_tables(embedding, namespace="ns1")

        call_args = mock_table.query.call_args
        assert call_args[1]["where"] == {"namespace": "ns1"}


def test_clone_namespace_clones_table_and_field(mock_chroma_client):
    mock_client, mock_table, mock_field = mock_chroma_client
    mock_table.get.return_value = {
        "ids": ["ns1.users"],
        "embeddings": [[0.1] * 1024],
        "metadatas": [{"namespace": "ns1"}],
    }
    mock_field.get.return_value = {
        "ids": ["ns1.users.id"],
        "embeddings": [[0.2] * 1024],
        "metadatas": [{"namespace": "ns1"}],
    }

    with patch("src.metadata.graph_store.chromadb.PersistentClient") as mock_chromadb:
        mock_chromadb.return_value = mock_client
        store = GraphStore(env="test")

        store.clone_namespace("ns1", "ns2")

        table_call = mock_table.upsert.call_args_list[-1]
        assert table_call[1]["ids"] == ["ns2.users"]
        assert table_call[1]["metadatas"][0]["namespace"] == "ns2"

        field_call = mock_field.upsert.call_args_list[-1]
        assert field_call[1]["ids"] == ["ns2.users.id"]
        assert field_call[1]["metadatas"][0]["namespace"] == "ns2"
