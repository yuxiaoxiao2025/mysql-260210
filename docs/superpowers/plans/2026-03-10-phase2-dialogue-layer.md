# 阶段二：核心对话层实施计划

> **For Claude:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现启动向导和对话引擎，实现"不懂就问"的交互模式

**Architecture:**
- 启动向导：首次使用时通过10个问题初始化知识库
- 对话引擎：检查知识库 → 匹配概念 → 不懂就问 → 用户确认 → 执行操作
- 概念识别：从用户输入中识别需要澄清的概念

**Tech Stack:** Python 3.10+, DashScope LLM, Pydantic

**依赖：** 阶段一（基础设施层）已完成

---

## 文件结构

```
src/
├── dialogue/                        # 新建：对话系统模块
│   ├── __init__.py
│   ├── startup_wizard.py            # 启动向导
│   ├── dialogue_engine.py           # 对话引擎
│   ├── concept_recognizer.py        # 概念识别器
│   ├── question_generator.py        # 问题生成器
│   └── intent_confirmer.py          # 意图确认器
│
├── cli/
│   └── interaction.py               # 修改：集成新对话引擎
│
└── main.py                          # 修改：启动流程
```

---

## Task 1: 创建概念识别器

**Files:**
- Create: `src/dialogue/__init__.py`
- Create: `src/dialogue/concept_recognizer.py`
- Test: `tests/dialogue/test_concept_recognizer.py`

- [ ] **Step 1: 创建对话系统模块目录**

```bash
mkdir -p E:/trae/mysql-260210/src/dialogue
mkdir -p E:/trae/mysql-260210/tests/dialogue
```

- [ ] **Step 2: 创建 `__init__.py`**

```python
# src/dialogue/__init__.py
"""
Intelligent dialogue system.

Provides natural language driven interaction with concept learning.
"""

from src.dialogue.concept_recognizer import ConceptRecognizer
from src.dialogue.dialogue_engine import DialogueEngine
from src.dialogue.startup_wizard import StartupWizard

__all__ = [
    "ConceptRecognizer",
    "DialogueEngine",
    "StartupWizard",
]
```

- [ ] **Step 3: 创建概念识别器**

```python
# src/dialogue/concept_recognizer.py
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

        # 3. 检查多义概念
        for concept in concepts:
            if concept.term in self.AMBIGUOUS_CONCEPTS:
                concept.possible_meanings = self.AMBIGUOUS_CONCEPTS[concept.term]
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
```

- [ ] **Step 4: 创建测试文件**

```python
# tests/dialogue/test_concept_recognizer.py
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
```

- [ ] **Step 5: 运行测试**

```bash
cd E:/trae/mysql-260210
python -m pytest tests/dialogue/test_concept_recognizer.py -v
```

- [ ] **Step 6: 提交**

```bash
git add src/dialogue/ tests/dialogue/
git commit -m "feat(dialogue): add concept recognizer for clarification detection"
```

---

## Task 2: 创建问题生成器

**Files:**
- Create: `src/dialogue/question_generator.py`
- Test: `tests/dialogue/test_question_generator.py`

- [ ] **Step 1: 创建问题生成器**

```python
# src/dialogue/question_generator.py
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
```

- [ ] **Step 2: 创建测试文件**

```python
# tests/dialogue/test_question_generator.py
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
```

- [ ] **Step 3: 运行测试**

```bash
cd E:/trae/mysql-260210
python -m pytest tests/dialogue/test_question_generator.py -v
```

- [ ] **Step 4: 提交**

```bash
git add src/dialogue/question_generator.py tests/dialogue/test_question_generator.py
git commit -m "feat(dialogue): add question generator for clarification"
```

---

## Task 3: 创建启动向导

**Files:**
- Create: `src/dialogue/startup_wizard.py`
- Test: `tests/dialogue/test_startup_wizard.py`

- [ ] **Step 1: 创建启动向导**

