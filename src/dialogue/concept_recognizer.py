"""
Concept recognizer for identifying terms that need clarification.

Analyzes user input to find terms that:
1. Are not in the knowledge base
2. Could have multiple meanings
3. Need business context clarification
"""

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class RecognizedConcept:
    """识别到的概念"""
    term: str  # 原始术语
    position: tuple  # 在文本中的位置
    context: str  # 上下文
    needs_clarification: bool = True  # 是否需要澄清
    possible_meanings: List[str] = field(default_factory=list)  # 可能的含义
    matched_concept_id: Optional[str] = None  # 匹配到的概念ID


class ConceptRecognizer:
    """
    概念识别器

    从用户输入中识别需要澄清的概念。
    """

    # 停用词（不需要识别的词）
    STOP_WORDS = {
        "的", "了", "是", "在", "有", "和", "与", "或", "这", "那",
        "我", "你", "他", "她", "它", "们", "什么", "怎么", "如何",
        "可以", "能", "会", "要", "想", "请", "帮", "查", "看",
        "一下", "一个", "哪些", "多少", "有没有", "是不是",
    }

    # 业务关键词（可能需要澄清的词）
    BUSINESS_KEYWORDS = {
        # 车辆相关
        "内部车辆", "固定车", "临时车", "月租车", "VIP车", "黑名单",
        # 园区相关
        "园区", "场库", "停车场", "车库", "车位",
        # 操作相关
        "下发", "同步", "推送", "绑定", "解绑", "删除", "添加",
        # 状态相关
        "停过", "去过", "进出场", "出入", "停放", "停车",
        # 时间相关
        "到期", "过期", "有效", "续期",
        # 费用相关
        "缴费", "费用", "收费", "金额",
        # 其他
        "投诉", "违规", "异常", "记录",
    }

    # 可能有多义的概念
    AMBIGUOUS_CONCEPTS = {
        "停过": ["进出场记录", "绑定关系"],
        "去过": ["进出场记录", "绑定关系"],
        "下发": ["设置状态为已下发", "同步到园区系统"],
        "内部车辆": ["线上固定车", "线下固定车"],
        "园区": ["场库信息", "园区配置"],
    }

    def __init__(self, concept_store_service):
        """
        初始化概念识别器。

        Args:
            concept_store_service: 概念存储服务实例
        """
        self.concept_store = concept_store_service
        logger.info("ConceptRecognizer initialized")

    def recognize(self, text: str) -> List[RecognizedConcept]:
        """
        识别文本中需要澄清的概念。

        Args:
            text: 用户输入文本

        Returns:
            识别到的概念列表
        """
        concepts = []

        # 1. 识别业务关键词
        for keyword in self.BUSINESS_KEYWORDS:
            if keyword in text:
                concept = self._analyze_keyword(keyword, text)
                if concept:
                    concepts.append(concept)

        # 2. 检查知识库匹配
        for concept in concepts:
            matched = self.concept_store.find_by_user_term(concept.term)
            if matched:
                concept.matched_concept_id = matched.concept_id
                concept.needs_clarification = False

        # 3. 检查多义概念（只有未匹配知识库的多义概念才需要澄清）
        for concept in concepts:
            if concept.term in self.AMBIGUOUS_CONCEPTS:
                concept.possible_meanings = self.AMBIGUOUS_CONCEPTS[concept.term]
                # 只有未匹配到知识库的多义概念才需要澄清
                if concept.matched_concept_id is None:
                    concept.needs_clarification = True

        return concepts

    def _analyze_keyword(self, keyword: str, text: str) -> Optional[RecognizedConcept]:
        """分析关键词"""
        pos = text.find(keyword)
        if pos == -1:
            return None

        # 提取上下文
        start = max(0, pos - 10)
        end = min(len(text), pos + len(keyword) + 10)
        context = text[start:end]

        return RecognizedConcept(
            term=keyword,
            position=(pos, pos + len(keyword)),
            context=context,
            needs_clarification=True,
        )

    def get_unrecognized_terms(self, text: str) -> List[str]:
        """
        获取未识别的术语。

        Args:
            text: 用户输入文本

        Returns:
            未识别的术语列表
        """
        concepts = self.recognize(text)
        return [c.term for c in concepts if c.needs_clarification]

    def get_ambiguity_options(self, term: str) -> List[str]:
        """
        获取多义词的选项。

        Args:
            term: 术语

        Returns:
            可能的含义列表
        """
        return self.AMBIGUOUS_CONCEPTS.get(term, [])
