import unittest
from unittest.mock import MagicMock, patch
import os
import json

class TestSchemaCache(unittest.TestCase):
    def setUp(self):
        self.mock_db = MagicMock()
        self.mock_db.get_table_schema.return_value = [
            {"name": "id", "type": "int", "comment": "主键"},
            {"name": "name", "type": "varchar", "comment": "姓名"}
        ]
        self.mock_db.get_all_tables.return_value = ["test_table"]
        self.cache_file = "test_cache_temp.json"
        # 清理测试文件
        if os.path.exists(self.cache_file):
            os.remove(self.cache_file)
    
    def tearDown(self):
        if os.path.exists(self.cache_file):
            os.remove(self.cache_file)
    
    def test_get_table_info_from_db(self):
        """测试首次获取表信息从数据库"""
        from src.cache.schema_cache import SchemaCache
        cache = SchemaCache(self.mock_db, cache_file=self.cache_file)
        table_info = cache.get_table_info("test_table")
        self.assertEqual(table_info["table_name"], "test_table")
        self.assertEqual(len(table_info["columns"]), 2)
    
    def test_get_table_info_from_memory_cache(self):
        """测试从内存缓存获取表信息"""
        from src.cache.schema_cache import SchemaCache
        cache = SchemaCache(self.mock_db, cache_file=self.cache_file)
        # 首次调用
        cache.get_table_info("test_table")
        # 第二次调用应该从内存缓存
        self.mock_db.get_table_schema.reset_mock()
        cache.get_table_info("test_table")
        self.mock_db.get_table_schema.assert_not_called()
    
    def test_warm_up_cache(self):
        """测试预热缓存功能"""
        from src.cache.schema_cache import SchemaCache
        cache = SchemaCache(self.mock_db, cache_file=self.cache_file)
        cache.warm_up()
        self.mock_db.get_all_tables.assert_called()

    def test_search_tables(self):
        """测试表搜索功能"""
        from src.cache.schema_cache import SchemaCache
        cache = SchemaCache(self.mock_db, cache_file=self.cache_file)
        # 预先设置一些缓存数据
        cache.memory_cache.put("user_table", {"table_name": "user_table", "columns": [{"name": "id", "comment": "用户ID"}]})
        cache.memory_cache.put("admin_user", {"table_name": "admin_user", "columns": []})
        cache.memory_cache.put("product_info", {"table_name": "product_info", "columns": []})
        
        results = cache.search_tables("user", limit=10)
        self.assertEqual(len(results), 2)  # user_table 和 admin_user
        self.assertTrue(any(r["table_name"] == "user_table" for r in results))


    def test_get_related_tables(self):
        """测试获取关联表功能"""
        from src.cache.schema_cache import SchemaCache
        cache = SchemaCache(self.mock_db, cache_file=self.cache_file)
        # 设置外键关系
        cache.memory_cache.put("orders", {
            "table_name": "orders",
            "columns": [],
            "foreign_keys": [{"column": "user_id", "references": "users.id"}]
        })
        cache.memory_cache.put("users", {
            "table_name": "users",
            "columns": [],
            "foreign_keys": [{"column": "role_id", "references": "roles.id"}]
        })
        cache.memory_cache.put("roles", {"table_name": "roles", "columns": []})
        
        related = cache.get_related_tables("orders", max_depth=2)
        self.assertIn("users", [r["table_name"] for r in related])


    def test_invalidate(self):
        """测试缓存失效"""
        from src.cache.schema_cache import SchemaCache
        cache = SchemaCache(self.mock_db, cache_file=self.cache_file)
        cache.memory_cache.put("test_table", {"table_name": "test_table", "columns": []})
        
        cache.invalidate("test_table")
        # 缓存应该被清除
        result = cache.memory_cache.get("test_table")
        self.assertIsNone(result)
