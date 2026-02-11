import pytest
from unittest.mock import patch, MagicMock, call
import pandas as pd
from main import main

def test_main_flow_list_tables():
    """测试主流程：列出表然后退出"""
    with patch('builtins.input', side_effect=['list tables', 'exit']), \
         patch('main.DatabaseManager') as MockDB, \
         patch('main.ExcelExporter') as MockExporter, \
         patch('main.LLMClient') as MockLLM, \
         patch('main.SchemaLoader') as MockSchemaLoader:
        mock_db_instance = MockDB.return_value
        mock_db_instance.get_all_tables.return_value = ['table1', 'table2']
        mock_schema_loader = MockSchemaLoader.return_value
        mock_schema_loader.get_schema_context.return_value = "Mock Schema Context"
        main()
        mock_db_instance.get_all_tables.assert_called_once()

def test_main_flow_query_export():
    """测试主流程：执行查询并导出"""
    with patch('builtins.input', side_effect=['SELECT * FROM table1', 'exit']), \
         patch('main.DatabaseManager') as MockDB, \
         patch('main.ExcelExporter') as MockExporter, \
         patch('main.LLMClient') as MockLLM, \
         patch('main.SchemaLoader') as MockSchemaLoader:
        mock_db_instance = MockDB.return_value
        mock_exporter_instance = MockExporter.return_value
        mock_schema_loader = MockSchemaLoader.return_value
        mock_schema_loader.get_schema_context.return_value = "Mock Schema Context"
        df_mock = pd.DataFrame({'id': [1], 'val': ['test']})
        mock_db_instance.execute_query.return_value = df_mock
        main()
        mock_db_instance.execute_query.assert_called_with('SELECT * FROM table1')
        mock_exporter_instance.export.assert_called_once()

def test_cli_rejects_disallowed_sql():
    """测试主流程：拒绝执行危险SQL（DROP/ALTER/TRUNCATE）"""
    dangerous_sql = "DROP TABLE users"
    with patch('builtins.input', side_effect=[dangerous_sql, 'exit']), \
         patch('main.DatabaseManager') as MockDB, \
         patch('main.ExcelExporter') as MockExporter, \
         patch('main.LLMClient') as MockLLM, \
         patch('main.SchemaLoader') as MockSchemaLoader:
        mock_db_instance = MockDB.return_value
        mock_schema_loader = MockSchemaLoader.return_value
        mock_schema_loader.get_schema_context.return_value = "Mock Schema Context"
        main()
        mock_db_instance.execute_query.assert_not_called()

def test_cli_rejects_alter_sql():
    """测试主流程：拒绝执行ALTER TABLE"""
    dangerous_sql = "ALTER TABLE users ADD COLUMN age INT"
    with patch('builtins.input', side_effect=[dangerous_sql, 'exit']), \
         patch('main.DatabaseManager') as MockDB, \
         patch('main.ExcelExporter') as MockExporter, \
         patch('main.LLMClient') as MockLLM, \
         patch('main.SchemaLoader') as MockSchemaLoader:
        mock_db_instance = MockDB.return_value
        mock_schema_loader = MockSchemaLoader.return_value
        mock_schema_loader.get_schema_context.return_value = "Mock Schema Context"
        main()
        mock_db_instance.execute_query.assert_not_called()
