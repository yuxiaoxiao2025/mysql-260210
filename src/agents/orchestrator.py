"""Orchestrator 实现 - 协调所有 Agent 的执行流程"""
from src.agents.context import AgentContext
from src.agents.config import IntentAgentConfig, SecurityAgentConfig, BaseAgentConfig
from src.agents.impl.intent_agent import IntentAgent
from src.agents.impl.retrieval_agent import RetrievalAgent
from src.agents.impl.knowledge_agent import KnowledgeAgent
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

    def __init__(self, intent_agent=None, retrieval_agent=None, knowledge_agent=None, security_agent=None,
                 preview_agent=None, execution_agent=None, review_agent=None, llm_client=None, knowledge_loader=None):
        """初始化 Orchestrator

        支持依赖注入用于测试，否则初始化默认 Agent。

        Args:
            intent_agent: IntentAgent 实例 (可选)
            retrieval_agent: RetrievalAgent 实例 (可选)
            security_agent: SecurityAgent 实例 (可选)
            preview_agent: PreviewAgent 实例 (可选)
            execution_agent: ExecutionAgent 实例 (可选)
            llm_client: LLM 客户端 (可选，用于初始化 IntentAgent)
            knowledge_loader: KnowledgeLoader 实例 (可选，用于初始化 IntentAgent)
        """
        self.intent_agent = intent_agent or IntentAgent(
            IntentAgentConfig(name="intent"), 
            llm_client=llm_client, 
            knowledge_loader=knowledge_loader
        )
        self.retrieval_agent = retrieval_agent or RetrievalAgent(BaseAgentConfig(name="retrieval"))
        self.knowledge_agent = knowledge_agent or KnowledgeAgent(
            BaseAgentConfig(name="knowledge"),
            llm_client=llm_client
        )
        self.security_agent = security_agent or SecurityAgent(SecurityAgentConfig(name="security"))
        self.preview_agent = preview_agent or PreviewAgent(BaseAgentConfig(name="preview"))
        self.review_agent = review_agent
        self.execution_agent = execution_agent or ExecutionAgent(
            BaseAgentConfig(name="execution"),
            llm_client=llm_client
        )

    def process(self, user_input: str, user_confirmation: bool | None = None) -> AgentContext:
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
            # Special handling for chat/qa intents that might need clarification but are actually valid interactions
            if context.intent and context.intent.type in ["chat", "qa"]:
                # Let them proceed to execution (or a specialized chat handler)
                # For now, we'll mark them as safe and let ExecutionAgent handle them (or add a ChatAgent)
                pass
            else:
                context.step_history.append("intent_failed")
                return context
        context.step_history.append("intent")

        # 2. Retrieval
        retrieval_res = self.retrieval_agent.run(context)
        if retrieval_res.success:
            context.step_history.append("retrieval")

        # 3. Knowledge (for chat/qa)
        if context.intent and context.intent.type in ["chat", "qa"]:
            knowledge_res = self.knowledge_agent.run(context)
            if not knowledge_res.success:
                context.step_history.append("knowledge_failed")
                return context
            context.execution_result = knowledge_res.data
            context.step_history.append("knowledge")
            context.step_history.append("execution")
            return context

        # 4. Security
        if not self.security_agent.run(context).success:
            context.step_history.append("security_failed")
            return context
        context.step_history.append("security")

        # 5. Preview (if mutation)
        if context.intent and context.intent.type == "mutation":
            preview_res = self.preview_agent.run(context)
            if preview_res.success:
                context.step_history.append("preview")

        # 6. Review (if provided)
        if self.review_agent and user_confirmation is not True:
            review_res = self.review_agent.run(context)
            if review_res.next_action == "ask_user":
                context.execution_result = review_res
                context.step_history.append("review")
                return context
            if not review_res.success:
                context.step_history.append("review_failed")
                return context
            context.step_history.append("review")
        elif user_confirmation is True:
            context.step_history.append("review_confirmed")

        # 7. Execution
        self.execution_agent.run(context)
        context.step_history.append("execution")

        return context
