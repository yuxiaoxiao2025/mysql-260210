import pytest
from src.db_manager import DatabaseManager
import pandas as pd

@pytest.fixture
def db_manager():
    return DatabaseManager()

def test_connection(db_manager):
    """测试能否成功连接"""
    with db_manager.get_connection() as conn:
        assert conn is not None

def test_execute_query(db_manager):
    """测试执行简单查询"""
    # 假设 config 表存在 (从 mysql.md 可知)
    # 或者用 SELECT 1
    df = db_manager.execute_query("SELECT 1 as val")
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert df.iloc[0]['val'] == 1

def test_get_all_tables(db_manager):
    """测试获取表列表"""
    tables = db_manager.get_all_tables()
    assert isinstance(tables, list)
    # 只要列表不报错即可，数据库可能为空，但至少应该能跑通
    print(f"Found tables: {tables}")

def test_get_table_schema(db_manager):
    """测试获取表结构"""
    tables = db_manager.get_all_tables()
    if tables:
        table_name = tables[0]
        schema = db_manager.get_table_schema(table_name)
        assert isinstance(schema, list)
        if schema:
            col = schema[0]
            assert 'name' in col
            assert 'type' in col
