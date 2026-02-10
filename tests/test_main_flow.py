import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from main import main

def test_main_flow_list_tables():
    """测试主流程：列出表然后退出"""
    with patch('builtins.input', side_effect=['list tables', 'exit']), \
         patch('main.DatabaseManager') as MockDB, \
         patch('main.ExcelExporter') as MockExporter:
        
        # Setup mock
        mock_db_instance = MockDB.return_value
        mock_db_instance.get_all_tables.return_value = ['table1', 'table2']
        
        # Run main
        main()
        
        # Verify
        mock_db_instance.get_all_tables.assert_called_once()

def test_main_flow_query_export():
    """测试主流程：执行查询并导出"""
    with patch('builtins.input', side_effect=['SELECT * FROM table1', 'exit']), \
         patch('main.DatabaseManager') as MockDB, \
         patch('main.ExcelExporter') as MockExporter:
        
        # Setup mock
        mock_db_instance = MockDB.return_value
        mock_exporter_instance = MockExporter.return_value
        
        # Mock query result
        df_mock = pd.DataFrame({'id': [1], 'val': ['test']})
        mock_db_instance.execute_query.return_value = df_mock
        
        # Run main
        main()
        
        # Verify
        mock_db_instance.execute_query.assert_called_with('SELECT * FROM table1')
        mock_exporter_instance.export.assert_called_once()
