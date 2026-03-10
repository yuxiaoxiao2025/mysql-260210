"""
SQL Generator Service for Knowledge Graph Explorer.

Generates SQL queries using LLM based on user query, table schemas, and join paths.
"""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
from sqlalchemy.exc import SQLAlchemyError, NoSuchTableError

from src.llm_client import LLMClient
from src.db_manager import DatabaseManager
from src.web.services.graph_service import KnowledgeGraphService

logger = logging.getLogger(__name__)

# Lazy import for networkx (optional dependency)
nx = None
try:
    import networkx as nx
except ImportError:
    logger.warning("networkx not available, join path finding disabled")


class SQLGenerator:
    """Service for generating SQL queries using LLM."""

    SYSTEM_PROMPT = """你是一个专业的 SQL 开发者。根据用户的需求描述和表结构，生成对应的 SQL 查询语句。

要求：
1. 只生成 SELECT 查询（禁止 INSERT/UPDATE/DELETE）
2. 使用合适的 JOIN 关联表
3. 添加必要的 WHERE 条件
4. 使用有意义的列别名
5. 如果不确定列名，使用 * 或列出主要列
6. 返回纯 SQL 语句，不要包含解释

表结构格式：
- 表名: {table_name}
  - 注释: {comment}
  - 列: {columns}"""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        db_manager: Optional[DatabaseManager] = None,
        graph_service: Optional[KnowledgeGraphService] = None
    ):
        """Initialize SQL Generator.

        Args:
            llm_client: LLM client for generating SQL
            db_manager: Database manager for schema and execution
            graph_service: Graph service for finding join paths
        """
        self.llm_client = llm_client or LLMClient()
        self.db_manager = db_manager or DatabaseManager()
        self.graph_service = graph_service

        # Conversation history for refine
        self._history: List[Dict[str, str]] = []

    def _validate_identifier(self, name: str) -> bool:
        """Validate database identifier (table/schema name).

        MySQL identifier rules:
        - Max 64 characters
        - Start with letter or underscore
        - Contain only alphanumeric, underscore
        """
        if not name or len(name) > 64:
            return False
        return bool(re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name))

    def _build_table_context(
        self,
        table_names: List[str],
        include_join_paths: bool = True
    ) -> str:
        """Build table context for LLM prompt.

        Args:
            table_names: List of table names
            include_join_paths: Whether to include join paths

        Returns:
            Formatted table context string
        """
        context_parts = []

        for table_name in table_names:
            try:
                # Parse schema.table format
                parts = table_name.split('.', 1)
                db_schema = parts[0] if len(parts) > 1 else ''
                tbl_name = parts[1] if len(parts) > 1 else parts[0]

                # Validate identifiers
                if db_schema and not self._validate_identifier(db_schema):
                    logger.warning(f"Invalid schema name: {db_schema}")
                    continue
                if not tbl_name or not self._validate_identifier(tbl_name):
                    logger.warning(f"Invalid table name: {tbl_name}")
                    continue

                # Get schema
                if db_schema and tbl_name:
                    schema = self.db_manager.get_table_schema_cross_db(db_schema, tbl_name)
                else:
                    schema = self.db_manager.get_table_schema(table_name)

                columns = [f"{c['name']} ({c['type']})" for c in schema]
                comment = schema[0].get('comment', '') if schema else ''

                table_info = f"- 表名: {table_name}\n  - 注释: {comment}\n  - 列: {', '.join(columns)}"
                context_parts.append(table_info)
            except (SQLAlchemyError, NoSuchTableError) as e:
                logger.warning(f"Database error getting schema for {table_name}: {e}")
            except Exception as e:
                logger.error(f"Unexpected error getting schema for {table_name}: {e}")

        # Add join paths if requested
        if include_join_paths and self.graph_service and len(table_names) > 1:
            context_parts.append("\n表之间的关系:")
            for i in range(len(table_names)):
                for j in range(i + 1, len(table_names)):
                    path = self._find_join_path(table_names[i], table_names[j])
                    if path:
                        context_parts.append(f"- {table_names[i]} -> {table_names[j]}: {' -> '.join(path)}")

        return "\n\n".join(context_parts)

    def _find_join_path(self, source: str, target: str) -> Optional[List[str]]:
        """Find join path between two tables.

        Args:
            source: Source table
            target: Target table

        Returns:
            List of tables in path, or None
        """
        if not self.graph_service or nx is None:
            return None

        try:
            G = self.graph_service.graph
            if source in G and target in G:
                return nx.shortest_path(G, source, target)
        except Exception:
            pass
        return None

    def _call_llm(self, messages: List[Dict[str, str]]) -> str:
        """Call LLM with messages.

        Args:
            messages: List of message dicts with 'role' and 'content'

        Returns:
            LLM response content
        """
        # Use the LLMClient's generate_sql method which handles the API call
        # Convert messages to a single prompt for generate_sql
        system_prompt = messages[0]["content"] if messages and messages[0]["role"] == "system" else ""
        user_prompt = messages[-1]["content"] if messages else ""

        try:
            # Use generate_sql which returns a dict with 'sql' key
            result = self.llm_client.generate_sql(
                user_query=user_prompt.replace(system_prompt, "").strip(),
                schema_context=system_prompt
            )
            return result.get("sql", "")
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise

    def generate_sql(
        self,
        user_query: str,
        selected_tables: List[str],
        include_join_paths: bool = True
    ) -> str:
        """Generate SQL from user query and selected tables.

        Args:
            user_query: User's natural language query
            selected_tables: List of selected table names
            include_join_paths: Whether to include join info

        Returns:
            Generated SQL query string
        """
        # Build context
        table_context = self._build_table_context(selected_tables, include_join_paths)

        # Build prompt
        user_prompt = f"""用户需求: {user_query}

表结构:
{table_context}

请生成对应的 SQL 查询语句。"""

        # Call LLM
        try:
            # Use generate_sql method
            response = self.llm_client.generate_sql(
                user_query=user_prompt,
                schema_context=self.SYSTEM_PROMPT
            )

            # Extract SQL from response
            sql = self._extract_sql(response.get("sql", str(response)))

            # Add to history
            self._history.append({
                "query": user_query,
                "sql": sql,
                "tables": ", ".join(selected_tables)
            })

            return sql
        except Exception as e:
            logger.error(f"Failed to generate SQL: {e}")
            return f"-- Error generating SQL: {e}"

    def _extract_sql(self, response: str) -> str:
        """Extract SQL from LLM response.

        Args:
            response: LLM response string

        Returns:
            Extracted SQL or original if no code block
        """
        # Try to extract from code block
        sql_match = re.search(r"```sql\n(.*?)```", response, re.DOTALL)
        if sql_match:
            return sql_match.group(1).strip()

        # Try generic code block
        sql_match = re.search(r"```\n(.*?)```", response, re.DOTALL)
        if sql_match:
            return sql_match.group(1).strip()

        return response.strip()

    def refine_sql(
        self,
        user_query: str,
        current_sql: str,
        selected_tables: List[str],
        refinement_hint: str
    ) -> str:
        """Refine existing SQL based on user feedback.

        Args:
            user_query: Original user query
            current_sql: Current SQL to refine
            selected_tables: Selected table names
            refinement_hint: User's refinement instruction

        Returns:
            Refined SQL
        """
        # Build prompt with history
        table_context = self._build_table_context(selected_tables)

        user_prompt = f"""用户需求: {user_query}

当前 SQL:
{current_sql}

修改要求: {refinement_hint}

表结构:
{table_context}

请根据修改要求生成新的 SQL。"""

        try:
            response = self.llm_client.generate_sql(
                user_query=user_prompt,
                schema_context=self.SYSTEM_PROMPT
            )

            return self._extract_sql(response.get("sql", str(response)))
        except Exception as e:
            logger.error(f"Failed to refine SQL: {e}")
            return current_sql

    def execute_sql(self, sql: str) -> Tuple[bool, pd.DataFrame, str]:
        """Execute SQL query.

        Args:
            sql: SQL query to execute

        Returns:
            Tuple of (success, dataframe, error_message)
        """
        # Safety check
        sql_upper = sql.upper().strip()
        if any(sql_upper.startswith(kw) for kw in ["INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE", "ALTER"]):
            return False, pd.DataFrame(), "只允许执行 SELECT 查询"

        try:
            result = self.db_manager.execute_query(sql)
            return True, result, ""
        except Exception as e:
            return False, pd.DataFrame(), str(e)

    @property
    def history(self) -> List[Dict[str, str]]:
        """Get generation history."""
        return self._history