```python
# src/dialogue/startup_wizard.py
"""
Startup wizard for knowledge base initialization.

Guides users through a set of questions to build initial knowledge base.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Callable

from src.memory.concept_store import ConceptStoreService
from src.memory.memory_models import ConceptMapping
from src.dialogue.question_generator import QuestionGenerator, ClarificationQuestion

logger = logging.getLogger(__name__)


class WizardState(Enum):
    """向导状态"""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


@dataclass
class WizardProgress:
    """向导进度"""
    current_question: int = 0
    total_questions: int = 10
    answers: List[dict] = None

    def __post_init__(self):
        if self.answers is None:
            self.answers = []


class StartupWizard:
    """
    启动向导

    通过对话引导用户建立初始知识库。
    """

    QUESTIONS_PER_SESSION = 10

    def __init__(
        self,
        concept_store: ConceptStoreService,
        retrieval_agent=None,
        question_generator: Optional[QuestionGenerator] = None
    ):
        """
        初始化启动向导。

        Args:
            concept_store: 概念存储服务
            retrieval_agent: 检索代理
            question_generator: 问题生成器
        """
        self.concept_store = concept_store
        self.retrieval_agent = retrieval_agent
        self.question_generator = question_generator or QuestionGenerator()
        self.state = WizardState.NOT_STARTED
        self.progress = WizardProgress()
        self.questions: List[ClarificationQuestion] = []

        logger.info("StartupWizard initialized")

    def should_start(self) -> bool:
        """检查是否应该启动向导"""
        return self.concept_store.is_empty()

    def start(self) -> ClarificationQuestion:
        """
        启动向导。

        Returns:
            第一个问题
        """
        self.state = WizardState.IN_PROGRESS
        self.progress = WizardProgress(total_questions=self.QUESTIONS_PER_SESSION)

        # 生成问题
        tables = self._get_tables_for_questions()
        self.questions = self.question_generator.generate_wizard_questions(
            tables,
            count=self.QUESTIONS_PER_SESSION
        )

        logger.info(f"Startup wizard started with {len(self.questions)} questions")
        return self.questions[0]

    def _get_tables_for_questions(self) -> List[dict]:
        """获取用于生成问题的表"""
        if self.retrieval_agent:
            # 从检索代理获取重要表
            stats = self.retrieval_agent.get_stats()
            # 这里简化处理，实际应该获取具体表信息
            return []
        return []

    def get_current_question(self) -> Optional[ClarificationQuestion]:
        """获取当前问题"""
        if self.state != WizardState.IN_PROGRESS:
            return None

        if self.progress.current_question >= len(self.questions):
            return None

        return self.questions[self.progress.current_question]

    def answer(self, answer_text: str) -> Optional[ClarificationQuestion]:
        """
        回答当前问题。

        Args:
            answer_text: 用户的回答

        Returns:
            下一个问题，如果完成则返回 None
        """
        if self.state != WizardState.IN_PROGRESS:
            logger.warning("Wizard not in progress")
            return None

        current = self.get_current_question()
        if not current:
            return None

        # 记录答案
        self.progress.answers.append({
            "question": current.question,
            "concept_term": current.concept_term,
            "answer": answer_text,
        })

        # 如果是学习型问题，创建概念映射
        if current.question_type == "learning" and current.concept_term:
            self._create_concept_from_answer(current, answer_text)

        # 前进到下一个问题
        self.progress.current_question += 1

        # 检查是否完成
        if self.progress.current_question >= len(self.questions):
            self.state = WizardState.COMPLETED
            logger.info("Startup wizard completed")
            return None

        return self.questions[self.progress.current_question]

    def _create_concept_from_answer(
        self,
        question: ClarificationQuestion,
        answer: str
    ) -> None:
        """根据答案创建概念映射"""
        # 检查是否选择了选项
        if answer in [chr(65 + i) for i in range(len(question.options))]:
            idx = ord(answer) - ord('A')
            if idx < len(question.options):
                selected_option = question.options[idx]
            else:
                selected_option = answer
        else:
            selected_option = answer

        # 创建概念映射
        concept = ConceptMapping(
            concept_id=f"learned_{question.concept_term}",
            user_terms=[question.concept_term],
            database_mapping={"user_description": selected_option},
            description=selected_option,
            learned_from="startup_wizard"
        )

        # 检查是否已存在
        existing = self.concept_store.find_by_user_term(question.concept_term)
        if existing:
            # 更新现有概念
            existing.add_user_term(question.concept_term)
            existing.description = selected_option
        else:
            # 添加新概念
            self.concept_store.add_concept(concept)

        logger.info(f"Created concept from answer: {question.concept_term} -> {selected_option}")

    def skip(self) -> Optional[ClarificationQuestion]:
        """跳过当前问题"""
        if self.state != WizardState.IN_PROGRESS:
            return None

        self.progress.current_question += 1

        if self.progress.current_question >= len(self.questions):
            self.state = WizardState.COMPLETED
            return None

        return self.questions[self.progress.current_question]

    def get_welcome_message(self) -> str:
        """获取欢迎消息"""
        return (
            "你好！我是你的停车数据库助手。\n\n"
            "看起来这是你第一次使用，让我问你几个问题，"
            "帮我更好地理解你的业务。这样以后我就能更准确地帮你了。\n\n"
            "准备好了吗？"
        )

    def get_completion_message(self) -> str:
        """获取完成消息"""
        return (
            "太好了！我已经了解了你的基本业务需求。\n\n"
            "以后如果还有新的概念需要告诉我，随时可以说。\n\n"
            "现在，有什么可以帮你的吗？"
        )

    def get_status(self) -> dict:
        """获取向导状态"""
        return {
            "state": self.state.value,
            "current": self.progress.current_question,
            "total": self.progress.total_questions,
            "answers_count": len(self.progress.answers),
        }
```

