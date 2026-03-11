"""Orchestrator 单元测试"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from unittest.mock import MagicMock, patch
import pytest

from src.agents.orchestrator import Orchestrator
from src.agents.context import AgentContext, IntentModel


class MockIntentResult:
    """用于测试的 Intent 结果 mock"""
    def __init__(self, need_clarify=False, intent_type="query"):
        self.need_clarify = need_clarify
        self.type = intent_type


class TestOrchestratorDependencyInjection:
    """测试 Orchestrator 依赖注入"""

    def test_orchestrator_dependency_injection(self):
        """测试通过依赖注入使用 mock agent"""
        # Inject mocks to test flow without real agents
        mock_intent = MagicMock()
        mock_intent.run.return_value.success = True
        # 设置嵌套属性链
        mock_intent.run.return_value.data = MagicMock()
        mock_intent.run.return_value.data.need_clarify = False
        mock_intent.run.return_value.data.type = "query"

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

        context = orch.process("test input")

        mock_intent.run.assert_called_once()
        mock_retrieval.run.assert_called_once()
        mock_security.run.assert_called_once()
        mock_execution.run.assert_called_once()

    def test_orchestrator_intent_failure_stops_flow(self):
        """测试意图识别失败时停止流程"""
        mock_intent = MagicMock()
        mock_intent.run.return_value.success = False

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
        """测试需要澄清时停止流程"""
        # 创建一个真正的 IntentModel 实例并注入到上下文中
        mock_intent = MagicMock()
        mock_intent.run.return_value.success = True

        mock_retrieval = MagicMock()
        mock_security = MagicMock()
        mock_execution = MagicMock()

        orch = Orchestrator(
            intent_agent=mock_intent,
            retrieval_agent=mock_retrieval,
            security_agent=mock_security,
            execution_agent=mock_execution
        )

        # 通过模拟 IntentAgent 在 run 中设置 context.intent.need_clarify = True
        def side_effect_set_intent(context):
            from src.agents.context import IntentModel
            context.intent = IntentModel(
                type="clarify",
                need_clarify=True
            )
            return MagicMock(success=True)

        mock_intent.run.side_effect = side_effect_set_intent

        context = orch.process("test input")

        mock_intent.run.assert_called_once()
        mock_retrieval.run.assert_not_called()
        mock_security.run.assert_not_called()
        mock_execution.run.assert_not_called()
        assert context.step_history[-1] == "intent_failed"

    def test_orchestrator_security_failure_stops_flow(self):
        """测试安全检查失败时停止流程"""
        mock_intent = MagicMock()
        mock_intent.run.return_value.success = True

        mock_retrieval = MagicMock()
        mock_retrieval.run.return_value.success = True

        mock_security = MagicMock()
        mock_security.run.return_value.success = False

        mock_execution = MagicMock()

        orch = Orchestrator(
            intent_agent=mock_intent,
            retrieval_agent=mock_retrieval,
            security_agent=mock_security,
            execution_agent=mock_execution
        )

        # 通过 side_effect 设置正确的 intent，并设置 is_safe
        def side_effect_set_intent(context):
            from src.agents.context import IntentModel
            context.intent = IntentModel(
                type="query",
                need_clarify=False
            )
            return MagicMock(success=True)

        def side_effect_set_security(context):
            context.is_safe = False
            return MagicMock(success=False)

        mock_intent.run.side_effect = side_effect_set_intent
        mock_security.run.side_effect = side_effect_set_security

        context = orch.process("test input")

        mock_intent.run.assert_called_once()
        mock_retrieval.run.assert_called_once()
        mock_security.run.assert_called_once()
        mock_execution.run.assert_not_called()
        assert context.is_safe is False

    def test_orchestrator_mutation_type_runs_preview(self):
        """测试 mutation 类型运行预览 agent"""
        mock_intent = MagicMock()
        mock_intent.run.return_value.success = True

        mock_retrieval = MagicMock()
        mock_retrieval.run.return_value.success = True

        mock_security = MagicMock()
        mock_security.run.return_value.success = True

        mock_preview = MagicMock()
        mock_preview.run.return_value.success = True

        mock_execution = MagicMock()
        mock_execution.run.return_value.success = True

        orch = Orchestrator(
            intent_agent=mock_intent,
            retrieval_agent=mock_retrieval,
            security_agent=mock_security,
            preview_agent=mock_preview,
            execution_agent=mock_execution
        )

        # 通过 side_effect 设置 mutation intent
        def side_effect_set_intent(context):
            from src.agents.context import IntentModel
            context.intent = IntentModel(
                type="mutation",
                need_clarify=False
            )
            return MagicMock(success=True)

        mock_intent.run.side_effect = side_effect_set_intent

        context = orch.process("delete user 123")

        mock_intent.run.assert_called_once()
        mock_retrieval.run.assert_called_once()
        mock_security.run.assert_called_once()
        mock_preview.run.assert_called_once()
        mock_execution.run.assert_called_once()

    def test_orchestrator_query_type_skips_preview(self):
        """测试 query 类型跳过预览 agent"""
        mock_intent = MagicMock()
        mock_intent.run.return_value.success = True
        # 设置嵌套属性链
        mock_intent.run.return_value.data = MagicMock()
        mock_intent.run.return_value.data.need_clarify = False
        mock_intent.run.return_value.data.type = "query"

        mock_retrieval = MagicMock()
        mock_retrieval.run.return_value.success = True

        mock_security = MagicMock()
        mock_security.run.return_value.success = True

        mock_preview = MagicMock()

        mock_execution = MagicMock()
        mock_execution.run.return_value.success = True

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
        mock_intent.run.return_value.success = True
        # 设置嵌套属性链
        mock_intent.run.return_value.data = MagicMock()
        mock_intent.run.return_value.data.need_clarify = False
        mock_intent.run.return_value.data.type = "query"

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

        context = orch.process("test input")

        assert context.user_input == "test input"
        assert "intent" in context.step_history
        assert "retrieval" in context.step_history
        assert "security" in context.step_history
        assert "execution" in context.step_history

    def test_orchestrator_step_history_order(self):
        """测试步骤历史记录顺序正确"""
        mock_intent = MagicMock()
        mock_intent.run.return_value.success = True
        # 设置嵌套属性链
        mock_intent.run.return_value.data = MagicMock()
        mock_intent.run.return_value.data.need_clarify = False
        mock_intent.run.return_value.data.type = "query"

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

        context = orch.process("test input")

        expected_steps = ["intent", "retrieval", "security", "execution"]
        assert context.step_history == expected_steps
