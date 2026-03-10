"""
Knowledge Graph Explorer - Streamlit Application.

An interactive database explorer that uses Knowledge Graph visualization
and LLM-powered Reranking to help users find tables and generate SQL.
"""

import logging
import sys
from pathlib import Path

import streamlit as st

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.web.state_manager import StateManager
from src.web.components.sidebar import render_sidebar

logger = logging.getLogger(__name__)

# Page config
st.set_page_config(
    page_title="Knowledge Graph Explorer",
    page_icon="🗄️",
    layout="wide",
    initial_sidebar_state="expanded",
)


def init_services():
    """Initialize backend services (to be implemented in later tasks)."""
    # Placeholder for service initialization
    # Will be implemented in Task 2 and Task 4
    pass


def main():
    """Main application entry point."""
    st.title("🗄️ Knowledge Graph Explorer")
    st.markdown("Interactive database explorer with Knowledge Graph visualization")

    # Initialize state manager
    state_manager = StateManager()

    # Initialize services
    init_services()

    # Render sidebar and get query
    query_text, search_clicked = render_sidebar(state_manager)

    # Main content area
    col1, col2 = st.columns([2, 1])

    with col1:
        st.header("📊 Graph View")
        st.info("Knowledge graph will be rendered here (Task 3)")

        # Placeholder for graph visualization
        if state_manager.selected_tables:
            st.write(f"**Selected Tables:** {', '.join(state_manager.selected_tables)}")
        else:
            st.info("Search and select tables to view graph")

    with col2:
        st.header("📋 Search Results")
        st.info("Search results will appear here (Task 4)")

        if state_manager.search_results:
            for result in state_manager.search_results:
                st.write(f"- {result}")

    # Handle search action
    if search_clicked and query_text:
        st.session_state["last_search_query"] = query_text
        # TODO: Implement search and rank in Task 4
        st.rerun()

    # Detail panel (Task 5)
    with st.expander("📝 Table Details", expanded=False):
        st.info("Table details and data preview will be shown here (Task 5)")

    # SQL Generation panel (Task 6)
    with st.expander("💻 Generated SQL", expanded=False):
        st.info("SQL generation and execution will be available here (Task 6)")

        if state_manager.generated_sql:
            st.code(state_manager.generated_sql, language="sql")


if __name__ == "__main__":
    # Setup logging for development
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    main()