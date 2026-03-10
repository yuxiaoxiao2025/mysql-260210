"""
Sidebar component for Knowledge Graph Explorer.

Provides query input and query history navigation.
"""

import streamlit as st

from src.web.state_manager import StateManager


def render_sidebar(state_manager: StateManager) -> tuple[str, bool, str]:
    """
    Render the sidebar with query input and history.

    Args:
        state_manager: StateManager instance for session state

    Returns:
        Tuple of (query_text, search_clicked, selected_history_timestamp)
    """
    with st.sidebar:
        st.header("🔍 Query Input")

        # Query input
        query_text = st.text_area(
            "Enter your query:",
            value=state_manager.current_query,
            height=100,
            placeholder="e.g., 查询停车订单信息",
            key="query_input"
        )

        # Update state if query changed
        if query_text != state_manager.current_query:
            state_manager.current_query = query_text

        # Search button
        search_clicked = st.button("🔎 Search", type="primary", use_container_width=True)

        st.divider()

        # Query History
        st.header("📜 Query History")

        history_entries = state_manager.get_history(limit=20)
        history_labels = {}

        if not history_entries:
            st.info("No query history yet")
            history_options = [""]
        else:
            history_options = [""]
            for entry in history_entries:
                timestamp = entry.get("timestamp", "")
                query = entry.get("query", "")
                if not timestamp:
                    continue
                if len(query) > 30:
                    label = f"{timestamp[:19]} - {query[:30]}..."
                else:
                    label = f"{timestamp[:19]} - {query}"
                history_options.append(timestamp)
                history_labels[timestamp] = label

        selected_history = st.selectbox(
            "History",
            options=history_options,
            format_func=lambda value: "(New Query)" if value == "" else history_labels.get(value, value),
            index=0,
            key="history_selector"
        )

        # Clear selection button
        if st.button("🗑️ Clear Selection", use_container_width=True):
            state_manager.clear_selection()
            st.rerun()

        # Reset all button
        if st.button("🔄 Reset All", use_container_width=True):
            state_manager.reset()
            st.rerun()

    return query_text, search_clicked, selected_history


def render_mock_sidebar() -> tuple[str, bool]:
    """
    Render a standalone mock sidebar for testing without StateManager.

    Returns:
        Tuple of (query_text, search_clicked)
    """
    with st.sidebar:
        st.header("🔍 Query Input")

        query_text = st.text_area(
            "Enter your query:",
            height=100,
            placeholder="e.g., 查询停车订单信息",
            key="mock_query_input"
        )

        search_clicked = st.button("🔎 Search", type="primary", use_container_width=True)

        st.divider()

        st.header("📜 Query History")
        st.info("No query history yet")

        st.divider()

        if st.button("🔄 Reset All", use_container_width=True):
            st.rerun()

    return query_text, search_clicked
