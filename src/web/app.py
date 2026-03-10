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
from src.web.components.graph_view import render_graph_view, render_empty_graph
from src.web.components.detail_panel import render_detail_panel
from src.web.services.graph_service import KnowledgeGraphService
from src.web.services.rerank_service import RerankService
from src.web.services.sql_generator import SQLGenerator
from src.metadata.schema_indexer import SchemaIndexer
from src.metadata.embedding_service import EmbeddingService
from src.db_manager import DatabaseManager

logger = logging.getLogger(__name__)

# Page config
st.set_page_config(
    page_title="Knowledge Graph Explorer",
    page_icon="🗄️",
    layout="wide",
    initial_sidebar_state="expanded",
)


def init_services():
    """Initialize backend services."""
    # Create service instances
    db_manager = DatabaseManager()
    embedding_service = EmbeddingService()
    schema_indexer = SchemaIndexer(
        db_manager=db_manager,
        embedding_service=embedding_service,
        env="dev"
    )

    # Create services
    graph_service = KnowledgeGraphService(schema_indexer)
    rerank_service = RerankService(
        graph_store=schema_indexer.graph_store,
        embedding_service=embedding_service
    )
    sql_generator = SQLGenerator(
        db_manager=db_manager,
        graph_service=graph_service
    )

    return {
        "db_manager": db_manager,
        "graph_service": graph_service,
        "rerank_service": rerank_service,
        "sql_generator": sql_generator,
    }


def handle_search(services, query_text, state_manager):
    """Handle search action and update state."""
    rerank_service = services["rerank_service"]

    try:
        # Search and rank tables
        results = rerank_service.search_and_rank(query_text, top_k=10)

        # Update search results in state
        state_manager.search_results = [
            {"table": r[0], "score": r[1], "reason": r[2]}
            for r in results
        ]

        # Auto-select top result
        if results:
            top_table = results[0][0]
            if top_table not in state_manager.selected_tables:
                state_manager.add_selected_table(top_table)

    except Exception as e:
        st.error(f"搜索失败: {e}")
        logger.error(f"Search error: {e}")


def handle_generate_sql(services, state_manager):
    """Generate SQL from selected tables."""
    sql_generator = services["sql_generator"]

    if not state_manager.selected_tables:
        return None

    try:
        sql = sql_generator.generate_sql(
            user_query=state_manager.current_query,
            selected_tables=state_manager.selected_tables
        )
        state_manager.generated_sql = sql
        return sql
    except Exception as e:
        st.error(f"SQL 生成失败: {e}")
        logger.error(f"SQL generation error: {e}")
        return None


def main():
    """Main application entry point."""
    st.title("🗄️ Knowledge Graph Explorer")
    st.markdown("Interactive database explorer with Knowledge Graph visualization")

    # Initialize state manager
    state_manager = StateManager()

    # Initialize services (cached for performance)
    if "services" not in st.session_state:
        st.session_state["services"] = init_services()

    services = st.session_state["services"]

    # Render sidebar and get query
    query_text, search_clicked = render_sidebar(state_manager)

    # Handle search action
    if search_clicked and query_text:
        handle_search(services, query_text, state_manager)
        state_manager.save_to_history()

    # Main content area
    col1, col2 = st.columns([2, 1])

    with col1:
        st.header("📊 Graph View")

        # Render graph visualization
        if state_manager.selected_tables:
            try:
                clicked_node = render_graph_view(
                    graph_service=services["graph_service"],
                    selected_tables=state_manager.selected_tables,
                    on_node_click=lambda node: state_manager.add_selected_table(node)
                )

                if clicked_node and clicked_node not in state_manager.selected_tables:
                    state_manager.add_selected_table(clicked_node)

                st.write(f"**Selected Tables:** {', '.join(state_manager.selected_tables)}")
            except Exception as e:
                st.error(f"图视图加载失败: {e}")
                logger.error(f"Graph view error: {e}")
                st.write(f"**Selected Tables:** {', '.join(state_manager.selected_tables)}")
        else:
            render_empty_graph()

    with col2:
        st.header("📋 Search Results")

        if state_manager.search_results:
            for result in state_manager.search_results:
                with st.container():
                    col_btn, col_info = st.columns([1, 3])

                    with col_btn:
                        if st.button("➕", key=f"add_{result['table']}"):
                            state_manager.add_selected_table(result["table"])
                            st.rerun()

                    with col_info:
                        st.markdown(f"**{result['table']}**")
                        st.caption(f"Score: {result['score']:.2f}")
                        if result.get("reason"):
                            st.caption(result["reason"][:100])
        else:
            st.info("Enter a query to search for tables")

    # Detail panel
    st.divider()
    try:
        render_detail_panel(
            db_manager=services["db_manager"],
            graph_service=services["graph_service"],
            selected_tables=state_manager.selected_tables
        )
    except Exception as e:
        st.error(f"表详情加载失败: {e}")
        logger.error(f"Detail panel error: {e}")

    # SQL Generation panel
    with st.expander("💻 Generated SQL", expanded=bool(state_manager.generated_sql)):
        if state_manager.selected_tables:
            if st.button("🔮 Generate SQL", use_container_width=True):
                handle_generate_sql(services, state_manager)

        if state_manager.generated_sql:
            st.code(state_manager.generated_sql, language="sql")

            # Execute SQL
            if st.button("▶️ Run Query", use_container_width=True):
                sql_generator = services["sql_generator"]
                success, result, error = sql_generator.execute_sql(state_manager.generated_sql)

                if success:
                    st.success(f"✅ Returned {len(result)} rows")
                    st.dataframe(result, use_container_width=True)
                else:
                    st.error(f"❌ Query failed: {error}")

            # Refine SQL
            with st.expander("✏️ Refine Query"):
                refine_hint = st.text_input("修改要求:", placeholder="e.g., 添加日期过滤条件")
                if st.button("Apply Refinement") and refine_hint:
                    sql_generator = services["sql_generator"]
                    refined_sql = sql_generator.refine_sql(
                        user_query=state_manager.current_query,
                        current_sql=state_manager.generated_sql,
                        selected_tables=state_manager.selected_tables,
                        refinement_hint=refine_hint
                    )
                    if refined_sql:
                        state_manager.generated_sql = refined_sql
                        st.rerun()
        else:
            st.info("Select tables and click Generate SQL")


if __name__ == "__main__":
    # Setup logging for development
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    main()