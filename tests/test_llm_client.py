import unittest
import os
import json
import pytest
from unittest.mock import MagicMock, patch
from src.llm_client import LLMClient

class TestLLMClient(unittest.TestCase):
    @patch.dict(os.environ, {"DASHSCOPE_API_KEY": "sk-test"})
    @patch("dashscope.Generation.call")
    def test_generate_sql(self, mock_call):
        mock_response = MagicMock()
        mock_response.status_code = 200
        # Mocking the nested structure: response.output.choices[0].message.content
        mock_choice = MagicMock()
        mock_choice.message.content = '{"sql": "SELECT * FROM table", "filename": "test_file", "sheet_name": "test_sheet", "reasoning": "test reasoning"}'
        
        mock_response.output.choices = [mock_choice]
        mock_call.return_value = mock_response

        client = LLMClient()
        result = client.generate_sql("query", "context")
        
        self.assertEqual(result['sql'], "SELECT * FROM table")
        self.assertEqual(result['filename'], "test_file")
        self.assertEqual(result['sheet_name'], "test_sheet")

    @patch.dict(os.environ, {"DASHSCOPE_API_KEY": "sk-test"})
    @patch("dashscope.Generation.call")
    def test_generate_sql_markdown_cleanup(self, mock_call):
        """Test that markdown code blocks are removed"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_choice = MagicMock()
        mock_choice.message.content = '```json\n{"sql": "SELECT 1", "filename": "f", "sheet_name": "s", "reasoning": "r"}\n```'
        
        mock_response.output.choices = [mock_choice]
        mock_call.return_value = mock_response

        client = LLMClient()
        result = client.generate_sql("query", "context")
        
        self.assertEqual(result['sql'], "SELECT 1")

    @patch.dict(os.environ, {"DASHSCOPE_API_KEY": "sk-test"})
    @patch("dashscope.Generation.call")
    def test_generate_sql_dml_contract(self, mock_call):
        """Test that LLM returns extended contract with DML support and preview SQL"""
        # Mock response with extended contract fields
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_choice = MagicMock()
        mock_choice.message.content = '''{
    "sql": "UPDATE users SET status = 'active' WHERE id IN (1, 2, 3)",
    "filename": "update_user_status",
    "sheet_name": "用户状态更新",
    "reasoning": "Update user status to active",
    "intent": "mutation",
    "preview_sql": "SELECT id, name, status FROM users WHERE id IN (1, 2, 3)",
    "key_columns": ["id"],
    "warnings": ["This will update 3 rows"]
}'''

        mock_response.output.choices = [mock_choice]
        mock_call.return_value = mock_response

        client = LLMClient()
        result = client.generate_sql("激活用户1,2,3的状态", "context")

        # Verify original fields still exist
        self.assertEqual(result['sql'], "UPDATE users SET status = 'active' WHERE id IN (1, 2, 3)")
        self.assertEqual(result['filename'], "update_user_status")
        self.assertEqual(result['sheet_name'], "用户状态更新")
        self.assertEqual(result['reasoning'], "Update user status to active")

        # Verify new DML fields
        self.assertEqual(result['intent'], "mutation")
        self.assertEqual(result['preview_sql'], "SELECT id, name, status FROM users WHERE id IN (1, 2, 3)")
        self.assertEqual(result['key_columns'], ["id"])
        self.assertEqual(result['warnings'], ["This will update 3 rows"])

    @patch.dict(os.environ, {"DASHSCOPE_API_KEY": "sk-test"})
    @patch("dashscope.Generation.call")
    def test_generate_sql_dml_contract_defaults(self, mock_call):
        """Test that default values are applied when LLM returns minimal response"""
        # Mock response with minimal fields (old contract)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_choice = MagicMock()
        mock_choice.message.content = '{"sql": "SELECT * FROM users", "filename": "f", "sheet_name": "s", "reasoning": "r"}'

        mock_response.output.choices = [mock_choice]
        mock_call.return_value = mock_response

        client = LLMClient()
        result = client.generate_sql("查询所有用户", "context")

        # Verify defaults are applied
        self.assertEqual(result['intent'], "query")  # Default for SELECT
        self.assertEqual(result.get('preview_sql'), None)  # No preview for SELECT
        self.assertEqual(result.get('key_columns'), [])  # Empty list default
        self.assertEqual(result.get('warnings'), [])  # Empty list default

    @patch.dict(os.environ, {"DASHSCOPE_API_KEY": "sk-test"})
    @patch("dashscope.Generation.call")
    def test_generate_sql_detects_dml_intent(self, mock_call):
        """Test that intent='mutation' is returned for DELETE/UPDATE/INSERT queries"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_choice = MagicMock()
        mock_choice.message.content = '''{
    "sql": "DELETE FROM logs WHERE created_at < '2024-01-01'",
    "filename": "clean_old_logs",
    "sheet_name": "清理旧日志",
    "reasoning": "Delete old log entries",
    "intent": "mutation",
    "preview_sql": "SELECT COUNT(*) FROM logs WHERE created_at < '2024-01-01'",
    "key_columns": ["id"],
    "warnings": ["This will delete log records permanently"]
}'''

        mock_response.output.choices = [mock_choice]
        mock_call.return_value = mock_response

        client = LLMClient()
        result = client.generate_sql("清理2024年前的日志", "context")

        self.assertEqual(result['intent'], "mutation")
        self.assertIn("DELETE", result['sql'].upper())
        self.assertIsNotNone(result['preview_sql'])

