"""Intent Agent 实现"""
from src.agents.base import BaseAgent
from src.agents.config import IntentAgentConfig
from src.agents.context import AgentContext, IntentModel
from src.agents.models import AgentResult
# Integration: Import existing module
from src.intent.intent_recognizer import IntentRecognizer


class IntentAgent(BaseAgent):
    """意图识别 Agent

    封装 IntentRecognizer，将识别结果映射到 IntentModel。
    """

    def __init__(self, config: IntentAgentConfig, llm_client=None, knowledge_loader=None):
        """初始化 IntentAgent

        Args:
            config: Agent 配置
            llm_client: LLM 客户端（可选，用于创建 IntentRecognizer）
            knowledge_loader: 知识库加载器（可选，用于创建 IntentRecognizer）
        """
        super().__init__(config)
        self.recognizer = IntentRecognizer(llm_client, knowledge_loader)

    def _run_impl(self, context: AgentContext) -> AgentResult:
        """执行意图识别

        Args:
            context: 执行上下文

        Returns:
            AgentResult: 执行结果
        """
        # Call existing logic
        recognized = self.recognizer.recognize(context.user_input)

        # Infer intent type from operation_id
        intent_type = self._infer_intent_type(recognized.operation_id)

        # Determine if clarification is needed
        need_clarify = (
            not recognized.is_matched
            or recognized.missing_params
            or recognized.confidence < 0.6
        )

        # Map to Context Model
        context.intent = IntentModel(
            type=intent_type,
            confidence=recognized.confidence,
            params=recognized.params,
            operation_id=recognized.operation_id,
            reasoning=recognized.reasoning,
            sql=recognized.fallback_sql,
            need_clarify=need_clarify
        )

        return AgentResult(success=True, data=context.intent)

    def _infer_intent_type(self, operation_id: str | None) -> str:
        """从 operation_id 推断意图类型

        Args:
            operation_id: 操作ID

        Returns:
            str: 意图类型 (query/mutation/clarify)
        """
        if not operation_id:
            return "clarify"

        # 根据 operation_id 后缀推断类型
        if operation_id.endswith("_query") or "_query_" in operation_id:
            return "query"
        elif any(suffix in operation_id for suffix in ["_create", "_update", "_delete", "_insert"]):
            return "mutation"
        else:
            # 默认根据 is_matched 等状态推断
            return "query"  # 默认类型
