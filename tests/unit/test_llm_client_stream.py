"""LLMClient.chat_stream 单元测试"""
import pytest
from unittest.mock import patch, MagicMock
from src.llm_client import LLMClient


class TestChatStreamValidation:
    """测试 chat_stream 的输入验证"""

    def test_empty_messages_returns_error_chunk(self):
        """空消息列表应返回 error chunk"""
        client = LLMClient.__new__(LLMClient)
        client.api_key = "test-key"
        client.client = None

        chunks = list(client.chat_stream(messages=[]))

        assert len(chunks) == 1
        assert chunks[0]["type"] == "error"
        assert "消息列表为空" in chunks[0]["content"]

    def test_no_api_key_returns_error_chunk(self):
        """未配置 API key 应返回 error chunk"""
        client = LLMClient.__new__(LLMClient)
        client.api_key = None
        client.client = None

        chunks = list(client.chat_stream(messages=[{"role": "user", "content": "test"}]))

        assert len(chunks) == 1
        assert chunks[0]["type"] == "error"
        assert "API 密钥未配置" in chunks[0]["content"]


class TestChatStreamOutputValidation:
    """测试 chat_stream 的输出验证"""

    @patch('src.llm_client.Generation.call')
    def test_no_content_returns_fallback_message(self, mock_call):
        """LLM 无输出时返回降级消息"""
        client = LLMClient.__new__(LLMClient)
        client.api_key = "test-key"
        client.client = None
        client._metrics_collector = MagicMock()

        # 模拟空响应：确保 _extract_stream_choice 返回 None
        mock_chunk = MagicMock()
        # 明确设置为空列表（falsy）或 None
        mock_chunk.choices = []  # OpenAI 格式：空列表
        # 对于 DashScope 格式
        mock_output = MagicMock()
        mock_output.choices = []  # 空列表
        mock_chunk.output = mock_output
        mock_chunk.usage = None
        mock_call.return_value = iter([mock_chunk])

        chunks = list(client.chat_stream(messages=[{"role": "user", "content": "test"}]))

        # 应该包含降级消息
        content_chunks = [c for c in chunks if c.get("type") == "content"]
        assert len(content_chunks) >= 1
        assert "抱歉" in content_chunks[-1]["content"] or "无法回答" in content_chunks[-1]["content"]

    @patch('src.llm_client.Generation.call')
    def test_exception_returns_error_chunk(self, mock_call):
        """异常时返回 error chunk"""
        client = LLMClient.__new__(LLMClient)
        client.api_key = "test-key"
        client.client = None
        client._metrics_collector = MagicMock()

        mock_call.side_effect = Exception("Network error")

        chunks = list(client.chat_stream(messages=[{"role": "user", "content": "test"}]))

        assert len(chunks) == 1
        assert chunks[0]["type"] == "error"
        assert "Network error" in chunks[0]["content"]