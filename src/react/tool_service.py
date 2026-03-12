"""MVP 工具服务 - 实现工具的具体逻辑"""
import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# 确认请求标记
NEED_CONFIRM_MARKER = "__NEED_CONFIRM__"


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

    def _tool_search_schema(self, query: str) -> str:
        """搜索表结构

        Args:
            query: 搜索关键词

        Returns:
            str: 相关表的信息
        """
        result = self.retrieval.search(query, top_k=5)

        if not result.matches:
            return "未找到相关的表。请尝试其他关键词。"

        lines = ["找到以下相关表："]
        for match in result.matches:
            table_name = match.table_name
            # description 可能在不同位置
            description = getattr(match, 'description', None) or ""
            lines.append(f"- {table_name}")
            if description:
                lines.append(f"  说明：{description[:100]}")

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