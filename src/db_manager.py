from sqlalchemy import create_engine, text, inspect
import pandas as pd
from src.config import get_db_url
from sqlalchemy.pool import QueuePool
from typing import Optional, Dict, List

class DatabaseManager:
    def __init__(self):
        self.db_url = get_db_url()
        self.engine = create_engine(
            self.db_url,
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_recycle=3600
        )
        
    def get_connection(self):
        """获取原始数据库连接"""
        return self.engine.connect()
        
    def execute_query(self, sql):
        """执行 SQL 查询并返回 DataFrame"""
        try:
            with self.get_connection() as conn:
                # 使用 pandas 的 read_sql 直接读取
                df = pd.read_sql(text(sql), conn)
                return df
        except Exception as e:
            print(f"Error executing query: {e}")
            raise

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
        commit: bool = False
    ) -> Dict[str, any]:
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
            before_df = pd.read_sql(text(preview_sql), conn)

            # 执行变更 SQL
            conn.execute(text(mutation_sql))

            # After: 再次执行预览查询获取变更后的数据
            after_df = pd.read_sql(text(preview_sql), conn)

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
