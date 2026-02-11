import unittest
import os
import json
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
