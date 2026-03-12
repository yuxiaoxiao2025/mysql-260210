"""Orchestrator 对话流程测试"""
import pytest
from unittest.mock import MagicMock
from src.agents.orchestrator import Orchestrator
from src.agents.context import AgentContext, IntentModel
from src.agents.models import AgentResult


class TestOrchestratorConversation:
    """测试 Orchestrator 对话流程"""

    def test_knowledge_agent_failure_sets_error_message(self):
        """KnowledgeAgent 失败时应设置错误消息"""
        # 创建 mock agents
        intent_agent = MagicMock()
        intent_agent.run.return_value = MagicMock(success=True)

        retrieval_agent = MagicMock()
        retrieval_agent.run.return_value = MagicMock(success=True)

        knowledge_agent = MagicMock()
        knowledge_agent.run.return_value = AgentResult(
            success=False,
            message="对话服务异常",
            data=None
        )

        orchestrator = Orchestrator(
            intent_agent=intent_agent,
            retrieval_agent=retrieval_agent,
            knowledge_agent=knowledge_agent
        )

        context = orchestrator._handle_conversation(AgentContext(user_input="测试"))

        assert "knowledge_failed" in context.step_history
        assert context.execution_result is not None
        assert "异常" in context.execution_result or "不可用" in context.execution_result

    def test_knowledge_agent_returns_none(self):
        """KnowledgeAgent 返回 None data 时应有降级"""
        intent_agent = MagicMock()
        intent_agent.run.return_value = MagicMock(success=True)

        retrieval_agent = MagicMock()
        retrieval_agent.run.return_value = MagicMock(success=True)

        knowledge_agent = MagicMock()
        knowledge_agent.run.return_value = AgentResult(
            success=True,
            data=None,
            message="success"
        )

        orchestrator = Orchestrator(
            intent_agent=intent_agent,
            retrieval_agent=retrieval_agent,
            knowledge_agent=knowledge_agent
        )

        context = orchestrator._handle_conversation(AgentContext(user_input="测试"))

        assert context.execution_result is not None
        assert "不可用" in context.execution_result or "稍后" in context.execution_result

    def test_knowledge_agent_success(self):
        """KnowledgeAgent 成功时应设置 generator"""
        def mock_generator():
            yield {"type": "content", "content": "测试回复"}

        intent_agent = MagicMock()
        intent_agent.run.return_value = MagicMock(success=True)

        retrieval_agent = MagicMock()
        retrieval_agent.run.return_value = MagicMock(success=True)

        knowledge_agent = MagicMock()
        knowledge_agent.run.return_value = AgentResult(
            success=True,
            data=mock_generator(),
            message="knowledge_stream_ready"
        )

        orchestrator = Orchestrator(
            intent_agent=intent_agent,
            retrieval_agent=retrieval_agent,
            knowledge_agent=knowledge_agent
        )

        context = orchestrator._handle_conversation(AgentContext(user_input="测试"))

        assert context.execution_result is not None
        assert "knowledge" in context.step_history