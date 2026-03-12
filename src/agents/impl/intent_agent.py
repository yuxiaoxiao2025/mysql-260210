"""Intent Agent 实现"""
import re
from typing import Optional, List

from src.agents.base import BaseAgent
from src.agents.config import IntentAgentConfig
from src.agents.context import AgentContext, IntentModel
from src.agents.models import AgentResult
from src.intent.intent_recognizer import IntentRecognizer
from src.dialogue.concept_recognizer import ConceptRecognizer, RecognizedConcept
from src.dialogue.question_generator import QuestionGenerator
from src.memory.concept_store import ConceptStoreService
from src.memory.memory_models import ConceptMapping


class IntentAgent(BaseAgent):
    """意图识别 Agent

    封装 IntentRecognizer，将识别结果映射到 IntentModel。
    支持概念识别和概念学习功能。
    """

    def __init__(
        self,
        config: IntentAgentConfig,
        llm_client=None,
        knowledge_loader=None,
        concept_store: Optional[ConceptStoreService] = None
    ):
        """初始化 IntentAgent

        Args:
            config: Agent 配置
            llm_client: LLM 客户端（可选，用于创建 IntentRecognizer）
            knowledge_loader: 知识库加载器（可选，用于创建 IntentRecognizer）
            concept_store: 概念存储服务（可选，用于概念识别和学习）
        """
        super().__init__(config)
        self.llm_client = llm_client
        self.concept_store = concept_store
        self.recognizer = IntentRecognizer(llm_client, knowledge_loader)

        # 概念学习组件（可选）
        if concept_store:
            self.concept_recognizer = ConceptRecognizer(concept_store)
            self.question_generator = QuestionGenerator()
        else:
            self.concept_recognizer = None
            self.question_generator = None

    def _run_impl(self, context: AgentContext) -> AgentResult:
        """执行意图识别

        Args:
            context: 执行上下文

        Returns:
            AgentResult: 执行结果
        """
        # 0. 检查是否是澄清回答（概念学习）
        if self.concept_store and self._is_clarification_response(context):
            self._handle_clarification(context)
            # 继续正常意图识别

        # 1. 如果启用了概念学习，先识别概念
        if self.concept_recognizer:
            concepts = self.concept_recognizer.recognize(context.user_input)
            unrecognized = [c for c in concepts if c.needs_clarification]

            # 如果有未识别概念，生成澄清问题
            if unrecognized:
                return self._generate_clarification(context, unrecognized)

        # 2. 正常意图识别
        recognized = self.recognizer.recognize(context.user_input)

        # 3. 推断意图类型
        intent_type = self._infer_intent_type(recognized.operation_id)

        # 4. 判断是否需要澄清
        need_clarify = bool(
            not recognized.is_matched
            or recognized.missing_params
            or recognized.confidence < self.config.confidence_threshold
        )

        # 5. 提取未知术语
        reasoning = recognized.reasoning or ""
        unknown_term = self._extract_unknown_term(reasoning)
        if unknown_term:
            need_clarify = True
            reasoning = f"{reasoning}。请问{unknown_term}具体指什么？"

        # 6. 映射到IntentModel
        context.intent = IntentModel(
            type=intent_type,
            confidence=recognized.confidence,
            params=recognized.params,
            operation_id=recognized.operation_id,
            reasoning=reasoning,
            sql=recognized.fallback_sql,
            need_clarify=need_clarify
        )

        return AgentResult(success=True, data=context.intent)

    def _is_clarification_response(self, context: AgentContext) -> bool:
        """检查是否是澄清回答
        
        优先使用 pending_clarification 状态标志，
        如果不可用则回退到关键词匹配。
        """
        # 优先使用状态标志
        if hasattr(context, 'pending_clarification') and context.pending_clarification:
            return True
            
        # 回退到关键词匹配
        if not context.chat_history or len(context.chat_history) < 2:
            return False

        # 检查最后一条助手消息是否包含澄清问题
        last_assistant_msg = None
        for msg in reversed(context.chat_history):
            if msg.get("role") == "assistant":
                last_assistant_msg = msg.get("content", "")
                break

        if not last_assistant_msg:
            return False

        # 简单判断：包含"请问"、"具体指"等关键词
        clarification_keywords = ["请问", "具体指", "是指", "指的是"]
        return any(kw in last_assistant_msg for kw in clarification_keywords)

    def _handle_clarification(self, context: AgentContext) -> None:
        """处理澄清回答，学习概念
        
        从对话历史中提取概念术语和用户解释，
        创建新概念并保存到 concept_store。
        """
        # 从chat_history中提取概念术语
        last_assistant_msg = ""
        for msg in reversed(context.chat_history):
            if msg.get("role") == "assistant":
                last_assistant_msg = msg.get("content", "")
                break

        # 提取概念术语：支持中英文引号
        matches = re.findall(r'["""\'](.*?)["""\']', last_assistant_msg)
        if matches:
            concept_term = matches[0]
        else:
            # 尝试从"请问XXX具体指什么"模式中提取术语
            match = re.search(r'请问([^\s，。？]+)(?:具体指|是指|指的是)', last_assistant_msg)
            if match:
                concept_term = match.group(1)
            else:
                return
        
        user_explanation = context.user_input

        # 创建新概念
        new_concept = ConceptMapping(
            concept_id=f"learned_{concept_term}",
            user_terms=[concept_term],
            database_mapping={"meaning": user_explanation},
            description=user_explanation,
            learned_from="dialogue"
        )

        # 保存到concept_store（带错误处理）
        try:
            self.concept_store.add_concept(new_concept)
            context.learned_concepts.append(new_concept)
        except Exception as e:
            # 记录错误但不中断流程
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to save learned concept '{concept_term}': {e}", exc_info=True)

    def _generate_clarification(self, context: AgentContext, unrecognized: List[RecognizedConcept]) -> AgentResult:
        """生成澄清问题"""
        # 只处理第一个未识别概念
        first_concept = unrecognized[0]
        question = self.question_generator.generate_clarification_question(first_concept)

        context.intent = IntentModel(
            type="clarify",
            confidence=0.0,
            need_clarify=True,
            clarification_question=question.question,
            unrecognized_concepts=[c.term for c in unrecognized],
            reasoning=f"发现未识别概念: {first_concept.term}"
        )

        return AgentResult(success=True, data=context.intent)

    def _extract_unknown_term(self, reasoning: str) -> str | None:
        """从识别推理中提取未知概念词。"""
        if not reasoning:
            return None
        match = re.search(r"Unknown concept:\s*'([^']+)'", reasoning, flags=re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    def _infer_intent_type(self, operation_id: str | None) -> str:
        """从 operation_id 推断意图类型

        Args:
            operation_id: 操作ID

        Returns:
            str: 意图类型 (query/mutation/clarify/chat/qa)
        """
        if not operation_id:
            return "clarify"

        if operation_id == "general_chat":
            return "chat"
        if operation_id == "knowledge_qa":
            return "qa"

        # 根据 operation_id 后缀推断类型
        if operation_id.endswith("_query") or "_query_" in operation_id:
            return "query"
        elif any(suffix in operation_id for suffix in ["_create", "_update", "_delete", "_insert"]):
            return "mutation"
        else:
            # 默认根据 is_matched 等状态推断
            return "query"  # 默认类型