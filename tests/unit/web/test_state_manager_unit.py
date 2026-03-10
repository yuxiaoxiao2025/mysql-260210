import sys
from unittest.mock import MagicMock

from src.web.state_manager import GraphData, QueryHistoryItem, StateManager


def _streamlit_module():
    return sys.modules["streamlit"]


def test_state_manager_initializes_defaults():
    manager = StateManager()
    st = _streamlit_module()
    assert st.session_state[StateManager.KEY_HISTORY] == []
    assert st.session_state[StateManager.KEY_SELECTED_TABLES] == []
    assert st.session_state[StateManager.KEY_GRAPH_DATA] == {"nodes": [], "edges": []}
    assert st.session_state[StateManager.KEY_CURRENT_QUERY] == ""


def test_add_remove_and_clear_selected_tables():
    manager = StateManager()
    manager.add_selected_table("users")
    manager.add_selected_table("users")
    manager.add_selected_table("orders")
    assert manager.selected_tables == ["users", "orders"]
    manager.remove_selected_table("users")
    assert manager.selected_tables == ["orders"]
    manager.clear_selection()
    assert manager.selected_tables == []


def test_graph_data_roundtrip():
    manager = StateManager()
    manager.graph_data = GraphData(nodes=[{"id": "n1"}], edges=[{"id": "e1"}])
    graph = manager.graph_data
    assert graph.nodes == [{"id": "n1"}]
    assert graph.edges == [{"id": "e1"}]


def test_add_to_history_appends_query_item():
    manager = StateManager()
    manager.add_to_history("查订单", ["orders"])
    assert len(manager.history) == 1
    item = manager.history[0]
    assert isinstance(item, QueryHistoryItem)
    assert item.query == "查订单"
    assert item.selected_tables == ["orders"]


def test_save_to_history_only_when_current_query_exists():
    manager = StateManager()
    manager.history_store = MagicMock()
    manager.current_query = ""
    manager.save_to_history("SELECT 1")
    manager.history_store.add_entry.assert_not_called()
    manager.current_query = "查订单"
    manager.selected_tables = ["orders"]
    manager.save_to_history("SELECT * FROM orders")
    manager.history_store.add_entry.assert_called_once()


def test_get_history_clear_history_restore_delegate_to_store():
    manager = StateManager()
    manager.history_store = MagicMock()
    manager.history_store.get_latest.return_value = [{"query": "q1"}]
    manager.history_store.clear.return_value = True
    manager.history_store.restore_session.return_value = {"query": "q1"}
    assert manager.get_history(limit=3) == [{"query": "q1"}]
    assert manager.clear_history() is True
    assert manager.restore_session("2026-01-01") == {"query": "q1"}
    manager.history_store.get_latest.assert_called_once_with(limit=3)
    manager.history_store.clear.assert_called_once()
    manager.history_store.restore_session.assert_called_once_with(timestamp="2026-01-01")


def test_reset_restores_defaults():
    manager = StateManager()
    manager.current_query = "x"
    manager.generated_sql = "SELECT 1"
    manager.selected_tables = ["users"]
    manager.search_results = [{"id": 1}]
    manager.graph_data = GraphData(nodes=[{"id": "n"}], edges=[{"id": "e"}])
    manager.history = [QueryHistoryItem(timestamp="t", query="q")]
    manager.reset()
    assert manager.current_query == ""
    assert manager.generated_sql == ""
    assert manager.selected_tables == []
    assert manager.search_results == []
    assert manager.graph_data.nodes == []
    assert manager.history == []


def test_init_uses_existing_session_values():
    st = _streamlit_module()
    st.session_state = {
        StateManager.KEY_HISTORY: ["h"],
        StateManager.KEY_SELECTED_TABLES: ["t"],
        StateManager.KEY_GRAPH_DATA: {"nodes": [{"id": "n"}], "edges": []},
        StateManager.KEY_SEARCH_RESULTS: [{"x": 1}],
        StateManager.KEY_CURRENT_QUERY: "q",
        StateManager.KEY_GENERATED_SQL: "SELECT 1",
    }
    manager = StateManager()
    assert manager.history == ["h"]
    assert manager.selected_tables == ["t"]
    assert manager.current_query == "q"


def test_generated_sql_property_roundtrip():
    manager = StateManager()
    manager.generated_sql = "SELECT now()"
    assert manager.generated_sql == "SELECT now()"


def test_search_results_property_roundtrip():
    manager = StateManager()
    manager.search_results = [{"table": "users"}]
    assert manager.search_results == [{"table": "users"}]
