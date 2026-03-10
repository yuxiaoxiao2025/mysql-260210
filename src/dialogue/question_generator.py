"""
Question generator for clarification and knowledge base building.

Generates natural language questions based on:
1. Unrecognized concepts
2. Ambiguous terms
3. Table schema analysis
"""

import logging
import random
from dataclasses import dataclass
from typing import List, Optional

from src.dialogue.concept_recognizer import RecognizedConcept

logger = logging.getLogger(__name__)


@dataclass
class ClarificationQuestion:
    """澄清问题"""
    question: str  # 问题文本
    concept_term: str  # 相关术语
    options: List[str]  # 选项列表
    question_type: str  # 问题类型: "clarification" | "learning" | "confirmation"


class QuestionGenerator:
    """
    问题生成器

    根据识别到的概念生成澄清问题。
    """

    # 问题模板
    CLARIFICATION_TEMPLATES = [
        '你说的"{term}"是什么意思？',
        '"{term}"在你的业务里指的是什么？',
        '我需要确认一下，"{term}"具体是指？',
    ]

    # 带选项的问题模板
    OPTION_TEMPLATES = [
        '"{term}"是指：\n{options}',
        '我理解"{term}"可能是：\n{options}\n请选择或说明其他含义',
    ]

    # 学习型问题模板
    LEARNING_TEMPLATES = [
        '我看到数据库里有 {table} 表，你的业务里叫它什么？',
        '{description}，你们平时怎么说这个？',
    ]

    def __init__(self, retrieval_agent=None):
        """
        初始化问题生成器。

        Args:
            retrieval_agent: 检索代理（用于获取表信息）
        """
        self.retrieval_agent = retrieval_agent
        logger.info("QuestionGenerator initialized")

    def generate_clarification_question(
        self,
        concept: RecognizedConcept
    ) -> ClarificationQuestion:
        """
        生成澄清问题。

        Args:
            concept: 识别到的概念

        Returns:
            澄清问题
        """
        if concept.possible_meanings:
            # 有可能的含义，生成选项
            return self._generate_option_question(concept)
        else:
            # 没有已知含义，生成开放问题
            return self._generate_open_question(concept)

    def _generate_option_question(self, concept: RecognizedConcept) -> ClarificationQuestion:
        """生成带选项的问题"""
        options = concept.possible_meanings
        options_text = "\n".join(
            f"{chr(65 + i)}. {opt}"
            for i, opt in enumerate(options)
        )
        options_text += f"\n{chr(65 + len(options))}. 其他（请说明）"

        template = random.choice(self.OPTION_TEMPLATES)
        question = template.format(
            term=concept.term,
            options=options_text
        )

        return ClarificationQuestion(
            question=question,
            concept_term=concept.term,
            options=options + ["其他"],
            question_type="clarification"
        )

    def _generate_open_question(self, concept: RecognizedConcept) -> ClarificationQuestion:
        """生成开放问题"""
        template = random.choice(self.CLARIFICATION_TEMPLATES)
        question = template.format(term=concept.term)

        return ClarificationQuestion(
            question=question,
            concept_term=concept.term,
            options=[],
            question_type="clarification"
        )

    def generate_learning_questions(
        self,
        table_info: dict,
        count: int = 1
    ) -> List[ClarificationQuestion]:
        """
        生成学习型问题（用于初始化知识库）。

        Args:
            table_info: 表信息
            count: 生成数量

        Returns:
            问题列表
        """
        questions = []

        table_name = table_info.get("table_name", "")
        comment = table_info.get("comment", "")
        domain = table_info.get("business_domain", "")

        # 根据表信息生成问题
        if comment:
            question_text = f"我看到数据库里有 {table_name} 表（{comment}），你们的业务里怎么叫它？"
        else:
            question_text = f"我看到数据库里有 {table_name} 表，这是什么业务相关的表？"

        questions.append(ClarificationQuestion(
            question=question_text,
            concept_term=table_name,
            options=[],
            question_type="learning"
        ))

        return questions

    def generate_confirmation_question(
        self,
        intent_description: str
    ) -> ClarificationQuestion:
        """
        生成确认问题。

        Args:
            intent_description: 意图描述

        Returns:
            确认问题
        """
        return ClarificationQuestion(
            question=f"我准备{intent_description}，可以吗？",
            concept_term="",
            options=["可以", "需要调整"],
            question_type="confirmation"
        )

    def generate_wizard_questions(
        self,
        tables: List[dict],
        count: int = 10
    ) -> List[ClarificationQuestion]:
        """
        生成向导问题（用于初始化知识库）。

        Args:
            tables: 表信息列表
            count: 问题数量

        Returns:
            问题列表
        """
        questions = []

        # 添加开场问题
        questions.append(ClarificationQuestion(
            question="你平时用这个工具主要查询哪些内容？",
            concept_term="query_intent",
            options=[
                "车牌信息查询",
                "进出场记录查询",
                "费用查询",
                "其他（请说明）"
            ],
            question_type="learning"
        ))

        questions.append(ClarificationQuestion(
            question="你会修改数据库的哪些内容？",
            concept_term="mutation_intent",
            options=[
                "下发车辆到园区",
                "添加/删除车牌",
                "修改车辆信息",
                "其他（请说明）"
            ],
            question_type="learning"
        ))

        # 根据表信息生成问题
        important_tables = self._select_important_tables(tables, count - 2)
        for table in important_tables:
            questions.extend(self.generate_learning_questions(table))

        return questions[:count]

    def _select_important_tables(self, tables: List[dict], count: int) -> List[dict]:
        """选择重要的表生成问题"""
        # 优先选择有业务域的表
        domain_tables = [t for t in tables if t.get("business_domain")]
        other_tables = [t for t in tables if not t.get("business_domain")]

        selected = domain_tables[:count]
        if len(selected) < count:
            selected.extend(other_tables[:count - len(selected)])

        return selected
