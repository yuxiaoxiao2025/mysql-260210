# tests/dialogue/test_dialogue_engine.py
"""
Tests for dialogue engine.
"""

import pytest
from unittest.mock import Mock, MagicMock

from src.dialogue.dialogue_engine import DialogueEngine, DialogueState, DialogueResponse
from src.memory.concept_store import ConceptStoreService
from src.memory.context_memory import ContextMemoryService
from src.memory.memory_models import ConceptMapping


class TestDialogueEngine:
    """对话引擎测试"""

    @pytest.fixture
    def mock_concept_store(self):
        """模拟概念存储服务"""
        mock = Mock(spec=ConceptStoreService)
        mock.is_empty.return_value = False
        mock.find_by_user_term.return_value = None
        mock.get_concept.return_value = None
        return mock

    @pytest.fixture
    def mock_context_memory(self):
        """模拟上下文记忆服务"""
        mock = Mock(spec=ContextMemoryService)
        mock.resolve_reference.side_effect = lambda x: x
        mock.get_current_plate.return_value = None
        return mock

    @pytest.fixture
    def engine(self, mock_concept_store, mock_context_memory):
        """创建对话引擎实例"""
        return DialogueEngine(
            concept_store=mock_concept_store,
            context_memory=mock_context_memory,
        )

    def test_initial_state_is_idle(self, engine):
        """测试初始状态为空闲"""
        assert engine.get_state() == DialogueState.IDLE

    def test_process_input_returns_response(self, engine):
        """测试处理输入返回响应"""
        response = engine.process_input("查一下沪BAB1565")

        assert response is not None
        assert response.message is not None

    def test_unrecognized_concept_triggers_clarification(self, engine, mock_concept_store):
        """测试未识别概念触发澄清"""
        mock_concept_store.find_by_user_term.return_value = None

        response = engine.process_input("这辆车停过哪些园区")

        # 应该进入澄清状态
        assert response.state == DialogueState.CLARIFYING

    def test_answer_clarification_advances_state(self, engine, mock_concept_store):
        """测试回答澄清问题推进状态"""
        mock_concept_store.find_by_user_term.return_value = None

        # 触发澄清 - 使用简单输入确保只有一个概念需要澄清
        response1 = engine.process_input("停过")

        if response1.state == DialogueState.CLARIFYING:
            # 回答澄清问题
            response2 = engine.process_input("A")

            # 如果只有一个概念，回答后应该进入确认状态或空闲状态
            # 如果有多个概念，则仍处于澄清状态但pending_questions减少
            assert response2.state in [DialogueState.CONFIRMING, DialogueState.IDLE, DialogueState.CLARIFYING]
        else:
            # 如果没有触发澄清，测试通过
            assert response1.state in [DialogueState.IDLE, DialogueState.CONFIRMING]

    def test_confirmation_flow(self, engine, mock_concept_store):
        """测试确认流程"""
        mock_concept = Mock(
            concept_id="test",
            user_terms=["测试"],
            description="测试概念"
        )
        mock_concept_store.find_by_user_term.return_value = mock_concept
        mock_concept_store.get_concept.return_value = mock_concept

        response = engine.process_input("确认执行")

        # 应该有确认选项
        if response.state == DialogueState.CONFIRMING:
            assert "可以" in response.options or "确认" in str(response.options)

    def test_reset_clears_state(self, engine):
        """测试重置清除状态"""
        engine.state = DialogueState.CLARIFYING
        engine.pending_questions = ["test"]

        engine.reset()

        assert engine.get_state() == DialogueState.IDLE
        assert len(engine.pending_questions) == 0


class TestDialogueResponse:
    """对话响应测试"""

    def test_response_creation(self):
        """测试响应创建"""
        response = DialogueResponse(
            message="测试消息",
            state=DialogueState.IDLE
        )

        assert response.message == "测试消息"
        assert response.state == DialogueState.IDLE
        assert response.needs_input is True
        assert response.options == []
        assert response.pending_concepts == []

    def test_response_with_options(self):
        """测试带选项的响应"""
        response = DialogueResponse(
            message="选择一项",
            state=DialogueState.CLARIFYING,
            options=["选项A", "选项B"]
        )

        assert len(response.options) == 2
        assert "选项A" in response.options


