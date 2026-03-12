# tests/integration/test_dialogue_orchestrator_integration.py
"""
集成测试：对话引擎与Orchestrator集成

测试完整流程：
1. 完整对话流程（chat -> KnowledgeAgent）
2. 概念学习流程（clarify -> learn -> continue）
3. 业务操作流程（query -> retrieval -> security -> execution）
"""
import pytest
import types
from unittest.mock import MagicMock

from src.agents.orchestrator import Orchestrator
from src.agents.context import AgentContext, IntentModel
from src.agents.models import AgentResult


@pytest.fixture
def orchestrator_with_mocks():
    """创建带mock的Orchestrator用于集成测试"""
    mock_intent = MagicMock()
    mock_retrieval = MagicMock()
    mock_knowledge = MagicMock()
    mock_security = MagicMock()
    mock_preview = MagicMock()
    mock_execution = MagicMock()

    # 默认返回成功
    mock_intent.run.return_value = AgentResult(success=True)
    mock_retrieval.run.return_value = AgentResult(success=True)
    mock_knowledge.run.return_value = AgentResult(success=True)
    mock_security.run.return_value = AgentResult(success=True)
    mock_preview.run.return_value = AgentResult(success=True)
    mock_execution.run.return_value = AgentResult(success=True)

    orch = Orchestrator(
        intent_agent=mock_intent,
        retrieval_agent=mock_retrieval,
        knowledge_agent=mock_knowledge,
        security_agent=mock_security,
        preview_agent=mock_preview,
        execution_agent=mock_execution
    )

    return orch, mock_intent, mock_retrieval, mock_knowledge, mock_security, mock_preview, mock_execution


class TestFullConversationFlow:
    """测试完整对话流程"""

    def test_full_conversation_flow(self, orchestrator_with_mocks):
        """测试完整对话流程：普通对话 -> 知识问答"""
        orch, mock_intent, mock_retrieval, mock_knowledge, mock_security, mock_preview, mock_execution = orchestrator_with_mocks

        # Mock intent返回chat类型
        def intent_side_effect(context):
            context.intent = IntentModel(type="chat", confidence=0.95, need_clarify=False)
            return AgentResult(success=True, data=context.intent)

        mock_intent.run.side_effect = intent_side_effect

        # Mock knowledge返回generator
        def mock_generator():
            yield {"type": "content", "content": "你好！"}

        mock_knowledge.run.return_value = AgentResult(
            success=True,
            data=mock_generator()
        )

        context = orch.process("你好")

        assert "intent" in context.step_history
        assert "retrieval" in context.step_history
        assert "knowledge" in context.step_history
        assert isinstance(context.execution_result, types.GeneratorType)

        # 消费generator
        chunks = list(context.execution_result)
        assert len(chunks) > 0


class TestConceptLearningFlow:
    """测试概念学习流程"""

    def test_concept_learning_flow_trigger_clarification(self, orchestrator_with_mocks):
        """测试概念学习流程：触发澄清"""
        orch, mock_intent, mock_retrieval, mock_knowledge, mock_security, mock_preview, mock_execution = orchestrator_with_mocks

        # Mock intent返回需要澄清
        def intent_side_effect(context):
            context.intent = IntentModel(
                type="clarify",
                confidence=0.0,
                need_clarify=True,
                clarification_question="请问ROI具体指什么？",
                unrecognized_concepts=["ROI"]
            )
            return AgentResult(success=True, data=context.intent)

        mock_intent.run.side_effect = intent_side_effect

        context = orch.process("查询ROI")

        assert context.pending_clarification is True
        assert context.intent is not None
        assert "ROI" in context.intent.unrecognized_concepts

    def test_concept_learning_flow_continue_after_clarification(self, orchestrator_with_mocks):
        """测试概念学习流程：澄清后继续"""
        orch, mock_intent, mock_retrieval, mock_knowledge, mock_security, mock_preview, mock_execution = orchestrator_with_mocks

        chat_history = [
            {"role": "assistant", "content": "请问ROI具体指什么？"},
            {"role": "user", "content": "投资回报率"}
        ]

        # Mock intent返回query类型（澄清后）
        def intent_side_effect(context):
            context.intent = IntentModel(
                type="query",
                confidence=0.9,
                need_clarify=False,
                operation_id="plate_query"
            )
            return AgentResult(success=True, data=context.intent)

        mock_intent.run.side_effect = intent_side_effect

        context = orch.process("投资回报率", chat_history=chat_history)

        # 验证继续执行业务流程
        assert context.pending_clarification is False
        assert "intent" in context.step_history
        assert "retrieval" in context.step_history
        assert "security" in context.step_history
        assert "execution" in context.step_history


class TestBusinessOperationFlow:
    """测试业务操作流程"""

    def test_business_operation_query_flow(self, orchestrator_with_mocks):
        """测试业务操作流程：query -> retrieval -> security -> execution"""
        orch, mock_intent, mock_retrieval, mock_knowledge, mock_security, mock_preview, mock_execution = orchestrator_with_mocks

        # Mock intent返回query类型
        def intent_side_effect(context):
            context.intent = IntentModel(
                type="query",
                confidence=0.95,
                need_clarify=False,
                operation_id="plate_query",
                params={"plate": "沪A12345"}
            )
            return AgentResult(success=True, data=context.intent)

        mock_intent.run.side_effect = intent_side_effect

        context = orch.process("查询车牌沪A12345")

        # 验证完整业务流程
        assert "intent" in context.step_history
        assert "retrieval" in context.step_history
        assert "security" in context.step_history
        assert "execution" in context.step_history

    def test_business_operation_mutation_flow(self, orchestrator_with_mocks):
        """测试业务操作流程：mutation包含preview"""
        orch, mock_intent, mock_retrieval, mock_knowledge, mock_security, mock_preview, mock_execution = orchestrator_with_mocks

        # Mock intent返回mutation类型
        def intent_side_effect(context):
            context.intent = IntentModel(
                type="mutation",
                confidence=0.95,
                need_clarify=False,
                operation_id="plate_update",
                params={"plate": "沪A12345", "status": "已年检"}
            )
            return AgentResult(success=True, data=context.intent)

        mock_intent.run.side_effect = intent_side_effect

        context = orch.process("更新车牌沪A12345状态为已年检")

        # 验证mutation流程（包含preview）
        assert "intent" in context.step_history
        assert "retrieval" in context.step_history
        assert "security" in context.step_history
        assert "preview" in context.step_history
        assert "execution" in context.step_history


class TestKnowledgeQAFlow:
    """测试知识问答流程"""

    def test_knowledge_qa_flow(self, orchestrator_with_mocks):
        """测试知识问答流程：qa -> retrieval -> knowledge"""
        orch, mock_intent, mock_retrieval, mock_knowledge, mock_security, mock_preview, mock_execution = orchestrator_with_mocks

        # Mock intent返回qa类型
        def intent_side_effect(context):
            context.intent = IntentModel(type="qa", confidence=0.95, need_clarify=False)
            return AgentResult(success=True, data=context.intent)

        mock_intent.run.side_effect = intent_side_effect

        # Mock KnowledgeAgent返回generator
        def mock_generator():
            yield {"type": "thinking", "content": "思考中..."}
            yield {"type": "content", "content": "根据数据库结构..."}

        mock_knowledge.run.return_value = AgentResult(
            success=True,
            data=mock_generator()
        )

        context = orch.process("数据库有哪些表？")

        # 验证知识问答流程
        assert "intent" in context.step_history
        assert "retrieval" in context.step_history
        assert "knowledge" in context.step_history
        assert isinstance(context.execution_result, types.GeneratorType)
