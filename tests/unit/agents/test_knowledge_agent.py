"""KnowledgeAgent 单元测试"""
import pytest
from unittest.mock import MagicMock, patch
from src.agents.impl.knowledge_agent import KnowledgeAgent
from src.agents.context import AgentContext, IntentModel


class TestKnowledgeAgentErrorHandling:
    """测试 KnowledgeAgent 错误处理"""

    def test_chat_stream_returns_none(self):
        """chat_stream 返回 None 时应返回失败结果"""
        config = MagicMock()
        llm_client = MagicMock()
        llm_client.chat_stream.return_value = None

        agent = KnowledgeAgent(config, llm_client=llm_client)

        context = AgentContext(user_input="测试问题")
        context.intent = IntentModel(type="chat", operation_id="general_chat")

        result = agent._run_impl(context)

        assert result.success is False
        assert "异常" in result.message or "LLM" in result.message

    def test_chat_stream_raises_exception(self):
        """chat_stream 抛出异常时应捕获"""
        config = MagicMock()
        llm_client = MagicMock()
        llm_client.chat_stream.side_effect = Exception("API Error")

        agent = KnowledgeAgent(config, llm_client=llm_client)

        context = AgentContext(user_input="测试问题")
        context.intent = IntentModel(type="chat", operation_id="general_chat")

        result = agent._run_impl(context)

        assert result.success is False
        assert "异常" in result.message

    def test_valid_stream_returns_success(self):
        """有效 generator 应返回成功"""
        config = MagicMock()
        llm_client = MagicMock()

        def mock_generator():
            yield {"type": "content", "content": "测试回复"}

        llm_client.chat_stream.return_value = mock_generator()

        agent = KnowledgeAgent(config, llm_client=llm_client)

        context = AgentContext(user_input="测试问题")
        context.intent = IntentModel(type="chat", operation_id="general_chat")

        result = agent._run_impl(context)

        assert result.success is True
        assert result.message == "knowledge_stream_ready"

    def test_intent_type_mismatch(self):
        """意图类型不匹配时应返回失败"""
        config = MagicMock()
        llm_client = MagicMock()

        agent = KnowledgeAgent(config, llm_client=llm_client)

        context = AgentContext(user_input="测试问题")
        context.intent = IntentModel(type="query", operation_id="some_query")

        result = agent._run_impl(context)

        assert result.success is False
        assert "qa/chat" in result.message

    def test_no_intent(self):
        """没有意图时应返回失败"""
        config = MagicMock()
        llm_client = MagicMock()

        agent = KnowledgeAgent(config, llm_client=llm_client)

        context = AgentContext(user_input="测试问题")
        # context.intent 为 None

        result = agent._run_impl(context)

        assert result.success is False