- [ ] **Step 2: 创建测试文件**

```python
# tests/dialogue/test_startup_wizard.py
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
```

- [ ] **Step 3: 运行测试**

```bash
cd E:/trae/mysql-260210
python -m pytest tests/dialogue/test_startup_wizard.py -v
```

- [ ] **Step 4: 提交**

```bash
git add src/dialogue/startup_wizard.py tests/dialogue/test_startup_wizard.py
git commit -m "feat(dialogue): add startup wizard for knowledge base initialization"
```

---

## Task 4: 创建对话引擎

**Files:**
- Create: `src/dialogue/dialogue_engine.py`
- Test: `tests/dialogue/test_dialogue_engine.py`

- [ ] **Step 1: 创建对话引擎**

```python
# src/dialogue/dialogue_engine.py
"""
Dialogue engine for intelligent conversation.

Core engine that coordinates:
1. Context memory (current plate, history)
2. Concept recognition (what needs clarification)
3. Question generation (how to ask)
4. Intent confirmation (before execution)
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple

from src.memory.concept_store import ConceptStoreService
from src.memory.context_memory import ContextMemoryService
from src.memory.memory_models import ConceptMapping
from src.dialogue.concept_recognizer import ConceptRecognizer, RecognizedConcept
from src.dialogue.question_generator import QuestionGenerator, ClarificationQuestion

logger = logging.getLogger(__name__)


class DialogueState(Enum):
    """对话状态"""
    IDLE = "idle"                      # 空闲，等待用户输入
    CLARIFYING = "clarifying"          # 澄清中，等待用户回答
    CONFIRMING = "confirming"          # 确认中，等待用户确认
    EXECUTING = "executing"            # 执行中
    ERROR = "error"                    # 错误状态


@dataclass
class DialogueResponse:
    """对话响应"""
    message: str                       # 响应消息
    state: DialogueState               # 对话状态
    needs_input: bool = True           # 是否需要用户输入
    options: List[str] = None          # 可选项
    pending_concepts: List[str] = None # 待澄清的概念
    intent_description: str = None     # 意图描述（用于确认）

    def __post_init__(self):
        if self.options is None:
            self.options = []
        if self.pending_concepts is None:
            self.pending_concepts = []


class DialogueEngine:
    """
    对话引擎

    协调记忆、概念识别、问题生成，实现智能对话。
    """

    def __init__(
        self,
        concept_store: ConceptStoreService,
        context_memory: ContextMemoryService,
        concept_recognizer: Optional[ConceptRecognizer] = None,
        question_generator: Optional[QuestionGenerator] = None,
    ):
        """
        初始化对话引擎。

        Args:
            concept_store: 概念存储服务
            context_memory: 上下文记忆服务
            concept_recognizer: 概念识别器
            question_generator: 问题生成器
        """
        self.concept_store = concept_store
        self.context_memory = context_memory
        self.concept_recognizer = concept_recognizer or ConceptRecognizer(concept_store)
        self.question_generator = question_generator or QuestionGenerator()

        self.state = DialogueState.IDLE
        self.pending_questions: List[ClarificationQuestion] = []
        self.current_concept_term: Optional[str] = None
        self.learned_concepts: List[ConceptMapping] = []

        logger.info("DialogueEngine initialized")

    def process_input(self, user_input: str) -> DialogueResponse:
        """
        处理用户输入。

        Args:
            user_input: 用户输入

        Returns:
            对话响应
        """
        logger.debug(f"Processing input: {user_input}")

        # 1. 记录用户消息
        self.context_memory.add_user_message(user_input)

        # 2. 解析代词引用
        resolved_input = self.context_memory.resolve_reference(user_input)

        # 3. 根据当前状态处理
        if self.state == DialogueState.CLARIFYING:
            return self._handle_clarification_response(user_input)

        if self.state == DialogueState.CONFIRMING:
            return self._handle_confirmation_response(user_input)

        # 4. 识别需要澄清的概念
        concepts = self.concept_recognizer.recognize(resolved_input)
        unrecognized = [c for c in concepts if c.needs_clarification]

        if unrecognized:
            return self._start_clarification(unrecognized)

        # 5. 所有概念都已识别，准备执行
        return self._prepare_execution(resolved_input, concepts)

    def _start_clarification(self, concepts: List[RecognizedConcept]) -> DialogueResponse:
        """开始澄清流程"""
        self.state = DialogueState.CLARIFYING
        self.pending_questions = []

        for concept in concepts:
            question = self.question_generator.generate_clarification_question(concept)
            self.pending_questions.append(question)

        # 返回第一个问题
        first_question = self.pending_questions[0]
        self.current_concept_term = first_question.concept_term

        return DialogueResponse(
            message=first_question.question,
            state=DialogueState.CLARIFYING,
            options=first_question.options,
            pending_concepts=[q.concept_term for q in self.pending_questions],
        )

    def _handle_clarification_response(self, answer: str) -> DialogueResponse:
        """处理澄清回答"""
        if not self.pending_questions:
            self.state = DialogueState.IDLE
            return DialogueResponse(
                message="好的，让我重新理解一下。",
                state=DialogueState.IDLE,
            )

        # 记录学习到的概念
        current_question = self.pending_questions.pop(0)
        self._learn_concept(current_question, answer)

        # 检查是否还有待澄清的概念
        if self.pending_questions:
            next_question = self.pending_questions[0]
            self.current_concept_term = next_question.concept_term

            return DialogueResponse(
                message=next_question.question,
                state=DialogueState.CLARIFYING,
                options=next_question.options,
                pending_concepts=[q.concept_term for q in self.pending_questions],
            )

        # 所有概念已澄清，进入确认状态
        self.state = DialogueState.CONFIRMING
        return self._generate_confirmation()

    def _learn_concept(self, question: ClarificationQuestion, answer: str) -> None:
        """学习概念映射"""
        # 解析答案
        if answer in [chr(65 + i) for i in range(len(question.options))]:
            idx = ord(answer) - ord('A')
            if idx < len(question.options):
                selected_meaning = question.options[idx]
            else:
                selected_meaning = answer
        else:
            selected_meaning = answer

        # 创建或更新概念映射
        existing = self.concept_store.find_by_user_term(question.concept_term)

        if existing:
            existing.description = selected_meaning
            existing.confirm()
            self.learned_concepts.append(existing)
        else:
            new_concept = ConceptMapping(
                concept_id=f"learned_{question.concept_term}",
                user_terms=[question.concept_term],
                database_mapping={"meaning": selected_meaning},
                description=selected_meaning,
                learned_from="dialogue"
            )
            self.concept_store.add_concept(new_concept)
            self.learned_concepts.append(new_concept)

        logger.info(f"Learned concept: {question.concept_term} -> {selected_meaning}")

        # 记录到上下文
        self.context_memory.record_correction(
            f"用户确认: {question.concept_term} = {selected_meaning}"
        )

    def _generate_confirmation(self) -> DialogueResponse:
        """生成确认问题"""
        # 根据学习到的概念生成意图描述
        # 这里简化处理，实际应该调用 LLM 生成
        intent_parts = []
        for concept in self.learned_concepts:
            intent_parts.append(f"{concept.user_terms[0]}({concept.description})")

        intent_description = "执行相关操作"
        if intent_parts:
            intent_description = f"根据你说的{', '.join(intent_parts)}，执行查询"

        return DialogueResponse(
            message=f"好的，我准备{intent_description}。这样可以吗？",
            state=DialogueState.CONFIRMING,
            options=["可以", "需要调整"],
            intent_description=intent_description,
        )

    def _handle_confirmation_response(self, answer: str) -> DialogueResponse:
        """处理确认回答"""
        if answer in ["可以", "是", "确认", "好的", "A"]:
            self.state = DialogueState.EXECUTING
            self.learned_concepts.clear()

            return DialogueResponse(
                message="好的，正在执行...",
                state=DialogueState.EXECUTING,
                needs_input=False,
            )
        else:
            self.state = DialogueState.IDLE
            self.learned_concepts.clear()

            return DialogueResponse(
                message="好的，请告诉我需要怎么调整？",
                state=DialogueState.IDLE,
            )

    def _prepare_execution(
        self,
        resolved_input: str,
        concepts: List[RecognizedConcept]
    ) -> DialogueResponse:
        """准备执行"""
        # 所有概念都已识别，生成确认
        self.state = DialogueState.CONFIRMING

        # 构建意图描述
        intent_description = self._build_intent_description(resolved_input, concepts)

        # 记录助手消息
        self.context_memory.add_assistant_message(
            f"准备{intent_description}",
            metadata={"intent": intent_description}
        )

        return DialogueResponse(
            message=f"我准备{intent_description}，这样可以吗？",
            state=DialogueState.CONFIRMING,
            options=["可以", "需要调整"],
            intent_description=intent_description,
        )

    def _build_intent_description(
        self,
        input_text: str,
        concepts: List[RecognizedConcept]
    ) -> str:
        """构建意图描述"""
        # 这里简化处理，实际应该调用 LLM
        # 从概念中获取映射信息
        concept_info = []
        for concept in concepts:
            if concept.matched_concept_id:
                stored = self.concept_store.get_concept(concept.matched_concept_id)
                if stored:
                    concept_info.append(f"{concept.term}({stored.description})")

        if concept_info:
            return f"根据{', '.join(concept_info)}执行查询"

        return "执行相关操作"

    def get_state(self) -> DialogueState:
        """获取当前状态"""
        return self.state

    def reset(self) -> None:
        """重置对话状态"""
        self.state = DialogueState.IDLE
        self.pending_questions.clear()
        self.current_concept_term = None
        self.learned_concepts.clear()
```

