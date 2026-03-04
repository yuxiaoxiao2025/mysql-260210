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


class TestPreferenceLearnerMoreScenarios(unittest.TestCase):
    """更多 PreferenceLearner 测试场景"""

    def setUp(self):
        """设置测试环境"""
        self.test_file = "test_preferences_more_temp.json"
        if os.path.exists(self.test_file):
            os.remove(self.test_file)

    def tearDown(self):
        """清理测试环境"""
        if os.path.exists(self.test_file):
            os.remove(self.test_file)

    def test_learn_with_multiple_keywords(self):
        """测试使用多个关键词学习"""
        learner = PreferenceLearner(storage_path=self.test_file)

        # 使用多个关键词学习
        learner.learn(["固定车", "白名单"], ["car_white_list"], "查固定车")

        # 用任何一个关键词都应该能找到
        result1 = learner.lookup(["固定车"])
        self.assertIsNotNone(result1)

        result2 = learner.lookup(["白名单"])
        self.assertIsNotNone(result2)

    def test_learn_with_multiple_tables(self):
        """测试学习多个表"""
        learner = PreferenceLearner(storage_path=self.test_file)

        learner.learn(["订单"], ["orders", "order_items"], "查订单")

        result = learner.lookup(["订单"])
        self.assertEqual(result["tables"], ["orders", "order_items"])

    def test_learn_different_queries_same_keywords(self):
        """测试相同关键词的不同查询"""
        learner = PreferenceLearner(storage_path=self.test_file)

        # 第一次学习
        learner.learn(["固定车"], ["car_white_list"], "查固定车")

        # 第二次学习相同关键词但不同表（应该覆盖）
        learner.learn(["固定车"], ["car_info"], "查车辆信息")

        result = learner.lookup(["固定车"])
        self.assertEqual(result["tables"], ["car_info"])

    def test_confidence_decay(self):
        """测试置信度衰减（如果实现了的话）"""
        learner = PreferenceLearner(storage_path=self.test_file)

        learner.learn(["测试"], ["test_table"], "测试查询")
        result1 = learner.lookup(["测试"])
        confidence1 = result1["confidence"]

        # 多次使用相同映射
        for i in range(5):
            learner.learn(["测试"], ["test_table"], f"测试查询{i}")

        result2 = learner.lookup(["测试"])
        confidence2 = result2["confidence"]

        # 置信度应该增加或保持
        self.assertGreaterEqual(confidence2, confidence1)

    def test_empty_keywords_list(self):
        """测试空关键词列表"""
        learner = PreferenceLearner(storage_path=self.test_file)

        learner.learn([], ["test_table"], "测试")

        # 空关键词应该无法查找
        result = learner.lookup([])
        self.assertIsNone(result)

    def test_empty_tables_list(self):
        """测试空表列表"""
        learner = PreferenceLearner(storage_path=self.test_file)

        learner.learn(["测试"], [], "测试")

        result = learner.lookup(["测试"])
        if result:
            self.assertEqual(result["tables"], [])

    def test_special_characters_in_keywords(self):
        """测试关键词中的特殊字符"""
        learner = PreferenceLearner(storage_path=self.test_file)

        learner.learn(["测试@#%", "特殊字符"], ["test_table"], "测试")

        result = learner.lookup(["测试@#%"])
        self.assertIsNotNone(result)

    def test_case_sensitive_lookup(self):
        """测试大小写敏感的查找"""
        learner = PreferenceLearner(storage_path=self.test_file)

        learner.learn(["FixedCar"], ["car_table"], "查询")

        # 大小写应该匹配（根据实现可能不同）
        result1 = learner.lookup(["FixedCar"])
        self.assertIsNotNone(result1)

        result2 = learner.lookup(["fixedcar"])
        # 如果实现区分大小写，这可能返回 None

    def test_learn_without_storage_path(self):
        """测试不指定存储路径"""
        learner = PreferenceLearner()

        # 应该使用默认路径
        learner.learn(["测试"], ["test_table"], "测试")

        # 可能需要手动清理默认文件
        # 这里只测试不会报错
        self.assertIsNotNone(learner)

    def test_multiple_learners_same_file(self):
        """测试多个学习者使用相同文件"""
        learner1 = PreferenceLearner(storage_path=self.test_file)
        learner1.learn(["测试"], ["table1"], "测试1")

        # 创建另一个学习者实例
        learner2 = PreferenceLearner(storage_path=self.test_file)
        learner2.learn(["测试2"], ["table2"], "测试2")

        # 两者都应该能访问数据
        result1 = learner2.lookup(["测试"])
        result2 = learner2.lookup(["测试2"])

        self.assertIsNotNone(result1)
        self.assertIsNotNone(result2)

    def test_clear_learning(self):
        """测试清除学习数据"""
        learner = PreferenceLearner(storage_path=self.test_file)

        learner.learn(["测试"], ["test_table"], "测试")
        result1 = learner.lookup(["测试"])
        self.assertIsNotNone(result1)

        # 删除文件
        if os.path.exists(self.test_file):
            os.remove(self.test_file)

        # 重新创建学习者
        learner2 = PreferenceLearner(storage_path=self.test_file)
        result2 = learner2.lookup(["测试"])

        # 应该找不到数据
        self.assertIsNone(result2)