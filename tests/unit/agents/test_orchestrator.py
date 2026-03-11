"""Orchestrator 单元测试"""
import sys
from unittest.mock import MagicMock, patch
import pytest

from src.agents.orchestrator import Orchestrator
from src.agents.context import AgentContext, IntentModel
from src.agents.models import AgentResult


class MockIntentResult:
    """用于测试的 Intent 结果 mock"""
    def __init__(self, need_clarify=False, intent_type="query"):
        self.need_clarify = need_clarify
        self.type = intent_type


def _create_intent_side_effect(intent_type="query", need_clarify=False, **kwargs):
    """创建 IntentAgent 的 side_effect 函数

    模拟真实的 IntentAgent 行为：设置 context.intent 并返回 AgentResult
    """
    def side_effect(context):
        context.intent = IntentModel(
            type=intent_type,
            need_clarify=need_clarify,
            **kwargs
        )
        return AgentResult(success=True, data=context.intent)
    return side_effect


class TestOrchestratorDependencyInjection:
    """测试 Orchestrator 依赖注入"""

    def test_orchestrator_dependency_injection(self):
        """测试通过依赖注入使用 mock agent"""
        # Inject mocks to test flow without real agents
        mock_intent = MagicMock()
        mock_intent.run.side_effect = _create_intent_side_effect(intent_type="query")

        mock_retrieval = MagicMock()
        mock_retrieval.run.return_value = AgentResult(success=True)

        mock_security = MagicMock()
        mock_security.run.return_value = AgentResult(success=True)

        mock_execution = MagicMock()
        mock_execution.run.return_value = AgentResult(success=True)

        orch = Orchestrator(
            intent_agent=mock_intent,
            retrieval_agent=mock_retrieval,
            security_agent=mock_security,
            execution_agent=mock_execution
        )

        context = orch.process("test input")

        mock_intent.run.assert_called_once()
        mock_retrieval.run.assert_called_once()
        mock_security.run.assert_called_once()
        mock_execution.run.assert_called_once()

    def test_orchestrator_intent_failure_stops_flow(self):
        """测试意图识别失败时停止流程"""
        mock_intent = MagicMock()
        mock_intent.run.return_value = AgentResult(success=False)

        mock_retrieval = MagicMock()
        mock_security = MagicMock()
        mock_execution = MagicMock()

        orch = Orchestrator(
            intent_agent=mock_intent,
            retrieval_agent=mock_retrieval,
            security_agent=mock_security,
            execution_agent=mock_execution
        )

        context = orch.process("test input")

        mock_intent.run.assert_called_once()
        mock_retrieval.run.assert_not_called()
        mock_security.run.assert_not_called()
        mock_execution.run.assert_not_called()
        assert context.step_history[-1] == "intent_failed"

    def test_orchestrator_need_clarify_stops_flow(self):
        """测试需要澄清时停止流程并设置 pending_clarification 标志"""
        mock_intent = MagicMock()
        mock_intent.run.side_effect = _create_intent_side_effect(
            intent_type="clarify",
            need_clarify=True
        )

        mock_retrieval = MagicMock()
        mock_security = MagicMock()
        mock_execution = MagicMock()

        orch = Orchestrator(
            intent_agent=mock_intent,
            retrieval_agent=mock_retrieval,
            security_agent=mock_security,
            execution_agent=mock_execution
        )

        context = orch.process("test input")

        mock_intent.run.assert_called_once()
        mock_retrieval.run.assert_not_called()
        mock_security.run.assert_not_called()
        mock_execution.run.assert_not_called()
        # 新逻辑：需要澄清时设置 pending_clarification 标志
        assert context.pending_clarification is True
        assert "intent" in context.step_history

    def test_orchestrator_security_failure_stops_flow(self):
        """测试安全检查失败时停止流程"""
        mock_intent = MagicMock()
        mock_intent.run.side_effect = _create_intent_side_effect(intent_type="query")

        mock_retrieval = MagicMock()
        mock_retrieval.run.return_value = AgentResult(success=True)

        mock_security = MagicMock()
        mock_security.run.return_value = AgentResult(success=False)

        mock_execution = MagicMock()

        orch = Orchestrator(
            intent_agent=mock_intent,
            retrieval_agent=mock_retrieval,
            security_agent=mock_security,
            execution_agent=mock_execution
        )

        context = orch.process("test input")

        mock_intent.run.assert_called_once()
        mock_retrieval.run.assert_called_once()
        mock_security.run.assert_called_once()
        mock_execution.run.assert_not_called()
        assert context.is_safe is None  # SecurityAgent 返回失败，is_safe 未设置

    def test_orchestrator_mutation_type_runs_preview(self):
        """测试 mutation 类型运行预览 agent"""
        mock_intent = MagicMock()
        mock_intent.run.side_effect = _create_intent_side_effect(intent_type="mutation")

        mock_retrieval = MagicMock()
        mock_retrieval.run.return_value = AgentResult(success=True)

        mock_security = MagicMock()
        mock_security.run.return_value = AgentResult(success=True)

        mock_preview = MagicMock()
        mock_preview.run.return_value = AgentResult(success=True)

        mock_execution = MagicMock()
        mock_execution.run.return_value = AgentResult(success=True)

        orch = Orchestrator(
            intent_agent=mock_intent,
            retrieval_agent=mock_retrieval,
            security_agent=mock_security,
            preview_agent=mock_preview,
            execution_agent=mock_execution
        )

        context = orch.process("delete user 123")

        mock_intent.run.assert_called_once()
        mock_retrieval.run.assert_called_once()
        mock_security.run.assert_called_once()
        mock_preview.run.assert_called_once()
        mock_execution.run.assert_called_once()

    def test_orchestrator_query_type_skips_preview(self):
        """测试 query 类型跳过预览 agent"""
        mock_intent = MagicMock()
        mock_intent.run.side_effect = _create_intent_side_effect(intent_type="query")

        mock_retrieval = MagicMock()
        mock_retrieval.run.return_value = AgentResult(success=True)

        mock_security = MagicMock()
        mock_security.run.return_value = AgentResult(success=True)

        mock_preview = MagicMock()

        mock_execution = MagicMock()
        mock_execution.run.return_value = AgentResult(success=True)

        orch = Orchestrator(
            intent_agent=mock_intent,
            retrieval_agent=mock_retrieval,
            security_agent=mock_security,
            preview_agent=mock_preview,
            execution_agent=mock_execution
        )

        context = orch.process("list all users")

        mock_intent.run.assert_called_once()
        mock_retrieval.run.assert_called_once()
        mock_security.run.assert_called_once()
        mock_preview.run.assert_not_called()
        mock_execution.run.assert_called_once()


