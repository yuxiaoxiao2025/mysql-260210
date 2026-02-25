import unittest
from unittest.mock import MagicMock
from src.matcher.table_matcher import TableMatcher

class TestTableMatcher(unittest.TestCase):
    def setUp(self):
        self.mock_cache = MagicMock()
        self.mock_cache.search_tables.return_value = [
            {"table_name": "car_white_list", "description": "固定车白名单", "columns": []},
            {"table_name": "vehicle_base", "description": "车辆基础信息", "columns": []}
        ]
        self.mock_cache.get_table_info.return_value = {
            "table_name": "car_white_list",
            "description": "固定车白名单",
            "columns": []
        }
    
    def test_match_tables_basic(self):
        """测试基本表匹配功能"""
        matcher = TableMatcher(self.mock_cache)
        result = matcher.match_tables("查固定车")
        self.assertIn("groups", result)
        self.assertIn("total_count", result)
    
    def test_extract_entities(self):
        """测试实体提取"""
        matcher = TableMatcher(self.mock_cache)
        entities = matcher._extract_entities("查固定车和园区信息")
        self.assertIsInstance(entities, list)
        self.assertGreater(len(entities), 0)
    
    def test_smart_recommend_fixed_car(self):
        """测试智能推荐 - 固定车"""
        matcher = TableMatcher(self.mock_cache)
        candidates = [
            {"table_name": "car_white_list", "description": "固定车白名单"},
            {"table_name": "car_temp", "description": "临时车记录"}
        ]
        recommended = matcher.smart_recommend("固定车", candidates)
        self.assertTrue(any(r["recommended"] for r in recommended))
    
    def test_get_table_detail(self):
        """测试获取表详情"""
        matcher = TableMatcher(self.mock_cache)
        detail = matcher.get_table_detail("car_white_list")
        self.assertEqual(detail["table_name"], "car_white_list")