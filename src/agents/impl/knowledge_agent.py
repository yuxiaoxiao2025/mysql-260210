"""Knowledge Agent 实现"""
from src.agents.base import BaseAgent
from src.agents.models import AgentResult
from src.agents.context import AgentContext
from src.llm_client import LLMClient


class KnowledgeAgent(BaseAgent):
    """知识问答 Agent，负责基于 schema 上下文输出流式回复。"""

    def __init__(self, config, llm_client: LLMClient | None = None):
        super().__init__(config)
        self.llm_client = llm_client or LLMClient()

    def _run_impl(self, context: AgentContext) -> AgentResult:
        if not context.intent or context.intent.type not in ["qa", "chat"]:
            return AgentResult(success=False, message="KnowledgeAgent 仅处理 qa/chat 意图")

        schema_context = context.schema_context or "暂无可用 schema 上下文"
        messages = [
            {
                "role": "system",
                "content": (
                    "你是数据库知识助手。请基于给定 schema 上下文回答用户问题，"
                    "优先给出准确、可执行的结论。"
                    f"\n\n[Schema Context]\n{schema_context}"
                ),
            },
            {"role": "user", "content": context.user_input},
        ]

        stream = self.llm_client.chat_stream(messages=messages, enable_thinking=True)
        return AgentResult(success=True, data=stream, message="knowledge_stream_ready")
