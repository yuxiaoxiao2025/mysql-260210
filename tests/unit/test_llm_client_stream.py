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