"""
Tests for question generator.
"""

import pytest

from src.dialogue.question_generator import QuestionGenerator, ClarificationQuestion
from src.dialogue.concept_recognizer import RecognizedConcept


class TestQuestionGenerator:
    """问题生成器测试"""

    @pytest.fixture
    def generator(self):
        """创建生成器实例"""
        return QuestionGenerator()

    def test_generate_clarification_with_options(self, generator):
        """测试生成带选项的澄清问题"""
        concept = RecognizedConcept(
            term="停过",
            position=(0, 2),
            context="停过哪些园区",
            possible_meanings=["进出场记录", "绑定关系"]
        )

        question = generator.generate_clarification_question(concept)

        assert "停过" in question.question
        assert len(question.options) > 0
        assert question.question_type == "clarification"

    def test_generate_open_question(self, generator):
        """测试生成开放问题"""
        concept = RecognizedConcept(
            term="投诉",
            position=(0, 2),
            context="投诉过吗",
            possible_meanings=[]
        )

        question = generator.generate_clarification_question(concept)

        assert "投诉" in question.question
        assert question.question_type == "clarification"

    def test_generate_confirmation_question(self, generator):
        """测试生成确认问题"""
        question = generator.generate_confirmation_question(
            "查询沪BAB1565在所有园区的进出场记录"
        )

        assert "查询沪BAB1565" in question.question
        assert "可以吗" in question.question
        assert question.question_type == "confirmation"

    def test_generate_wizard_questions(self, generator):
        """测试生成向导问题"""
        tables = [
            {"table_name": "cloud_fixed_plate", "comment": "固定车辆表", "business_domain": "车辆管理"},
            {"table_name": "cloud_park", "comment": "园区表", "business_domain": "园区管理"},
        ]

        questions = generator.generate_wizard_questions(tables, count=5)

        assert len(questions) <= 5
        # 应该包含开场问题
        assert any("查询哪些内容" in q.question for q in questions)
