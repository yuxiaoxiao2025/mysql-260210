from sqlalchemy import create_engine, text, inspect
import pandas as pd
from src.config import get_db_url
from sqlalchemy.pool import QueuePool
from typing import Optional, Dict, List, Any, Tuple

_DEFAULT_DB = object()

class DatabaseManager:
    def __init__(self, specific_db: Optional[str] | object = _DEFAULT_DB):
        if specific_db is _DEFAULT_DB:
            self.specific_db = None
            self.db_url = self._build_db_url(None, use_default_db=True)
        else:
            self.specific_db = specific_db
            self.db_url = self._build_db_url(specific_db, use_default_db=False)

        self.engine = create_engine(
            self.db_url,
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_recycle=3600
        )

    def _build_db_url(
        self, db_name: Optional[str], use_default_db: bool = True
    ) -> str:
        return get_db_url(db_name=db_name, use_default_db=use_default_db)
        
    def get_connection(self):
        """获取原始数据库连接"""
        return self.engine.connect()
        
    def execute_query(self, sql: str, params: Optional[Dict[str, Any]] = None):
        """
        执行 SQL 查询并返回 DataFrame

        Args:
            sql: SQL 语句，支持命名参数 (:param_name)
            params: 参数字典，可选

        Returns:
            DataFrame 查询结果
        """
        try:
            with self.get_connection() as conn:
                # 使用 pandas 的 read_sql 直接读取，支持参数化查询
                df = pd.read_sql(text(sql), conn, params=params or {})
                return df
        except Exception as e:
            print(f"Error executing query: {e}")
            raise

    def execute_update(self, sql: str, params: Optional[Dict[str, Any]] = None) -> int:
        """
        执行变更 SQL (INSERT/UPDATE/DELETE) 并返回影响行数

        最佳实践:
        - 使用 engine.begin() 自动管理事务
        - 使用 text() 包装 + 参数化绑定防止 SQL 注入
        - 异常时自动回滚

        Args:
            sql: SQL 语句，支持命名参数 (:param_name)
            params: 参数字典，可选

        Returns:
            受影响的行数 (int)

        Example:
            >>> db.execute_update("INSERT INTO users (name) VALUES (:name)", {"name": "Alice"})
            1
            >>> db.execute_update("UPDATE users SET age = :age WHERE id = :id", {"age": 25, "id": 1})
            1
        """
        with self.engine.begin() as conn:
            result = conn.execute(text(sql), params or {})
            return result.rowcount

    def get_all_tables(self):
        """获取所有表名"""
        inspector = inspect(self.engine)
        return inspector.get_table_names()

    def get_all_databases(self, exclude_system: bool = True) -> List[str]:
        """获取所有数据库名称"""
        with self.get_connection() as conn:
            result = conn.execute(text("SHOW DATABASES"))
            databases = [row[0] for row in result.fetchall()]

        if not exclude_system:
            return databases

        system_dbs = {"information_schema", "mysql", "performance_schema", "sys"}
        return [db_name for db_name in databases if db_name not in system_dbs]

    def get_tables_in_database(self, db_name: str) -> List[str]:
        """获取指定数据库中的表名"""
        sql = text(
            """
            SELECT TABLE_NAME
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = :db_name
            """
        )
        with self.get_connection() as conn:
            result = conn.execute(sql, {"db_name": db_name})
            return [row[0] for row in result.fetchall()]

    def check_tables_structure_match(self, db1: str, db2: str) -> bool:
        """比较两个数据库的表结构是否一致"""
        tables_db1 = set(self.get_tables_in_database(db1))
        tables_db2 = set(self.get_tables_in_database(db2))

        if tables_db1 != tables_db2:
            return False

        for table_name in tables_db1:
            columns_db1 = self._get_table_columns(db1, table_name)
            columns_db2 = self._get_table_columns(db2, table_name)
            if columns_db1 != columns_db2:
                return False

        return True

    def _get_table_columns(self, db_name: str, table_name: str) -> List[Tuple[str, str]]:
        sql = text(
            """
            SELECT COLUMN_NAME, COLUMN_TYPE
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = :db_name AND TABLE_NAME = :table_name
            ORDER BY ORDINAL_POSITION
            """
        )
        with self.get_connection() as conn:
            result = conn.execute(
                sql, {"db_name": db_name, "table_name": table_name}
            )
            return [(row[0], row[1]) for row in result.fetchall()]

    def get_table_schema(self, table_name, schema=None):
        """获取表结构信息"""
        inspector = inspect(self.engine)
        columns = inspector.get_columns(table_name, schema=schema)
        # 简化输出，只保留 name, type, comment
        schema_info = []
        for col in columns:
            schema_info.append({
                "name": col['name'],
                "type": str(col['type']),
                "comment": col.get('comment', '')
            })
        return schema_info

    def execute_in_transaction(
        self,
        mutation_sql: str,
        preview_sql: str,
        key_columns: List[str],
        commit: bool = False,
        mutation_params: Optional[Dict[str, Any]] = None,
        preview_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        在事务内执行变更操作，返回 Before/After 数据和差异摘要。

        工作流程：
        1. 开始事务
        2. 执行 preview_sql 获取变更前的数据
        3. 执行 mutation_sql 执行变更
        4. 再次执行 preview_sql 获取变更后的数据
        5. 根据 commit 参数决定提交或回滚
        6. 计算 Before/After 的差异摘要

        Args:
            mutation_sql: 要执行的变更 SQL (INSERT/UPDATE/DELETE)
            preview_sql: 用于查看变更前后状态的查询 SQL
            key_columns: 用于对齐行的主键列列表
            commit: 是否提交事务，默认 False（回滚）
            mutation_params: 变更 SQL 的参数字典，可选
            preview_params: 预览 SQL 的参数字典，可选

        Returns:
            包含以下键的字典:
            - before: 变更前的 DataFrame
            - after: 变更后的 DataFrame
            - diff_summary: 差异摘要 {inserted, updated, deleted}
            - committed: 事务是否已提交
        """
        from src.txn_preview import summarize_diff

        with self.engine.begin() as conn:
            # Before: 执行预览查询获取变更前的数据
            before_df = pd.read_sql(text(preview_sql), conn, params=preview_params or {})

            # 执行变更 SQL
            conn.execute(text(mutation_sql), mutation_params or {})

            # After: 再次执行预览查询获取变更后的数据
            after_df = pd.read_sql(text(preview_sql), conn, params=preview_params or {})

            # 计算差异摘要
            diff_summary = summarize_diff(before_df, after_df, key_columns)

            # 根据 commit 参数决定提交或回滚
            # SQLAlchemy 的 context manager 会自动处理
            # 如果 commit=False，则在退出 context 时回滚
            if commit:
                # 事务会在退出 context 时自动提交
                committed = True
            else:
                # 回滚事务
                conn.rollback()
                committed = False

            return {
                "before": before_df,
                "after": after_df,
                "diff_summary": diff_summary,
                "committed": committed
            }

    def execute_multi_step_transaction(
        self,
        sql_steps: List[Tuple[str, Optional[Dict[str, Any]]]],
        commit: bool = True
    ) -> Dict[str, Any]:
        """
        执行多步骤事务 - 所有步骤在同一事务中

        使用 engine.begin() 模式，确保所有步骤在同一事务内执行。
        如果任何步骤失败，整个事务自动回滚。

        常见用例：
        - 批量数据插入
        - 批量更新多个表
        - "批量下发到所有场库"等批量操作场景

        Args:
            sql_steps: SQL 步骤列表，每个元素是 (sql, params) 元组
                      - sql: SQL 语句（支持命名参数 :param_name）
                      - params: 参数字典，可选，默认为 None
            commit: 是否提交事务
                   - True: 提交事务（默认）
                   - False: 回滚事务（用于测试或预览）

        Returns:
            包含以下键的字典:
            - success: 是否成功执行 (bool)
            - steps_executed: 成功执行的步骤数 (int)
            - affected_rows: 每个步骤的影响行数列表 (List[int])
            - error: 错误信息，仅在失败时存在 (str)
            - failed_at_step: 失败的步骤索引，仅在失败时存在 (int)
            - committed: 事务是否已提交 (bool)

        Example:
            >>> db.execute_multi_step_transaction([
            ...     ("INSERT INTO users (name) VALUES (:name)", {"name": "Alice"}),
            ...     ("INSERT INTO users (name) VALUES (:name)", {"name": "Bob"}),
            ...     ("UPDATE users SET age = 20 WHERE name = 'Alice'", None)
            ... ], commit=True)
            {
                'success': True,
                'steps_executed': 3,
                'affected_rows': [1, 1, 1],
                'committed': True
            }

            >>> db.execute_multi_step_transaction([
            ...     ("INSERT INTO valid_table (name) VALUES ('test')", None),
            ...     ("INVALID SQL", None)  # 这会触发回滚
            ... ], commit=True)
            {
                'success': False,
                'error': '...',
                'failed_at_step': 1,
                'steps_executed': 1,
                'affected_rows': [1],
                'committed': False
            }
        """
        affected_rows = []
        failed_step = -1
        error_msg = None

        with self.engine.begin() as conn:
            try:
                # 执行所有 SQL 步骤
                for i, (sql, params) in enumerate(sql_steps):
                    result = conn.execute(text(sql), params or {})
                    affected_rows.append(result.rowcount)

                # 所有步骤执行成功
                steps_executed = len(sql_steps)

                # 根据 commit 参数决定提交或回滚
                # SQLAlchemy 的 context manager 会自动处理
                # 如果 commit=False，则在退出 context 时回滚
                if commit:
                    # 事务会在退出 context 时自动提交
                    committed = True
                else:
                    # 回滚事务
                    conn.rollback()
                    committed = False

                return {
                    "success": True,
                    "steps_executed": steps_executed,
                    "affected_rows": affected_rows,
                    "committed": committed
                }

            except Exception as e:
                # 记录失败信息
                error_msg = str(e)
                failed_step = len(affected_rows)  # 失败的步骤索引

                # 回滚事务（异常时会自动回滚，但明确调用更清晰）
                conn.rollback()

                return {
                    "success": False,
                    "error": error_msg,
                    "failed_at_step": failed_step,
                    "steps_executed": len(affected_rows),
                    "affected_rows": affected_rows,
                    "committed": False
                }