if __name__ == '__main__':
    unittest.main()


# ==================== 补充测试用例 ====================


class TestLLMClientConversationHistory:
    """测试对话历史管理"""

    @patch.dict(os.environ, {"DASHSCOPE_API_KEY": "sk-test"})
    def test_add_to_history_success(self):
        """测试添加成功的查询到历史"""
        client = LLMClient()
        client._add_to_history("查询所有用户", {
            'sql': 'SELECT * FROM users',
            'reasoning': '查询所有用户',
            'success': True
        })

        assert len(client.conversation_history) == 1
        assert client.conversation_history[0][0] == "查询所有用户"
        assert client.conversation_history[0][1]['sql'] == 'SELECT * FROM users'

    @patch.dict(os.environ, {"DASHSCOPE_API_KEY": "sk-test"})
    def test_add_to_history_max_rounds(self):
        """测试历史记录最大轮数限制"""
        client = LLMClient()
        client.max_history_rounds = 3

        # 添加 5 轮对话
        for i in range(5):
            client._add_to_history(f"查询{i}", {
                'sql': f'SELECT * FROM table{i}',
                'success': True
            })

        # 应该只保留最后 3 轮
        assert len(client.conversation_history) == 3
        assert client.conversation_history[0][0] == "查询2"
        assert client.conversation_history[1][0] == "查询3"
        assert client.conversation_history[2][0] == "查询4"

    @patch.dict(os.environ, {"DASHSCOPE_API_KEY": "sk-test"})
    def test_clear_history(self):
        """测试清除历史"""
        client = LLMClient()
        client._add_to_history("查询1", {'sql': 'SELECT 1', 'success': True})
        client._add_to_history("查询2", {'sql': 'SELECT 2', 'success': True})

        assert len(client.conversation_history) == 2

        client.clear_history()

        assert len(client.conversation_history) == 0

    @patch.dict(os.environ, {"DASHSCOPE_API_KEY": "sk-test"})
    def test_add_error_to_history(self):
        """测试添加错误到历史"""
        client = LLMClient()
        client.add_error_to_history("查询失败", "SQL 语法错误")

        assert len(client.conversation_history) == 1
        assert client.conversation_history[0][0] == "查询失败"
        assert client.conversation_history[0][1]['error'] == "SQL 语法错误"
        assert client.conversation_history[0][1]['success'] is False

    @patch.dict(os.environ, {"DASHSCOPE_API_KEY": "sk-test"})
    def test_add_error_to_history_max_rounds(self):
        """测试错误历史的最大轮数限制"""
        client = LLMClient()
        client.max_history_rounds = 2

        # 添加 4 个错误
        for i in range(4):
            client.add_error_to_history(f"错误{i}", f"描述{i}")

        # 应该只保留最后 2 个
        assert len(client.conversation_history) == 2
        assert "错误2" in client.conversation_history[0][0]
        assert "错误3" in client.conversation_history[1][0]


