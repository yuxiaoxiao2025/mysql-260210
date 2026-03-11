"""Orchestrator 路由增强测试 - chat_history 参数支持"""
import pytest
from unittest.mock import MagicMock

from src.agents.orchestrator import Orchestrator
from src.agents.context import AgentContext, IntentModel


class TestOrchestratorChatHistory:
    """测试 Orchestrator 接受 chat_history 参数"""

    def test_orchestrator_process_with_chat_history(self):
        """测试 Orchestrator 接受 chat_history 参数"""
        # Mock agents
        mock_intent = MagicMock()
        mock_intent.run.return_value.success = True

        mock_retrieval = MagicMock()
        mock_retrieval.run.return_value.success = True

        mock_security = MagicMock()
        mock_security.run.return_value.success = True

        mock_execution = MagicMock()
        mock_execution.run.return_value.success = True

        orch = Orchestrator(
            intent_agent=mock_intent,
            retrieval_agent=mock_retrieval,
            security_agent=mock_security,
            execution_agent=mock_execution
        )

        chat_history = [
            {"role": "user", "content": "之前的问题"},
            {"role": "assistant", "content": "之前的回答"}
        ]

        context = orch.process("新问题", chat_history=chat_history)

        # 验证 chat_history 被传递到 context
        assert len(context.chat_history) == 2
        assert context.chat_history[0]["role"] == "user"
        assert context.chat_history[0]["content"] == "之前的问题"
        assert context.chat_history[1]["role"] == "assistant"
        assert context.chat_history[1]["content"] == "之前的回答"

    def test_orchestrator_process_with_empty_chat_history(self):
        """测试 Orchestrator 处理空 chat_history"""
        mock_intent = MagicMock()
        mock_intent.run.return_value.success = True

        mock_retrieval = MagicMock()
        mock_retrieval.run.return_value.success = True

        mock_security = MagicMock()
        mock_security.run.return_value.success = True

        mock_execution = MagicMock()
        mock_execution.run.return_value.success = True

        orch = Orchestrator(
            intent_agent=mock_intent,
            retrieval_agent=mock_retrieval,
            security_agent=mock_security,
            execution_agent=mock_execution
        )

        context = orch.process("新问题", chat_history=[])

        # 验证空 chat_history
        assert len(context.chat_history) == 0

    def test_orchestrator_process_without_chat_history(self):
        """测试 Orchestrator 不传 chat_history 时默认为空列表"""
        mock_intent = MagicMock()
        mock_intent.run.return_value.success = True

        mock_retrieval = MagicMock()
        mock_retrieval.run.return_value.success = True

        mock_security = MagicMock()
        mock_security.run.return_value.success = True

        mock_execution = MagicMock()
        mock_execution.run.return_value.success = True

        orch = Orchestrator(
            intent_agent=mock_intent,
            retrieval_agent=mock_retrieval,
            security_agent=mock_security,
            execution_agent=mock_execution
        )

        context = orch.process("新问题")

        # 验证默认为空列表
        assert context.chat_history == []

    def test_orchestrator_chat_history_passed_to_intent_agent(self):
        """测试 chat_history 被传递给 IntentAgent"""
        mock_intent = MagicMock()
        mock_intent.run.return_value.success = True

        mock_retrieval = MagicMock()
        mock_retrieval.run.return_value.success = True

        mock_security = MagicMock()
        mock_security.run.return_value.success = True

        mock_execution = MagicMock()
        mock_execution.run.return_value.success = True

        orch = Orchestrator(
            intent_agent=mock_intent,
            retrieval_agent=mock_retrieval,
            security_agent=mock_security,
            execution_agent=mock_execution
        )

        chat_history = [
            {"role": "user", "content": "查询车牌ABC"},
            {"role": "assistant", "content": "找到了车辆ABC..."}
        ]

        orch.process("它的状态是什么", chat_history=chat_history)

        # 验证 IntentAgent.run 被调用，且 context 包含 chat_history
        mock_intent.run.assert_called_once()
        called_context = mock_intent.run.call_args[0][0]
        assert called_context.chat_history == chat_history
