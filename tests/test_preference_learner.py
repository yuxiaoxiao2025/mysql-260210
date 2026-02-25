import unittest
import os
from src.learner.preference_learner import PreferenceLearner

class TestPreferenceLearner(unittest.TestCase):
    def setUp(self):
        self.test_file = "test_preferences_temp.json"
        if os.path.exists(self.test_file):
            os.remove(self.test_file)
    
    def tearDown(self):
        if os.path.exists(self.test_file):
            os.remove(self.test_file)
    
    def test_learn_and_lookup(self):
        """测试学习和查找功能"""
        learner = PreferenceLearner(storage_path=self.test_file)
        
        # 学习一个映射
        learner.learn(["固定车"], ["car_white_list"], "查固定车")
        
        # 查找记忆
        result = learner.lookup(["固定车"])
        self.assertIsNotNone(result)
        self.assertEqual(result["tables"], ["car_white_list"])
        self.assertGreaterEqual(result["confidence"], 0.5)
    
    def test_confidence_increases_with_reuse(self):
        """测试置信度随使用次数增加"""
        learner = PreferenceLearner(storage_path=self.test_file)
        
        # 第一次学习
        learner.learn(["固定车"], ["car_white_list"], "查固定车")
        result1 = learner.lookup(["固定车"])
        
        # 第二次学习相同映射
        learner.learn(["固定车"], ["car_white_list"], "查所有固定车")
        result2 = learner.lookup(["固定车"])
        
        self.assertGreater(result2["confidence"], result1["confidence"])
    
    def test_lookup_nonexistent(self):
        """测试查找不存在的映射"""
        learner = PreferenceLearner(storage_path=self.test_file)
        result = learner.lookup(["不存在的实体"])
        self.assertIsNone(result)
    
    def test_persistence(self):
        """测试持久化存储"""
        learner1 = PreferenceLearner(storage_path=self.test_file)
        learner1.learn(["固定车"], ["car_white_list"], "查固定车")
        
        # 创建新实例，应该能读取之前保存的数据
        learner2 = PreferenceLearner(storage_path=self.test_file)
        result = learner2.lookup(["固定车"])
        self.assertIsNotNone(result)
        self.assertEqual(result["tables"], ["car_white_list"])