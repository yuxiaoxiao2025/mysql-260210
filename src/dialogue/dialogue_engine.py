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
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

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
    options: List[str] = field(default_factory=list)          # 可选项
    pending_concepts: List[str] = field(default_factory=list) # 待澄清的概念
    intent_description: Optional[str] = None     # 意图描述（用于确认）


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
        self.pending_intent: Optional[str] = None  # Store intent for execution

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
        
        self.pending_intent = intent_description

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
            
            intent_to_execute = self.pending_intent
            self.pending_intent = None

            return DialogueResponse(
                message="好的，正在执行...",
                state=DialogueState.EXECUTING,
                needs_input=False,
                intent_description=intent_to_execute
            )
        else:
            self.state = DialogueState.IDLE
            self.learned_concepts.clear()
            self.pending_intent = None

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
        self.pending_intent = intent_description

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
        self.pending_intent = None
