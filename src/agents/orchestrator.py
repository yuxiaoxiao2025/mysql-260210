"""Orchestrator 实现 - 协调所有 Agent 的执行流程"""
from src.agents.context import AgentContext
from src.agents.config import IntentAgentConfig, SecurityAgentConfig, BaseAgentConfig
from src.agents.impl.intent_agent import IntentAgent
from src.agents.impl.retrieval_agent import RetrievalAgent
from src.agents.impl.security_agent import SecurityAgent
from src.agents.impl.preview_agent import PreviewAgent
from src.agents.impl.execution_agent import ExecutionAgent


class Orchestrator:
    """Orchestrator - 协调 Agent 执行流程

    按照以下顺序协调 Agent 执行:
    1. IntentAgent - 识别用户意图
    2. RetrievalAgent - 检索相关 Schema 信息
    3. SecurityAgent - 验证 SQL 安全
    4. PreviewAgent - 预览变更操作 (仅 mutation)
    5. ExecutionAgent - 执行操作

    Attributes:
        intent_agent: IntentAgent 实例
        retrieval_agent: RetrievalAgent 实例
        security_agent: SecurityAgent 实例
        preview_agent: PreviewAgent 实例
        execution_agent: ExecutionAgent 实例
    """

    def __init__(self, intent_agent=None, retrieval_agent=None, security_agent=None,
                 preview_agent=None, execution_agent=None):
        """初始化 Orchestrator

        支持依赖注入用于测试，否则初始化默认 Agent。

        Args:
            intent_agent: IntentAgent 实例 (可选)
            retrieval_agent: RetrievalAgent 实例 (可选)
            security_agent: SecurityAgent 实例 (可选)
            preview_agent: PreviewAgent 实例 (可选)
            execution_agent: ExecutionAgent 实例 (可选)
        """
        self.intent_agent = intent_agent or IntentAgent(IntentAgentConfig(name="intent"))
        self.retrieval_agent = retrieval_agent or RetrievalAgent(BaseAgentConfig(name="retrieval"))
        self.security_agent = security_agent or SecurityAgent(SecurityAgentConfig(name="security"))
        self.preview_agent = preview_agent or PreviewAgent(BaseAgentConfig(name="preview"))
        self.execution_agent = execution_agent or ExecutionAgent(BaseAgentConfig(name="execution"))

    def process(self, user_input: str) -> AgentContext:
        """处理用户输入

        按照标准流程执行 Agent 协调:
        1. 意图识别 - 识别用户意图
        2. 信息检索 - 检索相关 Schema
        3. 安全检查 - 验证 SQL 安全
        4. 预览操作 - mutation 类型预览
        5. 执行操作 - 执行最终操作

        Args:
            user_input: 用户输入文本

        Returns:
            AgentContext: 包含执行结果的上下文
        """
        context = AgentContext(user_input=user_input)

        # 1. Intent
        res = self.intent_agent.run(context)
        if not res.success or (context.intent and context.intent.need_clarify):
            context.step_history.append("intent_failed")
            return context
        context.step_history.append("intent")

        # 2. Retrieval
        retrieval_res = self.retrieval_agent.run(context)
        if retrieval_res.success:
            context.step_history.append("retrieval")

        # 3. Security
        if not self.security_agent.run(context).success:
            context.step_history.append("security_failed")
            return context
        context.step_history.append("security")

        # 4. Preview (if mutation)
        if context.intent and context.intent.type == "mutation":
            preview_res = self.preview_agent.run(context)
            if preview_res.success:
                context.step_history.append("preview")

        # 5. Execution (if query or confirmed mutation)
        self.execution_agent.run(context)
        context.step_history.append("execution")

        return context