- [ ] **Step 2: 创建测试文件**

```python
# tests/dialogue/test_dialogue_engine.py
"""
Tests for dialogue engine.
"""

import pytest
from unittest.mock import Mock

from src.dialogue.dialogue_engine import DialogueEngine, DialogueState
from src.memory.concept_store import ConceptStoreService
from src.memory.context_memory import ContextMemoryService


class TestDialogueEngine:
    """对话引擎测试"""

    @pytest.fixture
    def mock_concept_store(self):
        """模拟概念存储服务"""
        mock = Mock(spec=ConceptStoreService)
        mock.is_empty.return_value = False
        mock.find_by_user_term.return_value = None
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

        # 触发澄清
        response1 = engine.process_input("这辆车停过哪些园区")
        assert response1.state == DialogueState.CLARIFYING

        # 回答澄清问题
        response2 = engine.process_input("进出场记录")

        # 状态应该变化
        assert response2.state != DialogueState.CLARIFYING or len(engine.pending_questions) == 0

    def test_confirmation_flow(self, engine, mock_concept_store):
        """测试确认流程"""
        mock_concept_store.find_by_user_term.return_value = Mock(
            concept_id="test",
            user_terms=["测试"],
            description="测试概念"
        )

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
```

- [ ] **Step 3: 运行测试**