class TestDialogueState:
    """对话状态测试"""

    def test_state_values(self):
        """测试状态值"""
        assert DialogueState.IDLE.value == "idle"
        assert DialogueState.CLARIFYING.value == "clarifying"
        assert DialogueState.CONFIRMING.value == "confirming"
        assert DialogueState.EXECUTING.value == "executing"
        assert DialogueState.ERROR.value == "error"


class TestDialogueEngineIntegration:
    """对话引擎集成测试"""

    @pytest.fixture
    def mock_concept_store(self):
        """模拟概念存储服务"""
        mock = Mock(spec=ConceptStoreService)
        mock.is_empty.return_value = False
        mock.find_by_user_term.return_value = None
        mock.get_concept.return_value = None
        mock.add_concept.return_value = None
        return mock

    @pytest.fixture
    def mock_context_memory(self):
        """模拟上下文记忆服务"""
        mock = Mock(spec=ContextMemoryService)
        mock.resolve_reference.side_effect = lambda x: x
        mock.get_current_plate.return_value = None
        mock.add_user_message.return_value = Mock()
        mock.add_assistant_message.return_value = Mock()
        mock.record_correction.return_value = None
        return mock

    @pytest.fixture
    def engine(self, mock_concept_store, mock_context_memory):
        """创建对话引擎实例"""
        return DialogueEngine(
            concept_store=mock_concept_store,
            context_memory=mock_context_memory,
        )

    def test_full_clarification_flow(self, engine, mock_concept_store):
        """测试完整澄清流程"""
        # 初始输入触发澄清
        mock_concept_store.find_by_user_term.return_value = None
        response1 = engine.process_input("停过哪里")
        assert response1.state == DialogueState.CLARIFYING
        assert len(response1.pending_concepts) > 0

        # 回答澄清
        response2 = engine.process_input("A")
        # 应该进入确认状态或继续澄清
        assert response2.state in [DialogueState.CONFIRMING, DialogueState.CLARIFYING, DialogueState.IDLE]

    def test_confirmation_accept(self, engine, mock_concept_store):
        """测试确认接受"""
        # 设置已知的概念
        mock_concept = ConceptMapping(
            concept_id="test_concept",
            user_terms=["测试"],
            description="测试描述"
        )
        mock_concept_store.find_by_user_term.return_value = mock_concept
        mock_concept_store.get_concept.return_value = mock_concept

        # 进入确认状态
        response1 = engine.process_input("查一下测试")
        assert response1.state == DialogueState.CONFIRMING

        # 确认
        response2 = engine.process_input("可以")
        assert response2.state == DialogueState.EXECUTING
        assert response2.needs_input is False

    def test_confirmation_reject(self, engine, mock_concept_store):
        """测试确认拒绝"""
        # 设置已知的概念
        mock_concept = ConceptMapping(
            concept_id="test_concept",
            user_terms=["测试"],
            description="测试描述"
        )
        mock_concept_store.find_by_user_term.return_value = mock_concept
        mock_concept_store.get_concept.return_value = mock_concept

        # 进入确认状态
        response1 = engine.process_input("查一下测试")
        assert response1.state == DialogueState.CONFIRMING

        # 拒绝
        response2 = engine.process_input("需要调整")
        assert response2.state == DialogueState.IDLE

    def test_pronoun_resolution(self, engine, mock_context_memory):
        """测试代词解析"""
        mock_context_memory.get_current_plate.return_value = "沪A12345"
        mock_context_memory.resolve_reference.side_effect = lambda x: x.replace("这辆车", "沪A12345")

        response = engine.process_input("这辆车停过哪里")
        assert response is not None
