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

if __name__ == '__main__':
    unittest.main()
