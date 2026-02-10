import pytest
import pandas as pd
import os
from src.exporter import ExcelExporter

@pytest.fixture
def exporter():
    return ExcelExporter(output_dir="output")

def test_export_basic(exporter):
    """测试基本导出功能"""
    data = {
        'ID': [1, 2, 3],
        'Name': ['Alice', 'Bob', 'Charlie'],
        'Age': [25, 30, 35],
        'Description': ['Long text description here to test column width adjustment', 'Short', 'Medium text']
    }
    df = pd.DataFrame(data)
    
    filename = "test_export_basic.xlsx"
    filepath = exporter.export(df, filename=filename)
    
    assert os.path.exists(filepath)
    print(f"Exported to: {filepath}")
    
    # 验证能否读取
    df_read = pd.read_excel(filepath)
    assert len(df_read) == 3
    assert 'Name' in df_read.columns

def test_export_empty(exporter):
    """测试导出空 DataFrame"""
    df = pd.DataFrame(columns=['A', 'B'])
    filepath = exporter.export(df, "test_empty.xlsx")
    assert os.path.exists(filepath)
