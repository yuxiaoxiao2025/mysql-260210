"""
Tests for startup wizard.
"""

import pytest
from unittest.mock import Mock, MagicMock

from src.dialogue.startup_wizard import StartupWizard, WizardState
from src.memory.concept_store import ConceptStoreService


class TestStartupWizard:
    """启动向导测试"""

    @pytest.fixture
    def mock_concept_store(self):
        """模拟概念存储服务"""
        mock = Mock(spec=ConceptStoreService)
        mock.is_empty.return_value = True
        mock.find_by_user_term.return_value = None
        return mock

    @pytest.fixture
    def wizard(self, mock_concept_store):
        """创建向导实例"""
        return StartupWizard(concept_store=mock_concept_store)

    def test_should_start_when_empty(self, wizard, mock_concept_store):
        """测试空知识库时应该启动向导"""
        mock_concept_store.is_empty.return_value = True
        assert wizard.should_start() is True

    def test_should_not_start_when_not_empty(self, wizard, mock_concept_store):
        """测试非空知识库时不应该启动向导"""
        mock_concept_store.is_empty.return_value = False
        assert wizard.should_start() is False

    def test_start_returns_first_question(self, wizard):
        """测试启动返回第一个问题"""
        question = wizard.start()

        assert question is not None
        assert wizard.state == WizardState.IN_PROGRESS

    def test_answer_advances_to_next_question(self, wizard):
        """测试回答后进入下一个问题"""
        wizard.start()
        first_question = wizard.get_current_question()

        next_question = wizard.answer("测试答案")

        assert wizard.progress.current_question == 1

    def test_completion_after_all_answers(self, wizard):
        """测试回答所有问题后完成"""
        wizard.start()
        wizard.progress.total_questions = 2
        wizard.questions = wizard.questions[:2]

        wizard.answer("答案1")
        wizard.answer("答案2")

        assert wizard.state == WizardState.COMPLETED

    def test_get_welcome_message(self, wizard):
        """测试获取欢迎消息"""
        message = wizard.get_welcome_message()

        assert "你好" in message
        assert "停车数据库助手" in message

    def test_get_completion_message(self, wizard):
        """测试获取完成消息"""
        message = wizard.get_completion_message()

        assert "了解了" in message or "完成" in message or "好的" in message
