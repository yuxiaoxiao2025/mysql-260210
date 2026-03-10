"""
Sidebar component for Knowledge Graph Explorer.

Provides query input and query history navigation.
"""

import streamlit as st

from src.web.state_manager import StateManager


def render_sidebar(state_manager: StateManager) -> str:
    """
    Render the sidebar with query input and history.

    Args:
        state_manager: StateManager instance for session state

    Returns:
        The current query text from input
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

        history = state_manager.history

        if not history:
            st.info("No query history yet")
            history_options = ["(New Query)"]
        else:
            history_options = ["(New Query)"] + [
                f"{item.timestamp[:19]} - {item.query[:30]}..."
                if len(item.query) > 30
                else f"{item.timestamp[:19]} - {item.query}"
                for item in reversed(history)
            ]

        selected_history = st.selectbox(
            "History",
            options=history_options,
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

    return query_text, search_clicked


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