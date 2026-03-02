"""
操作执行器

安全执行业务操作，支持参数校验、预览生成和事务执行。
"""

import logging
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class StepPreview:
    """步骤预览结果"""
    step_name: str
    sql: str
    before: List[Dict] = field(default_factory=list)
    after: List[Dict] = field(default_factory=list)
    affected_rows: int = 0
    error: Optional[str] = None


@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    operation_id: str
    operation_name: str
    previews: List[StepPreview] = field(default_factory=list)
    executed: bool = False
    error: Optional[str] = None
    summary: str = ""


class OperationExecutor:
    """操作执行器"""

    def __init__(self, db_manager, knowledge_loader):
        """
        初始化操作执行器

        Args:
            db_manager: 数据库管理器
            knowledge_loader: 知识库加载器
        """
        self.db_manager = db_manager
        self.knowledge_loader = knowledge_loader

    def execute_operation(
        self,
        operation_id: str,
        params: Dict[str, Any],
        preview_only: bool = True,
        auto_commit: bool = False
    ) -> ExecutionResult:
        """
        执行业务操作

        Args:
            operation_id: 操作ID
            params: 参数字典
            preview_only: 是否仅预览（不执行）
            auto_commit: 是否自动提交（跳过确认）

        Returns:
            ExecutionResult 执行结果
        """
        # 1. 获取操作模板
        operation = self.knowledge_loader.get_operation(operation_id)
        if not operation:
            return ExecutionResult(
                success=False,
                operation_id=operation_id,
                operation_name="",
                error=f"未找到操作模板: {operation_id}"
            )

        # 2. 校验参数
        validation_result = self._validate_params(operation, params)
        if not validation_result["valid"]:
            return ExecutionResult(
                success=False,
                operation_id=operation_id,
                operation_name=operation.name,
                error=validation_result["error"]
            )

        # 3. 补全参数默认值
        params = self._fill_default_params(operation, params)

        # 4. 根据操作类型执行
        if operation.is_query():
            return self._execute_query(operation, params)
        else:
            return self._execute_mutation(operation, params, preview_only, auto_commit)

    def _validate_params(self, operation, params: Dict[str, Any]) -> Dict:
        """
        校验参数

        Args:
            operation: 操作模板
            params: 参数字典

        Returns:
            {"valid": bool, "error": str}
        """
        for param in operation.params:
            if param.required and param.name not in params:
                return {
                    "valid": False,
                    "error": f"缺少必需参数: {param.name} ({param.description})"
                }

            value = params.get(param.name)
            if value is None:
                continue

            # 类型校验
            if param.type == "int":
                if not isinstance(value, (int, str)) or (isinstance(value, str) and not value.isdigit()):
                    return {
                        "valid": False,
                        "error": f"参数 {param.name} 必须是整数"
                    }
                value = int(value)

            # 范围校验
            if param.type == "int":
                if param.min is not None and value < param.min:
                    return {
                        "valid": False,
                        "error": f"参数 {param.name} 不能小于 {param.min}"
                    }
                if param.max is not None and value > param.max:
                    return {
                        "valid": False,
                        "error": f"参数 {param.name} 不能大于 {param.max}"
                    }

            # 正则校验
            if param.pattern and isinstance(value, str):
                if not re.match(param.pattern, value.upper() if "京津沪" in param.pattern else value):
                    return {
                        "valid": False,
                        "error": f"参数 {param.name} 格式不正确"
                    }

            # 枚举校验
            if param.enum_from:
                validated = self.knowledge_loader.lookup_enum_value(param.enum_from, str(value))
                if not validated:
                    available = self.knowledge_loader.get_enum_values_flat(param.enum_from)
                    return {
                        "valid": False,
                        "error": f"参数 {param.name} 的值 '{value}' 无效，可选值: {', '.join(available[:5])}..."
                    }

        return {"valid": True, "error": ""}

    def _fill_default_params(self, operation, params: Dict[str, Any]) -> Dict[str, Any]:
        """填充默认参数值"""
        filled = dict(params)
        for param in operation.params:
            if param.name not in filled and param.default is not None:
                # 处理特殊默认值
                if param.default == "NOW()":
                    from datetime import datetime
                    filled[param.name] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                else:
                    filled[param.name] = param.default
        return filled

    def _execute_query(self, operation, params: Dict[str, Any]) -> ExecutionResult:
        """
        执行查询操作

        Args:
            operation: 操作模板
            params: 参数字典

        Returns:
            ExecutionResult
        """
        if not operation.sql:
            return ExecutionResult(
                success=False,
                operation_id=operation.id,
                operation_name=operation.name,
                error="查询操作缺少 SQL 定义"
            )

        try:
            # 替换参数
            sql = self._render_sql(operation.sql, params)

            # 执行查询
            df = self.db_manager.execute_query(sql)

            # 转换为字典列表
            results = df.to_dict('records')

            preview = StepPreview(
                step_name="查询结果",
                sql=sql,
                before=[],
                after=results,
                affected_rows=len(results)
            )

            return ExecutionResult(
                success=True,
                operation_id=operation.id,
                operation_name=operation.name,
                previews=[preview],
                executed=True,
                summary=f"查询成功，返回 {len(results)} 条记录"
            )

        except Exception as e:
            logger.error(f"查询执行失败: {e}")
            return ExecutionResult(
                success=False,
                operation_id=operation.id,
                operation_name=operation.name,
                error=f"查询执行失败: {str(e)}"
            )

    def _execute_mutation(
        self,
        operation,
        params: Dict[str, Any],
        preview_only: bool,
        auto_commit: bool
    ) -> ExecutionResult:
        """
        执行变更操作

        Args:
            operation: 操作模板
            params: 参数字典
            preview_only: 是否仅预览
            auto_commit: 是否自动提交

        Returns:
            ExecutionResult
        """
        if not operation.steps:
            return ExecutionResult(
                success=False,
                operation_id=operation.id,
                operation_name=operation.name,
                error="变更操作缺少执行步骤"
            )

        previews = []

        try:
            # 生成每个步骤的预览
            for step in operation.steps:
                sql = self._render_sql(step.sql, params)

                # 生成预览 SQL（SELECT 形式）
                preview_sql = self._generate_preview_sql(sql, step.affects_rows)

                # 获取执行前数据
                before_data = []
                if preview_sql:
                    try:
                        before_df = self.db_manager.execute_query(preview_sql)
                        before_data = before_df.to_dict('records')
                    except Exception as e:
                        logger.warning(f"获取预览数据失败: {e}")

                preview = StepPreview(
                    step_name=step.name,
                    sql=sql,
                    before=before_data,
                    after=[],  # 执行后填充
                    affected_rows=len(before_data)
                )
                previews.append(preview)

            # 如果仅预览，返回结果
            if preview_only:
                return ExecutionResult(
                    success=True,
                    operation_id=operation.id,
                    operation_name=operation.name,
                    previews=previews,
                    executed=False,
                    summary=f"预览完成，共 {len(previews)} 个步骤"
                )

            # 执行变更（事务）
            if auto_commit or operation.category == "mutation":
                return self._execute_transaction(operation, params, previews)

            return ExecutionResult(
                success=True,
                operation_id=operation.id,
                operation_name=operation.name,
                previews=previews,
                executed=False,
                summary="等待用户确认"
            )

        except Exception as e:
            logger.error(f"变更操作失败: {e}")
            return ExecutionResult(
                success=False,
                operation_id=operation.id,
                operation_name=operation.name,
                previews=previews,
                error=f"变更操作失败: {str(e)}"
            )

    def _execute_transaction(
        self,
        operation,
        params: Dict[str, Any],
        previews: List[StepPreview]
    ) -> ExecutionResult:
        """
        在事务中执行变更

        Args:
            operation: 操作模板
            params: 参数字典
            previews: 预览列表

        Returns:
            ExecutionResult
        """
        try:
            # 依次执行每个步骤
            for i, step in enumerate(operation.steps):
                sql = self._render_sql(step.sql, params)

                # 使用数据库管理器的事务方法
                result = self.db_manager.execute_update(sql)

                # 更新预览
                previews[i].affected_rows = result

            return ExecutionResult(
                success=True,
                operation_id=operation.id,
                operation_name=operation.name,
                previews=previews,
                executed=True,
                summary=f"执行成功，共 {len(previews)} 个步骤"
            )

        except Exception as e:
            logger.error(f"事务执行失败: {e}")
            return ExecutionResult(
                success=False,
                operation_id=operation.id,
                operation_name=operation.name,
                previews=previews,
                error=f"事务执行失败: {str(e)}"
            )

    def _render_sql(self, sql_template: str, params: Dict[str, Any]) -> str:
        """
        渲染 SQL 模板

        Args:
            sql_template: SQL 模板（使用 :param 占位符）
            params: 参数字典

        Returns:
            渲染后的 SQL
        """
        sql = sql_template

        # 替换 :param 形式的参数
        for key, value in params.items():
            if value is None:
                sql = sql.replace(f":{key}", "NULL")
            elif isinstance(value, str):
                # 转义单引号
                escaped = value.replace("'", "''")
                sql = sql.replace(f":{key}", f"'{escaped}'")
            elif isinstance(value, int):
                sql = sql.replace(f":{key}", str(value))
            else:
                sql = sql.replace(f":{key}", str(value))

        return sql

    def _generate_preview_sql(self, sql: str, affects_rows: str) -> Optional[str]:
        """
        生成预览 SQL

        Args:
            sql: 原始 SQL
            affects_rows: 影响行类型

        Returns:
            预览 SQL
        """
        sql_upper = sql.upper().strip()

        # UPDATE: 生成 SELECT 查看受影响的行
        if sql_upper.startswith("UPDATE"):
            # 提取表名和 WHERE 条件
            match = re.search(r"UPDATE\s+(\S+)\s+SET\s+(.+?)\s+WHERE\s+(.+)", sql, re.IGNORECASE | re.DOTALL)
            if match:
                table = match.group(1)
                where_clause = match.group(3)
                return f"SELECT * FROM {table} WHERE {where_clause}"

        # DELETE: 生成 SELECT 查看要删除的行
        elif sql_upper.startswith("DELETE"):
            match = re.search(r"DELETE\s+FROM\s+(\S+)\s+WHERE\s+(.+)", sql, re.IGNORECASE)
            if match:
                table = match.group(1)
                where_clause = match.group(2)
                return f"SELECT * FROM {table} WHERE {where_clause}"

        # INSERT: 无法预览，返回空
        elif sql_upper.startswith("INSERT"):
            return None

        return None

    def format_preview_output(self, result: ExecutionResult) -> str:
        """
        格式化预览输出

        Args:
            result: 执行结果

        Returns:
            格式化的文本
        """
        if not result.success:
            return f"❌ 错误: {result.error}"

        lines = [
            f"🔍 操作: {result.operation_name}",
            f"📋 状态: {'已执行' if result.executed else '预览模式'}",
            ""
        ]

        if result.previews:
            lines.append("📊 步骤预览:")
            for i, preview in enumerate(result.previews, 1):
                lines.append(f"  Step {i}: {preview.step_name}")
                lines.append(f"    SQL: {preview.sql[:100]}..." if len(preview.sql) > 100 else f"    SQL: {preview.sql}")
                if preview.before:
                    lines.append(f"    影响行数: {len(preview.before)}")
                if preview.error:
                    lines.append(f"    ⚠️ 错误: {preview.error}")
                lines.append("")

        if result.summary:
            lines.append(f"📝 {result.summary}")

        return "\n".join(lines)


# 全局单例
_operation_executor: Optional[OperationExecutor] = None


def get_operation_executor(db_manager=None, knowledge_loader=None) -> OperationExecutor:
    """
    获取操作执行器单例

    Args:
        db_manager: 数据库管理器
        knowledge_loader: 知识库加载器

    Returns:
        OperationExecutor 实例
    """
    global _operation_executor

    if _operation_executor is None:
        if db_manager is None or knowledge_loader is None:
            raise ValueError("首次调用需要提供 db_manager 和 knowledge_loader")
        _operation_executor = OperationExecutor(db_manager, knowledge_loader)

    return _operation_executor
