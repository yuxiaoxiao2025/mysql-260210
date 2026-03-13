from sqlalchemy import create_engine, text, inspect
import pandas as pd
import os
import re
from dotenv import load_dotenv
from sqlalchemy.pool import QueuePool
from typing import Optional, Dict, List, Any, Tuple

# Load environment variables
load_dotenv()

_DEFAULT_DB = object()

class DatabaseManager:
    """数据库管理器，支持单库和跨库查询"""

    # 系统数据库（自动排除）
    SYSTEM_DATABASES = frozenset([
        "information_schema",
        "mysql",
        "performance_schema",
        "sys"
    ])
    _VALID_IDENTIFIER = re.compile(r"^[A-Za-z0-9_]+$")

    def __init__(self, specific_db: Optional[str] | object = _DEFAULT_DB):
        """
        初始化数据库管理器

        Args:
            specific_db: 指定连接的数据库
                - _DEFAULT_DB (默认): 使用环境变量 DB_NAME 指定的默认数据库
                - None: 不指定数据库（用于跨库查询）
                - str: 指定数据库名称
        """
        if specific_db is _DEFAULT_DB:
            # 使用默认数据库
            self.specific_db = None
            default_db = os.getenv('DB_NAME')
            self.db_url = self._build_db_url(default_db)
        else:
            # 指定数据库或不指定
            self.specific_db = specific_db
            self.db_url = self._build_db_url(specific_db)

        self.engine = create_engine(
            self.db_url,
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_recycle=3600
        )

    def _build_db_url(self, db_name: Optional[str] = None) -> str:
        """
        构建数据库连接 URL

        Args:
            db_name: 数据库名，None 表示不指定数据库

        Returns:
            数据库连接 URL
        """
        db_user = os.getenv('DB_USER', 'root')
        db_password = os.getenv('DB_PASSWORD', '')
        db_host = os.getenv('DB_HOST', 'localhost')
        db_port = os.getenv('DB_PORT', '3306')

        base_url = f"mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/"

        if db_name:
            return base_url + db_name
        return base_url  # 不指定数据库，支持跨库查询
        
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

    # ==================== 跨库查询方法 ====================

    def get_all_databases(self, exclude_system: bool = True) -> List[str]:
        """
        获取所有数据库列表

        Args:
            exclude_system: 是否排除系统数据库
                - True: 排除 information_schema, mysql, performance_schema, sys
                - False: 包含所有数据库

        Returns:
            数据库名称列表

        Example:
            >>> db = DatabaseManager(specific_db=None)
            >>> databases = db.get_all_databases(exclude_system=True)
            ['parkcloud', 'db_parking_center', 'cloudinterface', 'p210113175340', ...]
        """
        with self.get_connection() as conn:
            result = conn.execute(text("SHOW DATABASES"))
            databases = [row[0] for row in result.fetchall()]

        if exclude_system:
            databases = [db for db in databases if db not in self.SYSTEM_DATABASES]

        return sorted(databases)

    def get_tables_in_database(self, db_name: str) -> List[str]:
        """
        获取指定数据库的所有表名

        Args:
            db_name: 数据库名

        Returns:
            表名列表

        Example:
            >>> db = DatabaseManager(specific_db=None)
            >>> tables = db.get_tables_in_database("parkcloud")
            ['cloud_fixed_plate', 'cloud_operator', 'cloud_park_info', ...]
        """
        sql = """
            SELECT TABLE_NAME
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = :db_name
            AND TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_NAME
        """
        with self.get_connection() as conn:
            result = conn.execute(text(sql), {"db_name": db_name})
            return [row[0] for row in result.fetchall()]

    def get_table_schema_cross_db(self, db_name: str, table_name: str) -> List[Dict[str, Any]]:
        """
        跨库获取表结构信息

        Args:
            db_name: 数据库名
            table_name: 表名

        Returns:
            列信息列表，每个元素包含 name, type, comment

        Example:
            >>> db = DatabaseManager(specific_db=None)
            >>> columns = db.get_table_schema_cross_db("parkcloud", "cloud_fixed_plate")
            [{'name': 'id', 'type': 'bigint', 'comment': '主键ID'}, ...]
        """
        sql = """
            SELECT
                COLUMN_NAME,
                COLUMN_TYPE,
                COLUMN_COMMENT
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = :db_name
                AND TABLE_NAME = :table_name
            ORDER BY ORDINAL_POSITION
        """
        with self.get_connection() as conn:
            result = conn.execute(text(sql), {"db_name": db_name, "table_name": table_name})
            columns = []
            for row in result.fetchall():
                columns.append({
                    "name": row[0],
                    "type": row[1],
                    "comment": row[2] or ""
                })
            return columns

    def is_table_empty(self, db_name: str, table_name: str) -> bool:
        if not self._VALID_IDENTIFIER.match(db_name) or not self._VALID_IDENTIFIER.match(table_name):
            raise ValueError("Invalid database or table name")

        table_rows_sql = """
            SELECT TABLE_ROWS
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = :db_name
                AND TABLE_NAME = :table_name
                AND TABLE_TYPE = 'BASE TABLE'
        """
        fallback_sql = f"SELECT 1 FROM `{db_name}`.`{table_name}` LIMIT 1"

        try:
            with self.get_connection() as conn:
                table_rows_result = conn.execute(
                    text(table_rows_sql),
                    {"db_name": db_name, "table_name": table_name}
                )
                table_rows_row = table_rows_result.fetchone()

                if table_rows_row and table_rows_row[0] is not None and table_rows_row[0] > 0:
                    return False

                fallback_result = conn.execute(text(fallback_sql))
                return fallback_result.fetchone() is None
        except Exception:
            return False

    def check_tables_structure_match(self, db1: str, db2: str) -> bool:
        """
        检查两个数据库的表结构是否相同

        用于验证园区库是否可以复用模板。

        Args:
            db1: 第一个数据库名
            db2: 第二个数据库名

        Returns:
            True 如果表结构完全相同，False 否则

        Example:
            >>> db = DatabaseManager(specific_db=None)
            >>> # 检查两个园区库结构是否相同
            >>> db.check_tables_structure_match("p210113175340", "p210121185450")
            True
        """
        # 1. 获取两个库的表列表
        tables1 = set(self.get_tables_in_database(db1))
        tables2 = set(self.get_tables_in_database(db2))

        # 2. 检查表数量和名称
        if tables1 != tables2:
            return False

        # 3. 检查每个表的列结构
        for table_name in tables1:
            schema1 = self.get_table_schema_cross_db(db1, table_name)
            schema2 = self.get_table_schema_cross_db(db2, table_name)

            # 比较列数量
            if len(schema1) != len(schema2):
                return False

            # 比较每列的名称和类型
            for col1, col2 in zip(schema1, schema2):
                if col1["name"] != col2["name"]:
                    return False
                if col1["type"].lower() != col2["type"].lower():
                    return False

        return True

    def get_database_table_counts(self) -> Dict[str, int]:
        """
        获取所有数据库的表数量统计

        Returns:
            字典 {数据库名: 表数量}

        Example:
            >>> db = DatabaseManager(specific_db=None)
            >>> counts = db.get_database_table_counts()
            {'parkcloud': 145, 'db_parking_center': 56, 'cloudinterface': 9, ...}
        """
        databases = self.get_all_databases(exclude_system=True)
        counts = {}
        for db_name in databases:
            tables = self.get_tables_in_database(db_name)
            counts[db_name] = len(tables)
        return counts

    def sample_data(self, table_name: str, limit: int = 5, schema: str = None) -> pd.DataFrame:
        """Get sample data from a table.

        Args:
            table_name: Name of the table
            limit: Number of rows to return (default 5)
            schema: Database schema (optional)

        Returns:
            DataFrame with sample data
        """
        table_full = f"{schema}.{table_name}" if schema else table_name
        query = f"SELECT * FROM {table_full} LIMIT {limit}"
        try:
            return self.execute_query(query)
        except Exception as e:
            from loguru import logger
            logger.warning(f"Failed to get sample data for {table_full}: {e}")
            return pd.DataFrame()
