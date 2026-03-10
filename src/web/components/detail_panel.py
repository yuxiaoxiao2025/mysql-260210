"""
Detail Panel Component for Knowledge Graph Explorer.

Shows table details, data sampling, and multi-table combination preview.
"""

import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.exc import SQLAlchemyError, NoSuchTableError

import pandas as pd
import streamlit as st

import networkx as nx

from src.db_manager import DatabaseManager
from src.web.services.graph_service import KnowledgeGraphService
from src.web.utils.validators import validate_identifier

logger = logging.getLogger(__name__)


def get_table_columns(db_manager: DatabaseManager, table_name: str) -> List[Dict[str, Any]]:
    """Get column metadata for a table.

    Supports both 'table_name' and 'schema.table_name' formats.

    Args:
        db_manager: DatabaseManager instance
        table_name: Table name (can be 'table' or 'schema.table' format)

    Returns:
        List of column metadata dicts, empty list on error
    """
    # Input validation
    if not table_name or not isinstance(table_name, str):
        logger.warning("Invalid table_name: must be non-empty string")
        return []

    # Parse schema.table format
    schema, _, tbl_name = table_name.partition('.')

    # Validate parsed components - only validate if they're standalone (not in schema.table format)

    try:
        if '.' in table_name:
            # Has schema.table format - split on first dot
            schema, _, tbl_name = table_name.partition('.')
            # Validate schema (must be simple identifier)
            if not validate_identifier(schema):
                logger.warning(f"Invalid schema name: {schema}")
                return []
            # Validate table name is not empty
            if not tbl_name:
                logger.warning(f"Invalid table name format: {table_name}")
                return []
            return db_manager.get_table_schema_cross_db(schema, tbl_name)
        else:
            # Simple table name
            if not validate_identifier(table_name):
                logger.warning(f"Invalid table name: {table_name}")
                return []
            return db_manager.get_table_schema(table_name)
    except (SQLAlchemyError, NoSuchTableError) as e:
        logger.warning(f"Database error getting schema for {table_name}: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error getting schema for {table_name}: {e}")
        return []


def find_join_path(
    graph_service: KnowledgeGraphService,
    source_table: str,
    target_table: str
) -> Optional[List[str]]:
    """Find the shortest join path between two tables.

    Args:
        graph_service: KnowledgeGraphService instance
        source_table: Source table name
        target_table: Target table name

    Returns:
        List of table names representing the join path, or None if no path
    """
    try:
        G = graph_service.graph
        if source_table not in G or target_table not in G:
            return None

        path = nx.shortest_path(G, source_table, target_table)
        return path
    except (nx.NodeNotFound, nx.NetworkXNoPath):
        return None


def render_table_detail(
    db_manager: DatabaseManager,
    table_name: str
) -> None:
    """Render detail view for a single table.

    Args:
        db_manager: DatabaseManager instance
        table_name: Table name to display
    """
    st.subheader(f"📋 {table_name}")

    # Get column metadata
    columns = get_table_columns(db_manager, table_name)

    if columns:
        col_info = []
        for col in columns:
            col_info.append({
                "Column": col.get("name", ""),
                "Type": col.get("type", ""),
                "Nullable": "",
                "Comment": col.get("comment", ""),
                "Key": ""
            })

        st.write("**列信息:**")
        st.dataframe(pd.DataFrame(col_info), use_container_width=True, hide_index=True)

    # Get sample data
    st.write("**数据样本:**")
    # Parse schema.table format for sample_data call
    schema, _, tbl_name = table_name.partition('.')

    # Validate before querying
    if schema and tbl_name and validate_identifier(schema) and validate_identifier(tbl_name):
        sample = db_manager.sample_data(tbl_name, schema=schema)
    elif tbl_name and validate_identifier(tbl_name):
        sample = db_manager.sample_data(tbl_name)
    else:
        logger.warning(f"Invalid table name for sample_data: {table_name}")
        sample = pd.DataFrame()

    if not sample.empty:
        st.dataframe(sample, use_container_width=True)
    else:
        st.warning("无法获取样本数据")


def render_multi_table_preview(
    db_manager: DatabaseManager,
    graph_service: KnowledgeGraphService,
    table_names: List[str]
) -> None:
    """Render preview for multiple selected tables.

    Args:
        db_manager: DatabaseManager instance
        graph_service: KnowledgeGraphService instance
        table_names: List of selected table names
    """
    if len(table_names) < 2:
        return

    st.subheader("🔗 多表关联预览")

    # Find join paths between all pairs
    all_joins = []
    for i in range(len(table_names)):
        for j in range(i + 1, len(table_names)):
            path = find_join_path(graph_service, table_names[i], table_names[j])
            if path:
                all_joins.append({
                    "from": table_names[i],
                    "to": table_names[j],
                    "path": " → ".join(path),
                    "hops": len(path) - 1
                })

    if all_joins:
        st.write("**发现的关系:**")
        st.dataframe(pd.DataFrame(all_joins), use_container_width=True, hide_index=True)

        # Generate sample JOIN query (for demonstration only)
        # Note: Table names come from graph metadata, not user input
        # In production, use parameterized queries with validated table names
        st.write("**JOIN 示例查询:**")

        # Simple two-table join
        sample_joins = all_joins[0]
        if sample_joins["hops"] == 1:
            # Direct join
            join_sql = f"""SELECT *
FROM {sample_joins['from']} a
JOIN {sample_joins['to']} b ON a.id = b.foreign_key_id
LIMIT 5"""
        else:
            # Multi-hop join
            path_tables = sample_joins['path'].split(" → ")
            join_parts = []
            for i in range(len(path_tables) - 1):
                join_parts.append(f"JOIN {path_tables[i+1]} ON {path_tables[i]}.id = {path_tables[i+1]}.fk_id")
            join_sql = f"""SELECT *
FROM {path_tables[0]} a
{" ".join(join_parts)}
LIMIT 5"""

        st.code(join_sql, language="sql")

        # Execute and show result
        if st.button("🔍 执行预览查询"):
            try:
                result = db_manager.execute_query(join_sql)
                if not result.empty:
                    st.dataframe(result, use_container_width=True)
            except Exception as e:
                st.error(f"查询失败：{e}")
    else:
        st.warning("未找到表之间的关系")


def render_detail_panel(
    db_manager: DatabaseManager,
    graph_service: KnowledgeGraphService,
    selected_tables: List[str]
) -> None:
    """Render the complete detail panel.

    Args:
        db_manager: DatabaseManager instance
        graph_service: KnowledgeGraphService instance
        selected_tables: List of selected table names
    """
    if not selected_tables:
        st.info("👆 选择表以查看详情")
        return

    st.header("📝 表详情")

    # Single table view
    if len(selected_tables) == 1:
        render_table_detail(db_manager, selected_tables[0])
    # Multi-table view
    else:
        render_multi_table_preview(db_manager, graph_service, selected_tables)
