import unittest
import os
from unittest.mock import MagicMock, patch
from src.schema_loader import SchemaLoader

class TestSchemaLoader(unittest.TestCase):
    def setUp(self):
        self.mock_db = MagicMock()
        self.mock_db.get_all_tables.return_value = ['table1']
        self.mock_db.get_table_schema.return_value = [{'name': 'col1', 'type': 'int', 'comment': 'id'}]

    @patch("builtins.open", new_callable=unittest.mock.mock_open, read_data="数据库名称：test_db\ntable1          测试表")
    @patch("os.path.exists", return_value=True)
    def test_load_descriptions(self, mock_exists, mock_open):
        loader = SchemaLoader(db_manager=self.mock_db)
        self.assertEqual(loader.table_descriptions['table1'], '测试表')
        self.assertEqual(loader.db_mapping['table1'], 'test_db')

    @patch("builtins.open", new_callable=unittest.mock.mock_open, read_data="table1          测试表")
    @patch("os.path.exists", return_value=True)
    def test_get_schema_context(self, mock_exists, mock_open):
        loader = SchemaLoader(db_manager=self.mock_db)
        context = loader.get_schema_context()
        self.assertIn("Table: table1", context)
        self.assertIn("Description: 测试表", context)
        self.assertIn("col1 (id)", context)

if __name__ == '__main__':
    unittest.main()


# ==================== 补充测试用例 ====================


class TestSchemaLoaderMoreScenarios(unittest.TestCase):
    """更多 SchemaLoader 测试场景"""

    def setUp(self):
        """设置测试环境"""
        self.mock_db = MagicMock()

    @patch("builtins.open", new_callable=unittest.mock.mock_open, read_data="数据库名称：test_db\ntable1          测试表")
    @patch("os.path.exists", return_value=True)
    def test_load_with_multiple_tables(self, mock_exists, mock_open):
        """测试加载多个表"""
        self.mock_db.get_all_tables.return_value = ['table1', 'table2', 'table3']
        self.mock_db.get_table_schema.side_effect = [
            [{'name': 'col1', 'type': 'int', 'comment': 'id'}],
            [{'name': 'col2', 'type': 'varchar', 'comment': 'name'}],
            [{'name': 'col3', 'type': 'date', 'comment': 'date'}]
        ]

        loader = SchemaLoader(db_manager=self.mock_db)
        self.assertEqual(loader.table_descriptions['table1'], '测试表')

    @patch("os.path.exists", return_value=False)
    def test_load_without_descriptions_file(self, mock_exists):
        """测试没有描述文件的情况"""
        self.mock_db.get_all_tables.return_value = ['table1']
        self.mock_db.get_table_schema.return_value = [{'name': 'col1', 'type': 'int', 'comment': 'id'}]

        loader = SchemaLoader(db_manager=self.mock_db)
        # 应该仍然能加载，只是没有描述
        self.assertEqual(len(loader.table_descriptions), 0)

    @patch("builtins.open", new_callable=unittest.mock.mock_open, read_data="数据库名称：test_db\ntable1          测试表\ntable2          另一个表")
    @patch("os.path.exists", return_value=True)
    def test_get_schema_context_with_descriptions(self, mock_exists, mock_open):
        """测试带表描述的上下文生成"""
        self.mock_db.get_all_tables.return_value = ['table1', 'table2']
        self.mock_db.get_table_schema.side_effect = [
            [{'name': 'col1', 'type': 'int', 'comment': 'id'}],
            [{'name': 'col2', 'type': 'varchar', 'comment': 'name'}]
        ]

        loader = SchemaLoader(db_manager=self.mock_db)
        context = loader.get_schema_context()

        self.assertIn("Table: table1", context)
        self.assertIn("Description: 测试表", context)
        self.assertIn("Table: table2", context)
        self.assertIn("Description: 另一个表", context)

    @patch("os.path.exists", return_value=False)
    def test_get_schema_context_without_descriptions(self, mock_exists):
        """测试没有描述的上下文生成"""
        self.mock_db.get_all_tables.return_value = ['table1']
        self.mock_db.get_table_schema.return_value = [{'name': 'col1', 'type': 'int', 'comment': 'id'}]

        loader = SchemaLoader(db_manager=self.mock_db)
        context = loader.get_schema_context()

        self.assertIn("Table: table1", context)
        # 没有描述
        self.assertNotIn("Description:", context)

    @patch("os.path.exists", return_value=False)
    def test_get_schema_context_empty_database(self, mock_exists):
        """测试空数据库的上下文生成"""
        self.mock_db.get_all_tables.return_value = []
        self.mock_db.get_table_schema.return_value = []

        loader = SchemaLoader(db_manager=self.mock_db)
        context = loader.get_schema_context()

        self.assertIn("No tables found", context)

    @patch("builtins.open", new_callable=unittest.mock.mock_open, read_data="数据库名称：test_db\ntable1          测试表")
    @patch("os.path.exists", return_value=True)
    def test_db_mapping(self, mock_exists, mock_open):
        """测试数据库映射"""
        self.mock_db.get_all_tables.return_value = ['table1']
        self.mock_db.get_table_schema.return_value = [{'name': 'col1', 'type': 'int', 'comment': 'id'}]

        loader = SchemaLoader(db_manager=self.mock_db)
        self.assertEqual(loader.db_mapping['table1'], 'test_db')

    @patch("builtins.open", side_effect=IOError("Permission denied"))
    @patch("os.path.exists", return_value=True)
    def test_load_with_file_error(self, mock_exists, mock_open):
        """测试文件读取错误"""
        self.mock_db.get_all_tables.return_value = ['table1']
        self.mock_db.get_table_schema.return_value = [{'name': 'col1', 'type': 'int', 'comment': 'id'}]

        # 应该能处理文件错误
        loader = SchemaLoader(db_manager=self.mock_db)
        self.assertIsNotNone(loader)

    @patch("builtins.open", new_callable=unittest.mock.mock_open, read_data="数据库名称：test_db\ntable1          测试表")
    @patch("os.path.exists", return_value=True)
    def test_get_table_info(self, mock_exists, mock_open):
        """测试获取表信息"""
        self.mock_db.get_all_tables.return_value = ['table1']
        self.mock_db.get_table_schema.return_value = [
            {'name': 'col1', 'type': 'int', 'comment': 'id'},
            {'name': 'col2', 'type': 'varchar(255)', 'comment': 'name'}
        ]

        loader = SchemaLoader(db_manager=self.mock_db)

        # 检查表信息是否正确加载
        self.assertIn('table1', loader.schema)

    @patch("os.path.exists", return_value=False)
    def test_reload_without_cache(self, mock_exists):
        """测试不带缓存重新加载"""
        self.mock_db.get_all_tables.return_value = ['table1']
        self.mock_db.get_table_schema.return_value = [{'name': 'col1', 'type': 'int', 'comment': 'id'}]

        loader = SchemaLoader(db_manager=self.mock_db)

        # 验证可以正常加载
        context1 = loader.get_schema_context()
        context2 = loader.get_schema_context()

        self.assertIn("Table: table1", context1)
        self.assertIn("Table: table1", context2)
