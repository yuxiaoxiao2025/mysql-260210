from sqlalchemy import create_engine, text, inspect
import pandas as pd
from src.config import get_db_url
from sqlalchemy.pool import QueuePool

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

    def get_table_schema(self, table_name):
        """获取表结构信息"""
        inspector = inspect(self.engine)
        columns = inspector.get_columns(table_name)
        # 简化输出，只保留 name, type, comment
        schema_info = []
        for col in columns:
            schema_info.append({
                "name": col['name'],
                "type": str(col['type']),
                "comment": col.get('comment', '')
            })
        return schema_info
