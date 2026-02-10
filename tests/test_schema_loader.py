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
