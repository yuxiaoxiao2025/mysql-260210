"""Web components package."""

from src.web.components.graph_view import (
    get_color_for_node,
    render_graph_view,
    render_empty_graph,
)
from src.web.components.detail_panel import (
    get_table_columns,
    find_join_path,
    render_table_detail,
    render_multi_table_preview,
    render_detail_panel,
)

__all__ = [
    "get_color_for_node",
    "render_graph_view",
    "render_empty_graph",
    "get_table_columns",
    "find_join_path",
    "render_table_detail",
    "render_multi_table_preview",
    "render_detail_panel",
]