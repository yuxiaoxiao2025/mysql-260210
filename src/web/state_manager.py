"""
State Manager for Knowledge Graph Explorer.

Manages session state including query history, selected tables,
graph data, and search results using Streamlit Session State.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import streamlit as st

from src.web.utils.history_store import HistoryStore


@dataclass
class QueryHistoryItem:
    """A single query history entry."""
    timestamp: str
    query: str
    selected_tables: List[str] = field(default_factory=list)


@dataclass
class GraphData:
    """Graph data structure for visualization."""
    nodes: List[Dict[str, Any]] = field(default_factory=list)
    edges: List[Dict[str, Any]] = field(default_factory=list)


class StateManager:
    """
    Manages Streamlit session state for the Knowledge Graph Explorer.

    Provides a clean interface for accessing and modifying session state
    with type safety and sensible defaults.
    """

    # State keys
    KEY_HISTORY = "history"
    KEY_SELECTED_TABLES = "selected_tables"
    KEY_GRAPH_DATA = "graph_data"
    KEY_SEARCH_RESULTS = "search_results"
    KEY_CURRENT_QUERY = "current_query"
    KEY_GENERATED_SQL = "generated_sql"

    def __init__(self):
        """Initialize StateManager and ensure session state is set up."""
        self._init_session_state()
        self.history_store = HistoryStore()

    def _init_session_state(self):
        """Initialize session state with default values if not exists."""
        if self.KEY_HISTORY not in st.session_state:
            st.session_state[self.KEY_HISTORY] = []

        if self.KEY_SELECTED_TABLES not in st.session_state:
            st.session_state[self.KEY_SELECTED_TABLES] = []

        if self.KEY_GRAPH_DATA not in st.session_state:
            st.session_state[self.KEY_GRAPH_DATA] = {"nodes": [], "edges": []}

        if self.KEY_SEARCH_RESULTS not in st.session_state:
            st.session_state[self.KEY_SEARCH_RESULTS] = []

        if self.KEY_CURRENT_QUERY not in st.session_state:
            st.session_state[self.KEY_CURRENT_QUERY] = ""

        if self.KEY_GENERATED_SQL not in st.session_state:
            st.session_state[self.KEY_GENERATED_SQL] = ""

    @property
    def history(self) -> List[QueryHistoryItem]:
        """Get query history."""
        return st.session_state[self.KEY_HISTORY]

    @history.setter
    def history(self, value: List[QueryHistoryItem]):
        """Set query history."""
        st.session_state[self.KEY_HISTORY] = value

    def add_to_history(self, query: str, selected_tables: List[str]):
        """Add a new entry to query history."""
        from datetime import datetime

        item = QueryHistoryItem(
            timestamp=datetime.now().isoformat(),
            query=query,
            selected_tables=selected_tables
        )
        self.history.append(item)

    @property
    def selected_tables(self) -> List[str]:
        """Get currently selected table names."""
        return st.session_state[self.KEY_SELECTED_TABLES]

    @selected_tables.setter
    def selected_tables(self, value: List[str]):
        """Set selected table names."""
        st.session_state[self.KEY_SELECTED_TABLES] = value

    def add_selected_table(self, table_name: str):
        """Add a table to selection."""
        if table_name not in self.selected_tables:
            self.selected_tables = self.selected_tables + [table_name]

    def remove_selected_table(self, table_name: str):
        """Remove a table from selection."""
        self.selected_tables = [t for t in self.selected_tables if t != table_name]

    def clear_selection(self):
        """Clear all selected tables."""
        self.selected_tables = []

    @property
    def graph_data(self) -> GraphData:
        """Get current graph data."""
        data = st.session_state[self.KEY_GRAPH_DATA]
        return GraphData(
            nodes=data.get("nodes", []),
            edges=data.get("edges", [])
        )

    @graph_data.setter
    def graph_data(self, value: GraphData):
        """Set graph data."""
        st.session_state[self.KEY_GRAPH_DATA] = {
            "nodes": value.nodes,
            "edges": value.edges
        }

    @property
    def search_results(self) -> List[Dict[str, Any]]:
        """Get current search results."""
        return st.session_state[self.KEY_SEARCH_RESULTS]

    @search_results.setter
    def search_results(self, value: List[Dict[str, Any]]):
        """Set search results."""
        st.session_state[self.KEY_SEARCH_RESULTS] = value

    @property
    def current_query(self) -> str:
        """Get current query text."""
        return st.session_state[self.KEY_CURRENT_QUERY]

    @current_query.setter
    def current_query(self, value: str):
        """Set current query text."""
        st.session_state[self.KEY_CURRENT_QUERY] = value

    @property
    def generated_sql(self) -> str:
        """Get generated SQL."""
        return st.session_state[self.KEY_GENERATED_SQL]

    @generated_sql.setter
    def generated_sql(self, value: str):
        """Set generated SQL."""
        st.session_state[self.KEY_GENERATED_SQL] = value

    def reset(self):
        """Reset all session state to defaults."""
        st.session_state[self.KEY_HISTORY] = []
        st.session_state[self.KEY_SELECTED_TABLES] = []
        st.session_state[self.KEY_GRAPH_DATA] = {"nodes": [], "edges": []}
        st.session_state[self.KEY_SEARCH_RESULTS] = []
        st.session_state[self.KEY_CURRENT_QUERY] = ""
        st.session_state[self.KEY_GENERATED_SQL] = ""

    def save_to_history(self, generated_sql: Optional[str] = None):
        """Save current session to history.

        Args:
            generated_sql: Generated SQL (optional)
        """
        if self.current_query:
            self.history_store.add_entry(
                query=self.current_query,
                selected_tables=self.selected_tables,
                generated_sql=generated_sql
            )

    def get_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get latest history entries.

        Args:
            limit: Number of entries to return

        Returns:
            List of history entries
        """
        return self.history_store.get_latest(limit=limit)

    def clear_history(self) -> bool:
        """Clear all history.

        Returns:
            True if successful
        """
        return self.history_store.clear()

    def restore_session(self, timestamp: str) -> Optional[Dict[str, Any]]:
        """Restore a specific session by timestamp.

        Args:
            timestamp: ISO timestamp of session to restore

        Returns:
            Session data or None if not found
        """
        return self.history_store.restore_session(timestamp=timestamp)