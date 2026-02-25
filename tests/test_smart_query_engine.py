import unittest
from unittest.mock import MagicMock
from src.matcher.smart_query_engine import SmartQueryEngine

class TestSmartQueryEngine(unittest.TestCase):
    def setUp(self):
        self.mock_cache = MagicMock()
        self.mock_learner = MagicMock()
        self.mock_matcher = MagicMock()
        
        self.mock_matcher._extract_entities.return_value = ["固定车"]
        self.mock_matcher.match_tables.return_value = {
            "groups": {"matched_tables": [{"table_name": "car_white_list", "score": 0.95}]},
            "total_count": 1
        }
    
    def test_process_query_with_high_confidence_memory(self):
        """测试高置信度记忆时自动应用"""
        # 模拟高置信度记忆
        self.mock_learner.lookup.return_value = {
            "tables": ["car_white_list"],
            "confidence": 0.9,
            "used_count": 5
        }
        
        engine = SmartQueryEngine(self.mock_cache, self.mock_learner, self.mock_matcher)
        result = engine.process_query("查固定车")
        
        self.assertFalse(result["needs_interaction"])
        self.assertEqual(result["selected_tables"], ["car_white_list"])
    
    def test_process_query_with_low_confidence_memory(self):
        """测试低置信度记忆时需要确认"""
        self.mock_learner.lookup.return_value = {
            "tables": ["car_white_list"],
            "confidence": 0.6,
            "used_count": 1
        }
        self.mock_matcher.match_tables.return_value = {
            "groups": {"matched_tables": [{"table_name": "car_white_list", "recommended": True}]},
            "total_count": 1
        }
        
        engine = SmartQueryEngine(self.mock_cache, self.mock_learner, self.mock_matcher)
        result = engine.process_query("查固定车")
        
        self.assertTrue(result["needs_interaction"])
    
    def test_process_query_without_memory(self):
        """测试无记忆时需要交互"""
        self.mock_learner.lookup.return_value = None
        self.mock_matcher.match_tables.return_value = {
            "groups": {"matched_tables": [{"table_name": "car_white_list", "recommended": True}]},
            "total_count": 1
        }
        
        engine = SmartQueryEngine(self.mock_cache, self.mock_learner, self.mock_matcher)
        result = engine.process_query("查固定车")
        
        self.assertTrue(result["needs_interaction"])
        self.assertEqual(len(result["suggestions"]), 1)
    
    def test_record_user_choice(self):
        """测试记录用户选择"""
        engine = SmartQueryEngine(self.mock_cache, self.mock_learner, self.mock_matcher)
        engine.record_user_choice(["固定车"], ["car_white_list"], "查固定车")
        
        self.mock_learner.learn.assert_called_once()

if __name__ == '__main__':
    unittest.main()