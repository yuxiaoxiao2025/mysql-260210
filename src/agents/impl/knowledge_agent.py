"""Knowledge Agent 实现"""
import logging
from src.agents.base import BaseAgent
from src.agents.models import AgentResult
from src.agents.context import AgentContext
from src.llm_client import LLMClient

logger = logging.getLogger(__name__)


class KnowledgeAgent(BaseAgent):
    """知识问答 Agent，负责基于 schema 上下文输出流式回复。"""

    def __init__(self, config, llm_client: LLMClient | None = None):
        super().__init__(config)
        self.llm_client = llm_client or LLMClient()

    def _run_impl(self, context: AgentContext) -> AgentResult:
        """执行知识问答

        Args:
            context: Agent 执行上下文

        Returns:
            AgentResult: 包含 generator 的结果对象
        """
        if not context.intent or context.intent.type not in ["qa", "chat"]:
            return AgentResult(success=False, message="KnowledgeAgent 仅处理 qa/chat 意图")

        # 构建消息
        schema_context = context.schema_context or "暂无可用 schema 上下文"

        # 简化系统提示，让模型更自由
        messages = [
            {
                "role": "system",
                "content": f"你是智能停车数据库助手。\n\n相关表: {schema_context}"
            },
            {"role": "user", "content": context.user_input},
        ]

        try:
            stream = self.llm_client.chat_stream(messages=messages, enable_thinking=True)

            # 验证 generator 是否有效
            if stream is None:
                logger.error("chat_stream returned None")
                return AgentResult(
                    success=False,
                    message="对话服务返回异常",
                    data=None
                )

            return AgentResult(success=True, data=stream, message="knowledge_stream_ready")

        except Exception as e:
            logger.error(f"KnowledgeAgent failed: {e}", exc_info=True)
            return AgentResult(
                success=False,
                message=f"对话服务异常: {str(e)}",
                data=None
            )
