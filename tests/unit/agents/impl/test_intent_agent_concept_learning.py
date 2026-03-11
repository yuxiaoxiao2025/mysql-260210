import pytest
from unittest.mock import MagicMock
from src.agents.impl.intent_agent import IntentAgent
from src.agents.config import IntentAgentConfig
from src.agents.context import AgentContext
from src.dialogue.concept_recognizer import RecognizedConcept
from src.dialogue.question_generator import ClarificationQuestion


def test_intent_agent_init_with_concept_store():
    """测试IntentAgent可以接受concept_store参数"""
    mock_llm = MagicMock()
    mock_knowledge = MagicMock()
    mock_concept_store = MagicMock()

    config = IntentAgentConfig(name="intent")
    agent = IntentAgent(
        config=config,
        llm_client=mock_llm,
        knowledge_loader=mock_knowledge,
        concept_store=mock_concept_store
    )

    assert agent.concept_store is mock_concept_store
    assert hasattr(agent, 'concept_recognizer')
    assert hasattr(agent, 'question_generator')


def test_intent_agent_recognize_unknown_concept():
    """测试IntentAgent识别未知概念并生成澄清问题"""
    mock_llm = MagicMock()
    mock_knowledge = MagicMock()
    mock_concept_store = MagicMock()

    # Mock concept_recognizer返回未知概念
    config = IntentAgentConfig(name="intent")
    agent = IntentAgent(config, mock_llm, mock_knowledge, mock_concept_store)

    # Mock recognize方法 - 需要提供完整的 RecognizedConcept 字段
    unknown_concept = RecognizedConcept(
        term="ROI",
        position=(0, 3),
        context="查询ROI",
        matched_concept_id=None,
        needs_clarification=True,
        possible_meanings=[]
    )
    agent.concept_recognizer.recognize = MagicMock(return_value=[unknown_concept])

    # Mock question_generator
    question = ClarificationQuestion(
        concept_term="ROI",
        question="请问ROI具体指什么？",
        options=["投资回报率", "其他含义"],
        question_type="clarification"
    )
    agent.question_generator.generate_clarification_question = MagicMock(return_value=question)

    # Mock recognizer.recognize to return a proper mock object
    mock_recognized = MagicMock()
    mock_recognized.operation_id = "plate_query"
    mock_recognized.is_matched = True
    mock_recognized.confidence = 0.9
    mock_recognized.params = {}
    mock_recognized.missing_params = []
    mock_recognized.reasoning = ""
    mock_recognized.fallback_sql = None
    agent.recognizer.recognize = MagicMock(return_value=mock_recognized)

    # 执行
    context = AgentContext(user_input="查询ROI")
    result = agent.run(context)

    # 验证
    assert result.success is True
    assert context.intent.need_clarify is True
    assert context.intent.clarification_question == "请问ROI具体指什么？"
    assert "ROI" in context.intent.unrecognized_concepts


def test_intent_agent_learn_from_clarification():
    """测试IntentAgent从澄清回答中学习概念"""
    mock_llm = MagicMock()
    mock_knowledge = MagicMock()
    mock_concept_store = MagicMock()

    config = IntentAgentConfig(name="intent")
    agent = IntentAgent(config, mock_llm, mock_knowledge, mock_concept_store)

    # 模拟澄清对话历史
    context = AgentContext(
        user_input="投资回报率",
        chat_history=[
            {"role": "assistant", "content": "请问ROI具体指什么？"},
            {"role": "user", "content": "投资回报率"}
        ]
    )

    # Mock recognizer返回正常意图
    mock_recognized = MagicMock()
    mock_recognized.operation_id = "plate_query"
    mock_recognized.is_matched = True
    mock_recognized.confidence = 0.9
    mock_recognized.params = {}
    mock_recognized.missing_params = []
    mock_recognized.reasoning = ""
    mock_recognized.fallback_sql = None
    agent.recognizer.recognize = MagicMock(return_value=mock_recognized)

    # 执行
    result = agent.run(context)

    # 验证概念已学习
    mock_concept_store.add_concept.assert_called_once()
    call_args = mock_concept_store.add_concept.call_args[0][0]
    assert "ROI" in call_args.user_terms
    assert "投资回报率" in call_args.description

    # 验证意图识别成功
    assert result.success is True
    assert context.intent.need_clarify is False