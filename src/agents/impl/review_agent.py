"""Review Agent 实现"""
from src.agents.base import BaseAgent
from src.agents.models import AgentResult
from src.agents.context import AgentContext
from src.agents.config import ReviewAgentConfig


class ReviewAgent(BaseAgent):
    """执行前确认 Agent。"""

    def __init__(self, config: ReviewAgentConfig):
        super().__init__(config)
        self.config = config

    def _run_impl(self, context: AgentContext) -> AgentResult:
        if not context.intent:
            return AgentResult(success=False, message="缺少意图信息", next_action="stop")

        intent_type = context.intent.type
        sql_text = context.intent.sql or ""

        if intent_type == "mutation" or sql_text.strip().upper().startswith(
            ("DELETE", "UPDATE", "INSERT", "DROP", "TRUNCATE", "ALTER")
        ):
            return AgentResult(
                success=True,
                next_action="ask_user",
                message=f"检测到高风险操作，是否确认执行？SQL: {sql_text or 'N/A'}",
                data={"intent_type": intent_type, "sql": sql_text},
            )

        if intent_type == "query" and self.config.auto_run_query:
            return AgentResult(success=True, message="查询操作已自动通过复核")

        return AgentResult(success=True, message="复核通过")
