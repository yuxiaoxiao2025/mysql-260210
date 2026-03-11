"""Orchestrator 路由增强测试 - chat_history 参数支持"""
import pytest
import types
from unittest.mock import MagicMock

from src.agents.orchestrator import Orchestrator
from src.agents.context import AgentContext, IntentModel
from src.agents.models import AgentResult


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


class TestOrchestratorRouting:
    """测试 Orchestrator 智能路由逻辑"""

    def test_orchestrator_route_chat_to_knowledge_agent(self):
        """测试Orchestrator将chat意图路由到KnowledgeAgent"""
        # Mock agents
        mock_intent = MagicMock()
        mock_retrieval = MagicMock()
        mock_knowledge = MagicMock()

        # Mock intent返回chat类型 - 使用side_effect设置context.intent
        def intent_side_effect(context):
            context.intent = IntentModel(type="chat", confidence=0.95, need_clarify=False)
            return AgentResult(success=True, data=context.intent)

        mock_intent.run.side_effect = intent_side_effect

        # Mock retrieval返回成功
        mock_retrieval.run.return_value = AgentResult(success=True)

        # Mock knowledge返回generator
        def mock_generator():
            yield {"type": "content", "content": "你好"}

        mock_knowledge.run.return_value = AgentResult(
            success=True,
            data=mock_generator()
        )

        orch = Orchestrator(
            intent_agent=mock_intent,
            retrieval_agent=mock_retrieval,
            knowledge_agent=mock_knowledge
        )

        context = orch.process("你好")

        # 验证路由
        assert "knowledge" in context.step_history
        assert isinstance(context.execution_result, types.GeneratorType)

    def test_orchestrator_route_query_to_business_flow(self):
        """测试Orchestrator将query意图路由到业务流程"""
        # Mock agents
        mock_intent = MagicMock()
        mock_retrieval = MagicMock()
        mock_security = MagicMock()
        mock_execution = MagicMock()

        # Mock intent返回query类型
        def intent_side_effect(context):
            context.intent = IntentModel(
                type="query",
                confidence=0.95,
                need_clarify=False,
                operation_id="plate_query"
            )
            return AgentResult(success=True, data=context.intent)

        mock_intent.run.side_effect = intent_side_effect

        mock_retrieval.run.return_value = AgentResult(success=True)
        mock_security.run.return_value = AgentResult(success=True)
        mock_execution.run.return_value = AgentResult(success=True)

        orch = Orchestrator(
            intent_agent=mock_intent,
            retrieval_agent=mock_retrieval,
            security_agent=mock_security,
            execution_agent=mock_execution
        )

        context = orch.process("查询车牌")

        # 验证完整业务流程
        assert "intent" in context.step_history
        assert "retrieval" in context.step_history
        assert "security" in context.step_history
        assert "execution" in context.step_history

    def test_orchestrator_route_qa_to_knowledge_agent(self):
        """测试Orchestrator将qa意图路由到KnowledgeAgent"""
        # Mock agents
        mock_intent = MagicMock()
        mock_retrieval = MagicMock()
        mock_knowledge = MagicMock()

        # Mock intent返回qa类型
        def intent_side_effect(context):
            context.intent = IntentModel(type="qa", confidence=0.90, need_clarify=False)
            return AgentResult(success=True, data=context.intent)

        mock_intent.run.side_effect = intent_side_effect

        mock_retrieval.run.return_value = AgentResult(success=True)

        # Mock knowledge返回generator
        def mock_generator():
            yield {"type": "content", "content": "这是知识问答的答案"}

        mock_knowledge.run.return_value = AgentResult(
            success=True,
            data=mock_generator()
        )

        orch = Orchestrator(
            intent_agent=mock_intent,
            retrieval_agent=mock_retrieval,
            knowledge_agent=mock_knowledge
        )

        context = orch.process("什么是数据库索引？")

        # 验证路由到知识问答流程
        assert "knowledge" in context.step_history
        assert isinstance(context.execution_result, types.GeneratorType)

    def test_orchestrator_sets_pending_clarification_flag(self):
        """测试Orchestrator在需要澄清时设置pending_clarification标志"""
        # Mock agents
        mock_intent = MagicMock()
        mock_retrieval = MagicMock()

        # Mock intent返回需要澄清的意图
        def intent_side_effect(context):
            context.intent = IntentModel(
                type="query",
                confidence=0.60,
                need_clarify=True,
                clarification_question="您是要查询车牌还是驾驶员信息？"
            )
            return AgentResult(success=True, data=context.intent)

        mock_intent.run.side_effect = intent_side_effect

        orch = Orchestrator(
            intent_agent=mock_intent,
            retrieval_agent=mock_retrieval
        )

        context = orch.process("查询")

        # 验证澄清标志被设置
        assert context.pending_clarification is True
