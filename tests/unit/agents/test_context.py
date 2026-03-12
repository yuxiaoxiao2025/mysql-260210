"""测试 AgentContext 和 IntentModel 的新增字段"""
import pytest
from src.agents.context import AgentContext, IntentModel
from src.memory.memory_models import ConceptMapping


class TestAgentContextChatHistory:
    """测试 AgentContext 支持 chat_history"""

    def test_agent_context_chat_history(self):
        """测试AgentContext支持chat_history"""
        context = AgentContext(
            user_input="你好",
            chat_history=[
                {"role": "user", "content": "之前的问题"},
                {"role": "assistant", "content": "之前的回答"}
            ]
        )
        assert len(context.chat_history) == 2
        assert context.chat_history[0]["role"] == "user"

    def test_agent_context_pending_clarification(self):
        """测试AgentContext支持pending_clarification标志"""
        context = AgentContext(user_input="查询ROI")
        assert context.pending_clarification is False

        context.pending_clarification = True
        assert context.pending_clarification is True

    def test_agent_context_learned_concepts(self):
        """测试AgentContext支持learned_concepts列表"""
        context = AgentContext(user_input="测试")
        assert context.learned_concepts == []

        concept = ConceptMapping(
            concept_id="test_concept",
            user_terms=["ROI"],
            database_mapping={"meaning": "投资回报率"},
            description="投资回报率"
        )
        context.learned_concepts.append(concept)
        assert len(context.learned_concepts) == 1


class TestIntentModelClarificationFields:
    """测试 IntentModel 支持澄清相关字段"""

    def test_intent_model_clarification_fields(self):
        """测试IntentModel支持澄清相关字段"""
        intent = IntentModel(
            type="query",
            confidence=0.5,
            need_clarify=True,
            clarification_question="请问ROI具体指什么？",
            unrecognized_concepts=["ROI"]
        )

        assert intent.need_clarify is True
        assert intent.clarification_question == "请问ROI具体指什么？"
        assert "ROI" in intent.unrecognized_concepts
        assert len(intent.unrecognized_concepts) == 1

    def test_intent_model_default_values(self):
        """测试IntentModel澄清字段的默认值"""
        intent = IntentModel(type="query", confidence=0.9)
        
        assert intent.need_clarify is False
        assert intent.clarification_question is None
        assert intent.unrecognized_concepts == []

    def test_intent_model_clarify_type(self):
        """测试IntentModel支持clarify类型"""
        intent = IntentModel(
            type="clarify",
            confidence=0.0,
            need_clarify=True,
            clarification_question="请澄清您的问题",
            unrecognized_concepts=["未知术语"]
        )
        
        assert intent.type == "clarify"
        assert intent.need_clarify is True
