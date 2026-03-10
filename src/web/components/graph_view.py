"""
Graph Visualization Component for Knowledge Graph Explorer.

Renders interactive knowledge graph using streamlit-agraph.
"""

import logging
from typing import List, Dict, Any, Callable, Optional

import streamlit as st
from streamlit_agraph import agraph, Node, Edge, Config

from src.web.services.graph_service import KnowledgeGraphService

logger = logging.getLogger(__name__)


def get_color_for_node(node_id: str, selected_tables: List[str], top_ranked: List[str] = None) -> str:
    """Determine node color based on selection state.

    Args:
        node_id: Table name
        selected_tables: Currently selected tables
        top_ranked: Top ranked tables from search (optional)

    Returns:
        Color hex code
    """
    if node_id in selected_tables:
        return "#22c55e"  # Green - selected
    elif top_ranked and node_id in top_ranked:
        return "#3b82f6"  # Blue - top ranked
    else:
        return "#9ca3af"  # Grey - neighbor


def render_graph_view(
    graph_service: KnowledgeGraphService,
    selected_tables: List[str],
    top_ranked: Optional[List[str]] = None,
    on_node_click: Optional[Callable[[str], None]] = None
) -> Optional[str]:
    """Render the knowledge graph visualization.

    Args:
        graph_service: KnowledgeGraphService instance
        selected_tables: Currently selected table names
        top_ranked: Top ranked tables from search (optional)
        on_node_click: Callback when node is clicked (optional)

    Returns:
        Clicked node ID or None
    """
    # Get subgraph for selected tables
    try:
        if selected_tables:
            subgraph_data = graph_service.get_subgraph_for_tables(selected_tables)
            nodes_data = subgraph_data.get("nodes", [])
            edges_data = subgraph_data.get("edges", [])
        else:
            # Show full graph or empty state
            nodes_data, edges_data = [], []
    except Exception as e:
        logger.error(f"Failed to get subgraph: {e}")
        st.error(f"Failed to load graph data: {e}")
        return None

    # Convert to agraph format
    nodes = [
        Node(
            id=n["id"],
            label=n["label"],
            color=get_color_for_node(n["id"], selected_tables, top_ranked),
            size=25 if n["id"] in selected_tables else 15,
            title=n.get("table_comment", ""),  # tooltip
        )
        for n in nodes_data
    ]

    edges = [
        Edge(
            source=e["source"],
            target=e["target"],
            label=e.get("relationship", ""),
            type="CURVED_SMOOTH",
            color="#94a3b8",
        )
        for e in edges_data
    ]

    # Configure graph
    config = Config(
        width=800,
        height=500,
        directed=True,
        physics=True,
        hierarchical=False,
        interaction={"hover": True},  # Only keep supported parameter
        nodes={"font": {"size": 14, "face": "Arial"}},
        edges={"font": {"size": 10, "face": "Arial"}},
    )

    # Render graph
    return_value = agraph(nodes=nodes, edges=edges, config=config)

    # Handle click (streamlit-agraph returns clicked node)
    if return_value and on_node_click:
        on_node_click(return_value)

    return return_value


def render_empty_graph() -> None:
    """Render empty graph placeholder."""
    st.info("Click nodes to select tables, or search for tables above")