```bash
cd E:/trae/mysql-260210
python -m pytest tests/dialogue/test_dialogue_engine.py -v
```

- [ ] **Step 4: 提交**

```bash
git add src/dialogue/dialogue_engine.py tests/dialogue/test_dialogue_engine.py
git commit -m "feat(dialogue): add dialogue engine with clarification and confirmation"
```

---

## Task 5: 集成到主程序

**Files:**
- Modify: `src/main.py`
- Modify: `src/cli/interaction.py`

- [ ] **Step 1: 修改 main.py 集成启动流程**

在 `src/main.py` 中添加新的启动流程：

```python
# 在 main.py 开头添加导入
from src.memory.concept_store import ConceptStoreService
from src.memory.context_memory import ContextMemoryService
from src.dialogue.startup_wizard import StartupWizard
from src.dialogue.dialogue_engine import DialogueEngine

# 在 main() 函数中添加启动逻辑
def main():
    """Main entry point."""
    # ... 现有初始化代码 ...

    # 初始化记忆系统
    concept_store = ConceptStoreService()
    context_memory = ContextMemoryService()

    # 检查是否需要启动向导
    wizard = StartupWizard(concept_store)
    if wizard.should_start():
        print(wizard.get_welcome_message())
        # ... 向导流程 ...
    else:
        # 询问是否补充知识库
        response = input("是否需要补充知识库？(y/n): ")
        if response.lower() == 'y':
            # ... 补充知识库流程 ...
            pass

    # 进入对话模式
    engine = DialogueEngine(concept_store, context_memory)
    print("你好，我是你的停车数据库助手，有什么可以帮你？")

    while True:
        user_input = input("\n[MySQL/AI] > ")
        if user_input.lower() in ['exit', 'quit', '退出']:
            break

        response = engine.process_input(user_input)
        print(f"\n{response.message}")

        if response.options:
            print(f"选项: {', '.join(response.options)}")

    # ... 其余代码 ...
```

- [ ] **Step 2: 运行集成测试**

```bash
cd E:/trae/mysql-260210
python main.py
```

- [ ] **Step 3: 提交**

```bash
git add src/main.py src/cli/interaction.py
git commit -m "feat: integrate dialogue engine into main program

- Add startup wizard check on launch
- Add knowledge base supplement prompt
- Replace fixed intent recognition with dialogue engine"
```

---

## 阶段二完成检查

- [ ] 所有测试通过
- [ ] 概念识别器可用
- [ ] 问题生成器可用
- [ ] 启动向导可用
- [ ] 对话引擎可用
- [ ] 主程序已集成新流程

**完成后进入阶段三：增强功能层**