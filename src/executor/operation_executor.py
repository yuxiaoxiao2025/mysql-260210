"""
操作执行器

安全执行业务操作，支持参数校验、预览生成和事务执行。
"""

import logging
import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
import pandas as pd

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

        logger.info(
            "Executing operation: %s (preview_only=%s, auto_commit=%s)",
            operation_id,
            preview_only,
            auto_commit,
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
                # 支持列表形式的值（批量下发到多个园区）
                if isinstance(value, list):
                    # 验证列表中的每个值
                    for item in value:
                        validated = self.knowledge_loader.lookup_enum_value(param.enum_from, str(item))
                        if not validated:
                            available = self.knowledge_loader.get_enum_values_flat(param.enum_from)
                            return {
                                "valid": False,
                                "error": f"参数 {param.name} 的值 '{item}' 无效，可选值: {', '.join(available[:5])}..."
                            }
                else:
                    # 单个值验证
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

    def _expand_park_name(self, park_name: Any) -> List[str]:
        """
        展开场库名称

        如果 park_name="全部"，则展开为所有激活场库的列表
        如果 park_name 是单个场库名称，则返回单元素列表
        如果 park_name 已经是列表，则直接返回

        Args:
            park_name: 场库名称（可以是"全部"、单个名称或列表）

        Returns:
            场库名称列表
        """
        # 如果已经是列表，直接返回
        if isinstance(park_name, list):
            return park_name

        # 如果是"全部"，展开为所有场库
        if park_name == "全部":
            all_parks = self.knowledge_loader.get_enum_values_flat("park_names")
            # 过滤掉"全部"本身，只返回实际场库
            return [p for p in all_parks if p != "全部"]

        # 单个场库，返回单元素列表
        return [park_name]

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
            # 使用参数化查询防止 SQL 注入
            sql_template, bound_params = self._render_sql(operation.sql, params)

            # 执行查询（使用参数化）
            with self.db_manager.get_connection() as conn:
                df = self._read_sql(sql_template, conn, bound_params)

            # 转换为字典列表
            results = df.to_dict('records')

            # 用于显示的 SQL（不包含实际参数值，避免泄露敏感信息）
            preview = StepPreview(
                step_name="查询结果",
                sql=sql_template,
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
                sql_template, bound_params = self._render_sql(step.sql, params)

                # 生成预览 SQL（SELECT 形式）
                preview_sql = self._generate_preview_sql(sql_template, step.affects_rows)

                # 获取执行前数据（使用参数化查询）
                before_data = []
                if preview_sql:
                    try:
                        with self.db_manager.get_connection() as conn:
                            before_df = self._read_sql(preview_sql, conn, bound_params)
                        before_data = before_df.to_dict('records')
                    except Exception as e:
                        logger.warning(f"获取预览数据失败: {e}")

                preview = StepPreview(
                    step_name=step.name,
                    sql=sql_template,
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
            # 依次执行每个步骤（使用参数化查询）
            for i, step in enumerate(operation.steps):
                sql_template, bound_params = self._render_sql(step.sql, params)

                # 使用数据库管理器的事务方法（支持参数化查询）
                result = self.db_manager.execute_update(sql_template, bound_params)

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

    def _render_sql(self, sql_template: str, params: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """
        渲染 SQL 模板，返回参数化查询

        使用参数化查询防止 SQL 注入，SQLAlchemy 会处理参数绑定。

        Args:
            sql_template: SQL 模板（使用 :param 占位符）
            params: 参数字典

        Returns:
            元组 (sql_template, bound_params) - SQL 模板和绑定参数
        """
        # 直接返回模板和参数，让 SQLAlchemy 处理绑定
        # 不进行任何字符串拼接，防止 SQL 注入
        bound_params = {}
        for key, value in params.items():
            bound_params[key] = value

        return sql_template, bound_params

    def _is_sqlalchemy_connection(self, conn: Any) -> bool:
        try:
            from sqlalchemy.engine import Connection
        except Exception:
            return False
        return isinstance(conn, Connection)

    def _read_sql(self, sql: str, conn: Any, params: Dict[str, Any]) -> pd.DataFrame:
        if self._is_sqlalchemy_connection(conn):
            from sqlalchemy import text
            return pd.read_sql(text(sql), conn, params=params)
        return pd.read_sql(sql, conn, params=params)

    def _generate_preview_sql(self, sql: str, affects_rows: str) -> Optional[str]:
        """
        生成预览 SQL

        使用 sqlglot 解析器正确处理子查询等复杂 SQL 结构。
        如果解析失败，则回退到基于正则表达式的方案。

        Args:
            sql: 原始 SQL
            affects_rows: 影响行类型

        Returns:
            预览 SQL
        """
        if not sql or not isinstance(sql, str):
            return None

        sql = sql.strip()
        if not sql:
            return None

        # 首先尝试使用 sqlglot 解析器
        preview = self._parse_with_sqlglot(sql)
        if preview:
            return preview

        # 回退到正则表达式方案
        logger.warning(f"SQL 解析失败，使用回退方案: {sql[:50]}...")
        return self._fallback_preview_sql(sql)

    def _parse_with_sqlglot(self, sql: str) -> Optional[str]:
        """
        使用 sqlglot 解析器生成预览 SQL

        Args:
            sql: 原始 SQL

        Returns:
            预览 SQL，如果解析失败返回 None
        """
        try:
            import sqlglot

            # 使用 MySQL 方言解析
            parsed = sqlglot.parse_one(sql, dialect='mysql')

            # 检查语句类型
            sql_type = parsed.args.get('type')
            if sql_type is None:
                # sqlglot 可能使用不同的键名，尝试获取语句类型
                if parsed.key.upper() == 'UPDATE':
                    sql_type = 'UPDATE'
                elif parsed.key.upper() == 'DELETE':
                    sql_type = 'DELETE'
                else:
                    return None

            # 处理 UPDATE 语句
            if str(sql_type).upper() == 'UPDATE':
                # 获取表名
                table = parsed.args.get('this')
                if not table:
                    return None

                # 获取 WHERE 子句
                where = parsed.args.get('where')
                if where:
                    # sqlglot 的 WHERE 表达式在生成 SQL 时会包含 WHERE 关键字
                    # 我们需要获取 WHERE 表达式内部的条件（不包含 WHERE 关键字）
                    where_sql = where.this.sql(dialect='mysql')
                    return f"SELECT * FROM {table.sql(dialect='mysql')} WHERE {where_sql}"

            # 处理 DELETE 语句
            elif str(sql_type).upper() == 'DELETE':
                # DELETE 语句的表名在 'this' 参数中
                table = parsed.args.get('this')
                where = parsed.args.get('where')

                if table and where:
                    table_sql = table.sql(dialect='mysql')
                    # sqlglot 的 WHERE 表达式在生成 SQL 时会包含 WHERE 关键字
                    # 我们需要获取 WHERE 表达式内部的条件（不包含 WHERE 关键字）
                    where_sql = where.this.sql(dialect='mysql')
                    return f"SELECT * FROM {table_sql} WHERE {where_sql}"

            return None

        except ImportError:
            logger.warning("sqlglot 未安装，使用回退方案")
            return None
        except Exception as e:
            logger.warning(f"SQL 解析失败: {e}")
            return None

    def _fallback_preview_sql(self, sql: str) -> Optional[str]:
        """
        回退方案：使用改进的正则表达式生成预览 SQL

        此方案更健壮地处理括号匹配，但不如 sqlglot 可靠。

        Args:
            sql: 原始 SQL

        Returns:
            预览 SQL
        """
        sql_upper = sql.upper()

        # UPDATE: 生成 SELECT 查看受影响的行
        if sql_upper.startswith("UPDATE"):
            table = self._extract_update_table(sql)
            where_clause = self._extract_where_clause(sql)
            if table and where_clause:
                return f"SELECT * FROM {table} WHERE {where_clause}"

        # DELETE: 生成 SELECT 查看要删除的行
        elif sql_upper.startswith("DELETE"):
            match = re.search(r"DELETE\s+FROM\s+(\S+)\s+WHERE\s+(.+)", sql, re.IGNORECASE | re.DOTALL)
            if match:
                table = match.group(1)
                where_clause = match.group(2)
                return f"SELECT * FROM {table} WHERE {where_clause}"

        # INSERT: 无法预览，返回空
        elif sql_upper.startswith("INSERT"):
            return None

        return None

    def _extract_update_table(self, sql: str) -> Optional[str]:
        """
        从 UPDATE 语句中提取表名

        Args:
            sql: UPDATE SQL 语句

        Returns:
            表名
        """
        match = re.search(r"UPDATE\s+(\S+)", sql, re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    def _extract_where_clause(self, sql: str) -> Optional[str]:
        """
        从 UPDATE 语句中提取 WHERE 子句（正确处理括号匹配）

        关键是要找到 SET 子句结束后的 WHERE，而不是子查询中的 WHERE

        Args:
            sql: UPDATE SQL 语句

        Returns:
            WHERE 子句（不包含 WHERE 关键字）
        """
        sql_upper = sql.upper()

        # 找到 SET 关键字的位置
        set_match = re.search(r"\s+SET\s+", sql_upper)
        if not set_match:
            return None

        set_end = set_match.end()

        # 从 SET 之后开始，跳过所有括号和字符串，找到第一个 WHERE
        where_pos = self._find_where_after_set(sql, set_end)

        if where_pos == -1:
            return None

        # 提取 WHERE 之后的内容
        where_content = sql[where_pos + 6:].strip()  # 跳过 "WHERE "
        return where_content if where_content else None

    def _find_where_after_set(self, sql: str, start_pos: int) -> int:
        """
        从指定位置开始，跳过 SET 子句中的括号和字符串，找到 WHERE 关键字

        Args:
            sql: SQL 语句
            start_pos: 开始位置（SET 之后）

        Returns:
            WHERE 关键字的位置，如果找不到返回 -1
        """
        i = start_pos
        paren_depth = 0
        in_string = False
        string_char = None

        while i < len(sql) - 4:  # 至少需要 4 个字符来匹配 "WHERE"
            char = sql[i]

            # 处理字符串字面量
            if char in ("'", '"') and not in_string:
                in_string = True
                string_char = char
                i += 1
                continue
            elif char == string_char and in_string:
                # 检查是否是转义的引号（两个连续引号）
                if i + 1 < len(sql) and sql[i + 1] == string_char:
                    i += 2  # 跳过转义的引号
                    continue
                else:
                    in_string = False
                    string_char = None
                    i += 1
                    continue

            # 如果在字符串中，跳过所有字符
            if in_string:
                i += 1
                continue

            # 处理括号
            if char == '(':
                paren_depth += 1
                i += 1
                continue
            elif char == ')':
                paren_depth -= 1
                i += 1
                continue

            # 只有在括号平衡时（paren_depth == 0）才检查 WHERE
            if paren_depth == 0:
                # 检查是否是 WHERE 关键字
                remaining = sql[i:].upper()
                if remaining.startswith("WHERE"):
                    # 确保 WHERE 后面是空格或结束，避免匹配 "WHEREEVER" 等
                    if len(sql) == i + 5 or not sql[i + 5].isalnum():
                        return i

            i += 1

        return -1

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
