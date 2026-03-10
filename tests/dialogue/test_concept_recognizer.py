"""
Tests for concept recognizer.
"""

import pytest
from unittest.mock import Mock

from src.dialogue.concept_recognizer import ConceptRecognizer, RecognizedConcept


class TestConceptRecognizer:
    """概念识别器测试"""

    @pytest.fixture
    def mock_concept_store(self):
        """模拟概念存储服务"""
        mock = Mock()
        # 模拟已知概念
        mock.find_by_user_term.side_effect = lambda term: (
            Mock(concept_id="parking_lot") if term == "园区" else None
        )
        return mock

    @pytest.fixture
    def recognizer(self, mock_concept_store):
        """创建识别器实例"""
        return ConceptRecognizer(mock_concept_store)

    def test_recognize_business_keyword(self, recognizer):
        """测试识别业务关键词"""
        concepts = recognizer.recognize("查一下沪BAB1565停过哪些园区")

        terms = [c.term for c in concepts]
        assert "停过" in terms or "园区" in terms

    def test_matched_concept_no_clarification(self, recognizer):
        """测试已匹配概念不需要澄清"""
        concepts = recognizer.recognize("查一下园区列表")

        for concept in concepts:
            if concept.term == "园区":
                assert concept.needs_clarification is False

    def test_ambiguous_concept_needs_clarification(self, recognizer):
        """测试多义概念需要澄清"""
        concepts = recognizer.recognize("这辆车停过哪些园区")

        for concept in concepts:
            if concept.term == "停过":
                assert concept.needs_clarification is True
                assert len(concept.possible_meanings) > 0

    def test_get_unrecognized_terms(self, recognizer):
        """测试获取未识别术语"""
        terms = recognizer.get_unrecognized_terms("沪BAB1565停过哪些园区")

        # "停过"是未匹配的多义词，应该在列表中
        assert "停过" in terms

    def test_get_ambiguity_options(self, recognizer):
        """测试获取多义选项"""
        options = recognizer.get_ambiguity_options("停过")

        assert len(options) > 0
        assert "进出场记录" in options
