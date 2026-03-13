"""MVP 工具服务 - 实现工具的具体逻辑"""
import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# 确认请求标记
NEED_CONFIRM_MARKER = "__NEED_CONFIRM__"

# Token 限制配置
MAX_TABLES = 3
MAX_FIELDS = 10


class MVPToolService:
    """MVP 工具服务

    实现 4 个工具的具体逻辑：
    - search_schema: 搜索表结构
    - execute_sql: 执行SQL
    - list_operations: 列出操作
    - execute_operation: 执行操作
    """

    def __init__(
        self,
        db_manager,
        retrieval_pipeline,
        operation_executor,
        knowledge_loader
    ):
        """初始化工具服务

        Args:
            db_manager: 数据库管理器
            retrieval_pipeline: 检索管道
            operation_executor: 操作执行器
            knowledge_loader: 知识库加载器
        """
        self.db = db_manager
        self.retrieval = retrieval_pipeline
        self.executor = operation_executor
        self.knowledge = knowledge_loader

    def execute(self, tool_name: str, args: dict) -> str:
        """执行工具

        Args:
            tool_name: 工具名称
            args: 工具参数

        Returns:
            str: 执行结果（字符串格式，供模型阅读）
        """
        method = getattr(self, f"_tool_{tool_name}", None)
        if not method:
            return f"错误：未知工具 {tool_name}"

        try:
            return method(**args)
        except Exception as e:
            logger.error(f"Tool {tool_name} failed: {e}", exc_info=True)
            return f"工具执行失败：{str(e)}"

    # ==================== 元数据/结构相关工具 ====================

    def _tool_search_schema(self, query: str) -> str:
        """搜索表结构，返回候选表及完整字段信息

        Args:
            query: 搜索关键词

        Returns:
            str: 候选表列表，每个表包含字段名、类型、注释
        """
        result = self.retrieval.search(query, top_k=10)

        if not result.matches:
            return "未找到相关的表。请尝试其他关键词。"

        # 限制返回表数量（考虑 Token 限制）
        lines = [f"找到 {len(result.matches)} 个相关表（显示前 {MAX_TABLES} 个）："]

        for match in result.matches[:MAX_TABLES]:
            # 跨库表名解析
            # TableMatch.database_name 可能是 None 或空字符串 ""
            # 使用 getattr 默认 ''，然后用 or None 将 falsy 值转为 None
            db_name = getattr(match, 'database_name', '') or None
            table_name = match.table_name

            # 处理 "db.table" 格式（当 TableMatch.database_name 为空时）
            # Also handle the case where database is already embedded in table_name and db_name is provided
            if '.' in table_name and not db_name:
                parts = table_name.split('.', 1)
                db_name = parts[0]
                table_name = parts[1]
            elif '.' in table_name and db_name and table_name.startswith(db_name + "."):
                # If table_name already includes the database name (e.g., "dbname.tablename")
                # and we also have db_name, avoid duplication by removing db_name from table_name
                table_name = table_name.replace(db_name + ".", "", 1)

            display_name = f"{db_name}.{table_name}" if db_name else table_name
            lines.append(f"\n### 表：{display_name}")

            # 获取字段信息（带错误处理）
            try:
                if db_name:
                    # 使用专用的跨库查询方法，参数顺序: (db_name, table_name)
                    schema_info = self.db.get_table_schema_cross_db(db_name, table_name)
                else:
                    schema_info = self.db.get_table_schema(table_name)

                if schema_info:
                    lines.append("字段列表：")
                    for col in schema_info[:MAX_FIELDS]:
                        col_name = col['name']
                        col_type = col['type']
                        col_comment = col.get('comment', '')

                        # 格式：字段名 (类型) -- 注释
                        if col_comment:
                            lines.append(f"  - {col_name} ({col_type}) -- {col_comment}")
                        else:
                            lines.append(f"  - {col_name} ({col_type})")

                    if len(schema_info) > MAX_FIELDS:
                        lines.append(f"  ... 共 {len(schema_info)} 个字段")
                else:
                    lines.append("  （表结构信息为空）")

            except Exception as e:
                logger.warning(f"获取表 {display_name} 结构失败: {e}")
                lines.append(f"  （字段信息获取失败，请尝试直接查询）")

        return "\n".join(lines)

    def _tool_list_tables(self, db_name: Optional[str] = None) -> str:
        """列出部分表名，帮助模型了解有哪些可用表。

        Args:
            db_name: 可选，指定数据库名；不提供时使用当前连接数据库

        Returns:
            str: 表名列表摘要
        """
        try:
            if db_name:
                # 跨库：通过信息_schema.TABLES 获取，避免切换连接
                tables = self.db.get_tables_in_database(db_name)
                prefix = f"数据库 {db_name} 中的表："
            else:
                tables = self.db.get_all_tables()
                prefix = "当前数据库中的表："
        except Exception as e:
            return f"获取表列表失败：{str(e)}"

        if not tables:
            return prefix + "（无表或无法获取）"

        # 限制返回数量，避免输出过长
        max_tables = 50
        display = tables[:max_tables]
        lines = [f"{prefix}（共 {len(tables)} 个，显示前 {len(display)} 个）"]
        for t in display:
            lines.append(f"- {t}")
        if len(tables) > len(display):
            lines.append(f"... 省略 {len(tables) - len(display)} 个表")
        return "\n".join(lines)

    def _tool_describe_table(self, table_name: str, db_name: Optional[str] = None) -> str:
        """查看单表结构信息（字段名、类型、注释）。"""
        try:
            if db_name:
                schema_info = self.db.get_table_schema_cross_db(db_name, table_name)
                display_name = f"{db_name}.{table_name}"
            else:
                schema_info = self.db.get_table_schema(table_name)
                display_name = table_name
        except Exception as e:
            return f"获取表结构失败：{str(e)}"

        if not schema_info:
            return f"未找到表 {display_name} 的结构信息。"

        lines = [f"表 {display_name} 的字段："]
        for col in schema_info[:MAX_FIELDS]:
            col_name = col.get("name", "")
            col_type = col.get("type", "")
            col_comment = col.get("comment") or ""
            if col_comment:
                lines.append(f"- {col_name} ({col_type}) -- {col_comment}")
            else:
                lines.append(f"- {col_name} ({col_type})")
        if len(schema_info) > MAX_FIELDS:
            lines.append(f"... 共 {len(schema_info)} 个字段")
        return "\n".join(lines)

    def _tool_list_indexes(self, table_name: str, db_name: Optional[str] = None) -> str:
        """查看指定表的索引元数据摘要，不返回任何 SQL 文本。"""
        try:
            indexes = self.db.get_table_indexes(db_name, table_name)
        except Exception as e:
            return f"获取索引信息失败：{str(e)}"

        if not indexes:
            full_name = f"{db_name}.{table_name}" if db_name else table_name
            return f"表 {full_name} 未找到索引信息。"

        # 聚合同一索引的多列信息
        by_index: Dict[str, Dict[str, Any]] = {}
        for row in indexes:
            index_name = row.get("index_name") or row.get("INDEX_NAME")
            if not index_name:
                continue
            key = index_name
            info = by_index.setdefault(
                key,
                {
                    "index_name": index_name,
                    "columns": [],
                    "unique": None,
                    "index_type": row.get("index_type") or row.get("INDEX_TYPE") or "",
                },
            )
            # 列顺序
            seq = row.get("seq_in_index") or row.get("SEQ_IN_INDEX") or 0
            column_name = row.get("column_name") or row.get("COLUMN_NAME") or ""
            info["columns"].append((int(seq), column_name))

            # 唯一性：non_unique = 0 表示唯一索引
            non_unique = row.get("non_unique")
            if non_unique is None:
                non_unique = row.get("NON_UNIQUE")
            if non_unique is not None:
                info["unique"] = (int(non_unique) == 0)

        lines = ["索引摘要："]
        for idx_name, info in sorted(by_index.items()):
            cols = sorted(info["columns"], key=lambda x: x[0])
            col_list = ", ".join(c for _, c in cols if c)
            unique_flag = info["unique"]
            if unique_flag is True:
                unique_str = "唯一索引"
            elif unique_flag is False:
                unique_str = "非唯一索引"
            else:
                unique_str = "唯一性未知"
            index_type = info.get("index_type") or ""
            if index_type:
                lines.append(
                    f"- 索引 {idx_name}: 列({col_list})，{unique_str}，类型 {index_type}"
                )
            else:
                lines.append(
                    f"- 索引 {idx_name}: 列({col_list})，{unique_str}"
                )

        return "\n".join(lines)

    # ==================== 只读 SQL & 执行计划 ====================

    @staticmethod
    def _is_readonly_sql(sql: str) -> bool:
        """判断 SQL 是否在只读白名单内。"""
        sql_stripped = sql.lstrip()
        if not sql_stripped:
            return False
        prefix = sql_stripped.upper()
        allowed_prefixes = (
            "SELECT",
            "SHOW",
            "DESC",
            "DESCRIBE",
            "EXPLAIN",
            "WITH",
        )
        return prefix.startswith(allowed_prefixes)

    def _reject_non_readonly(self) -> str:
        return (
            "该 SQL 不在只读白名单内，已拒绝执行。"
            "只允许以 SELECT/SHOW/DESC/DESCRIBE/EXPLAIN/WITH 开头的查询，不允许 INSERT/UPDATE/DELETE/ALTER 等变更或 DDL。"
        )

    def _tool_explain_sql(self, sql: str, purpose: Optional[str] = None) -> str:
        """对只读 SQL 执行 EXPLAIN，返回执行计划摘要。"""
        if not self._is_readonly_sql(sql):
            return self._reject_non_readonly()

        try:
            df = self.db.explain_readonly_sql(sql)
        except Exception as e:
            return f"EXPLAIN 执行失败：{str(e)}"

        if df.empty:
            return "EXPLAIN 未返回任何执行计划行。"

        # 通常 MySQL EXPLAIN 会返回 type/key/possible_keys/rows/Extra 等列
        # 这里只做摘要，不打印 SQL 文本
        summary_lines = ["执行计划摘要："]
        for idx, row in df.iterrows():
            # iterrows() 返回的是 pandas.Series；用 .get 读取列更稳健
            row_type = row.get("type")
            key = row.get("key")
            possible_keys = row.get("possible_keys")
            rows_val = row.get("rows")
            extra = row.get("Extra") if "Extra" in row else row.get("extra")

            parts = []
            if row_type:
                parts.append(f"type={row_type}")
            if key:
                parts.append(f"使用索引 key={key}")
            elif possible_keys:
                parts.append(f"可能使用索引 possible_keys={possible_keys}")
            if rows_val is not None:
                parts.append(f"预估扫描行数 rows={rows_val}")
            if extra:
                parts.append(f"Extra={extra}")

            is_full_scan = (str(row_type).lower() == "all") if row_type else False
            if is_full_scan:
                parts.append("⚠️ 可能是全表扫描")

            summary_lines.append(f"- 步骤 {idx}: " + "，".join(parts))

        if purpose:
            summary_lines.append(f"\n分析目的：{purpose}")
        return "\n".join(summary_lines)

    def _tool_run_readonly_sql(self, sql: str, purpose: Optional[str] = None) -> str:
        """在只读白名单下执行 SQL，返回 DataFrame 摘要（行数 + head），不输出 SQL 原文。"""
        if not self._is_readonly_sql(sql):
            return self._reject_non_readonly()

        try:
            df = self.db.execute_query(sql)
        except Exception as e:
            return f"只读查询执行失败：{str(e)}"

        total_rows = len(df)
        if total_rows == 0:
            base = "只读查询执行成功，但结果为空。"
            if purpose:
                return base + f"（目的：{purpose}）"
            return base

        head_rows = min(20, total_rows)
        display_df = df.head(head_rows)
        lines = [f"只读查询返回 {total_rows} 行数据，显示前 {head_rows} 行："]
        lines.append(display_df.to_string(index=False))
        if total_rows > head_rows:
            lines.append(f"... 省略 {total_rows - head_rows} 行")
        if purpose:
            lines.append(f"\n查询目的：{purpose}")
        return "\n".join(lines)

    def _tool_execute_sql(self, sql: str, description: str = None) -> str:
        """执行SQL

        Args:
            sql: SQL语句
            description: 操作描述

        Returns:
            str: 执行结果
        """
        sql_upper = sql.strip().upper()

        # SELECT 查询直接执行
        if sql_upper.startswith("SELECT") or sql_upper.startswith("SHOW") or sql_upper.startswith("DESC"):
            try:
                df = self.db.execute_query(sql)
                if df.empty:
                    return "查询结果为空。"

                # 限制显示行数
                display_df = df.head(20)
                result = f"查询返回 {len(df)} 行数据：\n"
                result += display_df.to_string(index=False)

                if len(df) > 20:
                    result += f"\n... 省略 {len(df) - 20} 行"

                return result
            except Exception as e:
                return f"查询失败：{str(e)}"

        # 修改操作需要确认
        return f"{NEED_CONFIRM_MARKER}\n操作：{description or '执行SQL'}\nSQL：{sql}"

    # ==================== 业务操作与 skills（占位实现） ====================

    def _tool_list_operations(self) -> str:
        """列出可用操作

        Returns:
            str: 操作列表
        """
        operations_dict = self.knowledge.get_all_operations()
        operations = list(operations_dict.values())

        if not operations:
            return "暂无预定义操作。"

        lines = ["可用的业务操作："]
        for i, op in enumerate(operations[:20]):  # 限制显示数量
            lines.append(f"- {op.id}: {op.name}")
            if op.description:
                lines.append(f"  {op.description[:50]}")

        if len(operations) > 20:
            lines.append(f"... 共 {len(operations)} 个操作")

        return "\n".join(lines)

    def _tool_execute_operation(self, operation_id: str, params: dict = None) -> str:
        """执行预定义操作

        Args:
            operation_id: 操作ID
            params: 操作参数

        Returns:
            str: 执行结果
        """
        params = params or {}

        # 先预览
        preview_result = self.executor.execute_operation(
            operation_id,
            params,
            preview_only=True
        )

        if not preview_result.success:
            return f"操作预览失败：{preview_result.error}"

        # 检查是否是修改操作
        op = self.knowledge.get_operation(operation_id)
        if op and op.is_mutation():
            # 返回预览信息，需要确认
            return f"{NEED_CONFIRM_MARKER}\n操作：{op.name}\n预览：{preview_result.summary or '即将执行'}"

        # 查询操作直接执行
        result = self.executor.execute_operation(
            operation_id,
            params,
            preview_only=False
        )

        if result.success:
            return f"操作成功：{result.summary or '已完成'}"
        else:
            return f"操作失败：{result.error}"

    def _tool_find_skills(self, query: str) -> str:
        from src.skills.skills_cli import find_skills

        result = find_skills(query)
        return json.dumps(result.to_dict(), ensure_ascii=False, indent=2)

    def _tool_install_skill(self, spec: str, global_install: bool = True) -> str:
        from src.skills.skills_cli import install_skill

        result = install_skill(spec, global_install=global_install)
        return json.dumps(result.to_dict(), ensure_ascii=False, indent=2)

    def confirm_and_execute_sql(self, sql: str) -> str:
        """确认后执行SQL

        Args:
            sql: SQL语句

        Returns:
            str: 执行结果
        """
        try:
            affected = self.db.execute_update(sql)
            return f"执行成功，影响 {affected} 行。"
        except Exception as e:
            return f"执行失败：{str(e)}"

    def confirm_and_execute_operation(self, operation_id: str, params: dict) -> str:
        """确认后执行操作

        Args:
            operation_id: 操作ID
            params: 操作参数

        Returns:
            str: 执行结果
        """
        result = self.executor.execute_operation(
            operation_id,
            params,
            preview_only=False,
            auto_commit=True
        )

        if result.success:
            return f"操作成功：{result.summary or '已完成'}"
        else:
            return f"操作失败：{result.error}"