class TestLLMClientRecognizeIntent:
    """测试意图识别功能"""

    @patch.dict(os.environ, {"DASHSCOPE_API_KEY": "sk-test"})
    @patch("dashscope.Generation.call")
    def test_recognize_intent_success(self, mock_call):
        """测试成功识别意图"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_choice = MagicMock()
        mock_choice.message.content = '''{
            "operation_id": "plate_distribute",
            "confidence": 0.95,
            "params": {
                "plate": "沪ABC1234",
                "park_name": "国际商务中心"
            },
            "fallback_sql": null,
            "reasoning": "用户想要下发车牌",
            "missing_params": [],
            "suggestions": []
        }'''

        mock_response.output.choices = [mock_choice]
        mock_call.return_value = mock_response

        client = LLMClient()
        result = client.recognize_intent(
            user_query="下发车牌 沪ABC1234 到 国际商务中心",
            operations_context="Available operations...",
            enum_values={"park_names": ["国际商务中心"]}
        )

        assert result['operation_id'] == "plate_distribute"
        assert result['confidence'] == 0.95
        assert result['params']['plate'] == "沪ABC1234"
        assert result['params']['park_name'] == "国际商务中心"
        assert result['missing_params'] == []

    @patch.dict(os.environ, {"DASHSCOPE_API_KEY": "sk-test"})
    @patch("dashscope.Generation.call")
    def test_recognize_intent_with_missing_params(self, mock_call):
        """测试识别意图时发现缺失参数"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_choice = MagicMock()
        mock_choice.message.content = '''{
            "operation_id": "plate_distribute",
            "confidence": 0.85,
            "params": {
                "plate": "沪ABC1234"
            },
            "fallback_sql": null,
            "reasoning": "缺少场库名称",
            "missing_params": ["park_name"],
            "suggestions": ["请提供场库名称"]
        }'''

        mock_response.output.choices = [mock_choice]
        mock_call.return_value = mock_response

        client = LLMClient()
        result = client.recognize_intent(
            user_query="下发车牌 沪ABC1234",
            operations_context="Available operations..."
        )

        assert result['missing_params'] == ["park_name"]
        assert len(result['suggestions']) > 0

    @patch.dict(os.environ, {"DASHSCOPE_API_KEY": "sk-test"})
    @patch("dashscope.Generation.call")
    def test_recognize_intent_no_match(self, mock_call):
        """测试没有匹配的操作"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_choice = MagicMock()
        mock_choice.message.content = '''{
            "operation_id": null,
            "confidence": 0.0,
            "params": {},
            "fallback_sql": "SELECT * FROM plates",
            "reasoning": "无法匹配任何操作",
            "missing_params": [],
            "suggestions": ["请尝试其他描述"]
        }'''

        mock_response.output.choices = [mock_choice]
        mock_call.return_value = mock_response

        client = LLMClient()
        result = client.recognize_intent(
            user_query="我想吃苹果",
            operations_context="Available operations..."
        )

        assert result['operation_id'] is None
        assert result['confidence'] == 0.0
        assert result['fallback_sql'] == "SELECT * FROM plates"

    @patch.dict(os.environ, {"DASHSCOPE_API_KEY": "sk-test"})
    @patch("dashscope.Generation.call")
    def test_recognize_intent_json_decode_error(self, mock_call):
        """测试 JSON 解析错误"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_choice = MagicMock()
        mock_choice.message.content = "invalid json"

        mock_response.output.choices = [mock_choice]
        mock_call.return_value = mock_response

        client = LLMClient()

        # JSON 解析错误返回错误结果，不抛出异常
        result = client.recognize_intent(
            user_query="查询车牌",
            operations_context="Available operations..."
        )

        # 验证返回的错误结果
        assert result['operation_id'] is None
        assert result['confidence'] == 0.0
        assert "解析响应失败" in result['reasoning'] or "JSON" in result['reasoning']
        assert len(result['suggestions']) > 0

    @patch.dict(os.environ, {"DASHSCOPE_API_KEY": "sk-test"})
    @patch("dashscope.Generation.call")
    def test_recognize_intent_api_error(self, mock_call):
        """测试 API 错误"""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.code = 400
        mock_response.message = "Bad request"

        mock_call.return_value = mock_response

        client = LLMClient()

        with pytest.raises(Exception) as context:
            client.recognize_intent(
                user_query="查询车牌",
                operations_context="Available operations..."
            )

        assert "API Error" in str(context.value) or "意图识别失败" in str(context.value)

    @patch.dict(os.environ, {"DASHSCOPE_API_KEY": "sk-test"})
    @patch("dashscope.Generation.call")
    def test_recognize_intent_with_enum_values(self, mock_call):
        """测试带枚举值的意图识别"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_choice = MagicMock()
        mock_choice.message.content = '''{
            "operation_id": "plate_distribute",
            "confidence": 0.9,
            "params": {
                "plate": "沪ABC1234",
                "park_name": "国际商务中心"
            },
            "fallback_sql": null,
            "reasoning": "匹配成功",
            "missing_params": [],
            "suggestions": []
        }'''

        mock_response.output.choices = [mock_choice]
        mock_call.return_value = mock_response

        client = LLMClient()
        enum_values = {
            "park_names": ["国际商务中心", "科技园", "商业广场"],
            "operator_names": ["张三", "李四", "王五"]
        }

        result = client.recognize_intent(
            user_query="下发车牌",
            operations_context="Available operations...",
            enum_values=enum_values
        )

        assert result['params']['park_name'] == "国际商务中心"


class TestLLMClientSuggestParamValue:
    """测试参数值推荐功能"""

    @patch.dict(os.environ, {"DASHSCOPE_API_KEY": "sk-test"})
    def test_suggest_param_value_with_list(self):
        """测试从列表推荐参数值"""
        client = LLMClient()
        available = ["国际商务中心", "科技园", "商业广场", "住宅小区", "医院"]

        result = client.suggest_param_value(
            param_name="park_name",
            param_description="场库名称",
            available_values=available,
            user_context="查询车牌"
        )

        assert "suggestions" in result
        assert "best_match" in result
        assert len(result['suggestions']) == 5
        assert result['best_match'] == "国际商务中心"

    @patch.dict(os.environ, {"DASHSCOPE_API_KEY": "sk-test"})
    def test_suggest_param_value_with_dict_list(self):
        """测试从字典列表推荐参数值"""
        client = LLMClient()
        available = [
            {"value": "park1", "display": "国际商务中心"},
            {"value": "park2", "display": "科技园"},
            {"value": "park3", "display": "商业广场"},
        ]

        result = client.suggest_param_value(
            param_name="park_name",
            param_description="场库名称",
            available_values=available
        )

        assert len(result['suggestions']) == 3
        assert result['suggestions'][0]['value'] == "park1"
        assert result['suggestions'][0]['display'] == "国际商务中心"
        assert result['best_match'] == "park1"

    @patch.dict(os.environ, {"DASHSCOPE_API_KEY": "sk-test"})
    def test_suggest_param_value_empty_list(self):
        """测试空列表的情况"""
        client = LLMClient()

        result = client.suggest_param_value(
            param_name="park_name",
            param_description="场库名称",
            available_values=[]
        )

        assert result['suggestions'] == []
        assert result['best_match'] is None

    @patch.dict(os.environ, {"DASHSCOPE_API_KEY": "sk-test"})
    def test_suggest_param_value_large_list(self):
        """测试大列表的情况（应该只返回前5个）"""
        client = LLMClient()
        available = [f"场库{i}" for i in range(10)]

        result = client.suggest_param_value(
            param_name="park_name",
            param_description="场库名称",
            available_values=available
        )

        assert len(result['suggestions']) == 5
        assert result['best_match'] == "场库0"


class TestLLMClientGenerateSQLWithHistory:
    """测试带历史记录的 SQL 生成"""

    @patch.dict(os.environ, {"DASHSCOPE_API_KEY": "sk-test"})
    @patch("dashscope.Generation.call")
    def test_generate_sql_with_conversation_history(self, mock_call):
        """测试使用对话历史生成 SQL"""
        # 第一次调用
        mock_response1 = MagicMock()
        mock_response1.status_code = 200
        mock_choice1 = MagicMock()
        mock_choice1.message.content = '''{
            "sql": "SELECT * FROM users WHERE status = 'active'",
            "filename": "active_users",
            "sheet_name": "活跃用户",
            "reasoning": "查询活跃用户"
        }'''

        mock_response1.output.choices = [mock_choice1]
        mock_call.return_value = mock_response1

        client = LLMClient()
        result1 = client.generate_sql("查询活跃用户", "schema context")

        assert result1['sql'] == "SELECT * FROM users WHERE status = 'active'"
        assert len(client.conversation_history) == 1

        # 第二次调用，应该包含历史
        mock_response2 = MagicMock()
        mock_response2.status_code = 200
        mock_choice2 = MagicMock()
        mock_choice2.message.content = '''{
            "sql": "SELECT * FROM users WHERE status = 'inactive'",
            "filename": "inactive_users",
            "sheet_name": "非活跃用户",
            "reasoning": "基于之前的查询，修改状态条件"
        }'''

        mock_response2.output.choices = [mock_choice2]
        mock_call.return_value = mock_response2

        result2 = client.generate_sql("查询非活跃用户", "schema context")

        assert result2['sql'] == "SELECT * FROM users WHERE status = 'inactive'"
        assert len(client.conversation_history) == 2

    @patch.dict(os.environ, {"DASHSCOPE_API_KEY": "sk-test"})
    @patch("dashscope.Generation.call")
    def test_generate_sql_with_error_context(self, mock_call):
        """测试带错误上下文的 SQL 生成"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_choice = MagicMock()
        mock_choice.message.content = '''{
            "sql": "SELECT name, email FROM users WHERE status = 'active'",
            "filename": "active_users",
            "sheet_name": "活跃用户",
            "reasoning": "修正列名"
        }'''

        mock_response.output.choices = [mock_choice]
        mock_call.return_value = mock_response

        client = LLMClient()
        result = client.generate_sql(
            "查询活跃用户",
            "schema context",
            error_context="Unknown column 'user_name' in 'field list'"
        )

        assert 'name' in result['sql']
        assert 'email' in result['sql']

    @patch.dict(os.environ, {"DASHSCOPE_API_KEY": "sk-test"})
    def test_generate_sql_without_api_key(self):
        """测试没有 API Key 的情况"""
        # 临时移除 API Key
        import os
        original_key = os.environ.get("DASHSCOPE_API_KEY")
        if "DASHSCOPE_API_KEY" in os.environ:
            del os.environ["DASHSCOPE_API_KEY"]

        try:
            client = LLMClient()
            assert client.api_key is None
            assert client.last_result is None
            assert client.conversation_history == []
        finally:
            # 恢复 API Key
            if original_key:
                os.environ["DASHSCOPE_API_KEY"] = original_key


class TestLLMClientLastResult:
    """测试最后结果存储"""

    @patch.dict(os.environ, {"DASHSCOPE_API_KEY": "sk-test"})
    @patch("dashscope.Generation.call")
    def test_last_result_stored(self, mock_call):
        """测试最后结果被正确存储"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_choice = MagicMock()
        mock_choice.message.content = '''{
            "sql": "SELECT * FROM users",
            "filename": "users",
            "sheet_name": "用户",
            "reasoning": "查询所有用户"
        }'''

        mock_response.output.choices = [mock_choice]
        mock_call.return_value = mock_response

        client = LLMClient()
        result = client.generate_sql("查询所有用户", "schema context")

        assert client.last_result is not None
        assert client.last_result == result
        assert client.last_result['sql'] == "SELECT * FROM users"