class TestOrchestratorContextManagement:
    """测试 Orchestrator 上下文管理"""

    def test_orchestrator_creates_context(self):
        """测试 Orchestrator 创建正确的上下文"""
        mock_intent = MagicMock()
        mock_intent.run.side_effect = _create_intent_side_effect(intent_type="query")

        mock_retrieval = MagicMock()
        mock_retrieval.run.return_value = AgentResult(success=True)

        mock_security = MagicMock()
        mock_security.run.return_value = AgentResult(success=True)

        mock_execution = MagicMock()
        mock_execution.run.return_value = AgentResult(success=True)

        orch = Orchestrator(
            intent_agent=mock_intent,
            retrieval_agent=mock_retrieval,
            security_agent=mock_security,
            execution_agent=mock_execution
        )

        context = orch.process("test input")

        assert context.user_input == "test input"
        assert "intent" in context.step_history
        assert "retrieval" in context.step_history
        assert "security" in context.step_history
        assert "execution" in context.step_history

    def test_orchestrator_step_history_order(self):
        """测试步骤历史记录顺序正确"""
        mock_intent = MagicMock()
        mock_intent.run.side_effect = _create_intent_side_effect(intent_type="query")

        mock_retrieval = MagicMock()
        mock_retrieval.run.return_value = AgentResult(success=True)

        mock_security = MagicMock()
        mock_security.run.return_value = AgentResult(success=True)

        mock_execution = MagicMock()
        mock_execution.run.return_value = AgentResult(success=True)

        orch = Orchestrator(
            intent_agent=mock_intent,
            retrieval_agent=mock_retrieval,
            security_agent=mock_security,
            execution_agent=mock_execution
        )

        context = orch.process("test input")

        expected_steps = ["intent", "retrieval", "security", "execution"]
        assert context.step_history == expected_steps
