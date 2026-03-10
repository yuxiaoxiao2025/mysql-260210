from unittest.mock import MagicMock

from src.metadata.models import ColumnMetadata, ForeignKeyRelation, KnowledgeGraph, TableMetadata
from src.web.services.graph_service import KnowledgeGraphService


def _build_kg_with_cycle():
    orders = TableMetadata(
        table_name="orders",
        namespace="biz",
        comment="订单",
        columns=[
            ColumnMetadata(name="id", data_type="INT", is_primary_key=True),
            ColumnMetadata(name="user_id", data_type="INT"),
        ],
        foreign_keys=[
            ForeignKeyRelation(column_name="user_id", referenced_table="users", referenced_column="id"),
        ],
    )
    users = TableMetadata(
        table_name="users",
        namespace="biz",
        comment="",
        columns=[
            ColumnMetadata(name="id", data_type="INT", is_primary_key=True),
            ColumnMetadata(name="dept_id", data_type="INT"),
        ],
        foreign_keys=[
            ForeignKeyRelation(column_name="dept_id", referenced_table="dept", referenced_column="id"),
        ],
    )
    dept = TableMetadata(
        table_name="dept",
        namespace="biz",
        comment="部门",
        columns=[
            ColumnMetadata(name="id", data_type="INT", is_primary_key=True),
            ColumnMetadata(name="owner_order_id", data_type="INT"),
        ],
        foreign_keys=[
            ForeignKeyRelation(column_name="owner_order_id", referenced_table="orders", referenced_column="id"),
        ],
    )
    return KnowledgeGraph(tables=[orders, users, dept])


def _service_with_graph(kg):
    indexer = MagicMock()
    indexer.graph_store.load_graph.return_value = kg
    return KnowledgeGraphService(indexer)


def test_build_graph_returns_empty_when_no_graph():
    service = _service_with_graph(None)
    graph = service.build_graph()
    assert graph.number_of_nodes() == 0
    assert graph.number_of_edges() == 0


def test_build_graph_sets_node_and_edge_attributes():
    service = _service_with_graph(_build_kg_with_cycle())
    graph = service.build_graph()
    assert set(graph.nodes()) == {"orders", "users", "dept"}
    assert graph.nodes["users"]["table_comment"] == ""
    assert sorted(graph.nodes["orders"]["columns"]) == ["id", "user_id"]
    assert graph.has_edge("orders", "users")
    edge = graph.get_edge_data("orders", "users")[0]
    assert edge["relationship"] == "foreign_key"
    assert edge["from_column"] == "user_id"
    assert edge["to_column"] == "id"


def test_graph_property_uses_lazy_cache():
    service = _service_with_graph(_build_kg_with_cycle())
    first = service.graph
    second = service.graph
    assert first is second
    service.schema_indexer.graph_store.load_graph.assert_called_once()


def test_get_neighbors_for_existing_and_missing_node():
    service = _service_with_graph(_build_kg_with_cycle())
    service.build_graph()
    assert set(service.get_neighbors("orders")) == {"users"}
    assert service.get_neighbors("missing") == []


def test_get_subgraph_empty_input_returns_empty_payload():
    service = _service_with_graph(_build_kg_with_cycle())
    service.build_graph()
    assert service.get_subgraph_for_tables([]) == {"nodes": [], "edges": []}


def test_get_subgraph_handles_missing_tables():
    service = _service_with_graph(_build_kg_with_cycle())
    service.build_graph()
    result = service.get_subgraph_for_tables(["ghost"])
    assert result == {"nodes": [], "edges": []}


def test_get_subgraph_radius_one_contains_direct_neighbors():
    service = _service_with_graph(_build_kg_with_cycle())
    service.build_graph()
    result = service.get_subgraph_for_tables(["orders"], radius=1)
    node_ids = {node["id"] for node in result["nodes"]}
    assert node_ids == {"orders", "users"}


def test_get_subgraph_radius_two_includes_cycle_node_without_infinite_loop():
    service = _service_with_graph(_build_kg_with_cycle())
    service.build_graph()
    result = service.get_subgraph_for_tables(["orders"], radius=3)
    node_ids = {node["id"] for node in result["nodes"]}
    assert node_ids == {"orders", "users", "dept"}
    assert len(result["edges"]) == 3


def test_get_subgraph_result_contract_is_nodes_edges_dict_list():
    service = _service_with_graph(_build_kg_with_cycle())
    service.build_graph()
    result = service.get_subgraph_for_tables(["orders"], radius=2)
    assert isinstance(result, dict)
    assert isinstance(result["nodes"], list)
    assert isinstance(result["edges"], list)
    for node in result["nodes"]:
        assert "id" in node and "label" in node
    for edge in result["edges"]:
        assert {"id", "source", "target"} <= set(edge)
