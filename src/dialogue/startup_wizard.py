"""
Startup wizard for knowledge base initialization.

Guides users through a set of questions to build initial knowledge base.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

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
