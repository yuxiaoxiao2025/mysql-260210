"""Security Agent 实现

集成 SQL 安全检查，防止危险 SQL 操作。
"""
from src.agents.base import BaseAgent
from src.agents.models import AgentResult
from src.agents.context import AgentContext
from src.agents.config import SecurityAgentConfig
from src.sql_safety import validate_sql, validate_direct_query_sql


class SecurityAgent(BaseAgent):
    """安全检查 Agent

    对用户意图中生成的 SQL 进行安全检查，拦截危险操作。

    Attributes:
        config: SecurityAgentConfig 配置对象
    """

    def __init__(self, config: SecurityAgentConfig):
        """初始化 Security Agent

        Args:
            config: Agent 配置对象
        """
        super().__init__(config)
        self.config = config

    def _run_impl(self, context: AgentContext) -> AgentResult:
        """执行安全检查

        Args:
            context: 执行上下文

        Returns:
            AgentResult: 执行结果
        """
        # 检查是否有 SQL 需要验证
        if not context.intent or not context.intent.sql:
            # 没有 SQL，跳过检查
            return AgentResult(success=True)

        sql = context.intent.sql

        try:
            # 基础 SQL 安全校验（检查危险关键字）
            is_valid, reason = validate_sql(sql)
            if not is_valid:
                context.is_safe = False
                return AgentResult(
                    success=False,
                    message=reason,
                    next_action="stop"
                )

            # 如果是 query 类型，进行额外的直接查询模式校验
            if context.intent.type == "query":
                is_valid, reason = validate_direct_query_sql(sql)
                if not is_valid:
                    context.is_safe = False
                    return AgentResult(
                        success=False,
                        message=reason,
                        next_action="stop"
                    )

            # 安全检查通过
            context.is_safe = True
            return AgentResult(success=True)

        except Exception as e:
            # 发生异常，视为不安全
            context.is_safe = False
            return AgentResult(
                success=False,
                message=str(e),
                next_action="stop"
            )
