import unittest
import pandas as pd
from src.preview.diff_renderer import DiffRenderer

class TestDiffRenderer(unittest.TestCase):
    def test_render_update_diff(self):
        """测试 UPDATE 操作的对比渲染"""
        renderer = DiffRenderer()
        
        before_df = pd.DataFrame([{"id": 1, "name": "张三", "state": 0}])
        after_df = pd.DataFrame([{"id": 1, "name": "张三", "state": 1}])
        
        changes = renderer.render_update_diff(before_df, after_df, ["id"])
        self.assertEqual(len(changes), 1)
        self.assertIn("state", changes[0]["changed_fields"])
        self.assertEqual(changes[0]["before"]["state"], 0)
        self.assertEqual(changes[0]["after"]["state"], 1)
    
    def test_render_update_diff_no_changes(self):
        """测试无变化时不返回"""
        renderer = DiffRenderer()
        
        before_df = pd.DataFrame([{"id": 1, "name": "张三", "state": 1}])
        after_df = pd.DataFrame([{"id": 1, "name": "张三", "state": 1}])
        
        changes = renderer.render_update_diff(before_df, after_df, ["id"])
        self.assertEqual(len(changes), 0)
    
    def test_render_delete_preview(self):
        """测试 DELETE 操作的预览渲染"""
        renderer = DiffRenderer()
        
        before_df = pd.DataFrame([
            {"id": 1, "name": "张三", "state": 0},
            {"id": 2, "name": "李四", "state": 0}
        ])
        
        delete_data = renderer.render_delete_preview(before_df)
        self.assertEqual(len(delete_data), 2)
        self.assertEqual(delete_data[0]["id"], 1)
    
    def test_render_delete_preview_empty(self):
        """测试空数据"""
        renderer = DiffRenderer()
        delete_data = renderer.render_delete_preview(pd.DataFrame())
        self.assertEqual(len(delete_data), 0)
    
    def test_render_insert_preview(self):
        """测试 INSERT 操作的预览渲染"""
        renderer = DiffRenderer()
        
        values = {"login_name": "new_user", "name": "新用户", "state": 1}
        insert_data = renderer.render_insert_preview(values)
        self.assertEqual(insert_data["login_name"], "new_user")
        self.assertEqual(insert_data["name"], "新用户")
    
    def test_render_diff_update(self):
        """测试完整的 diff 渲染 - UPDATE"""
        renderer = DiffRenderer()
        
        before_df = pd.DataFrame([{"id": 1, "name": "张三", "state": 0}])
        after_df = pd.DataFrame([{"id": 1, "name": "张三", "state": 1}])
        
        result = renderer.render_diff(before_df, after_df, "update", ["id"])
        self.assertEqual(result["operation_type"], "update")
        self.assertIn("summary", result)
        self.assertIn("changes", result)
        self.assertEqual(result["summary"]["updated"], 1)