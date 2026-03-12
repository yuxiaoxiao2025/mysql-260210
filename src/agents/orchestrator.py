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

    def process(
        self,
        user_input: str,
        chat_history: list[dict] | None = None,
        user_confirmation: bool | None = None
    ) -> AgentContext:
        """处理用户输入

        按照标准流程执行 Agent 协调:
        1. 意图识别 - 识别用户意图
        2. 根据意图类型路由:
           - chat/qa -> 对话流程 (KnowledgeAgent)
           - query/mutation -> 业务流程 (Security -> Preview -> Execution)

        Args:
            user_input: 用户输入文本
            chat_history: 对话历史（可选），用于多轮对话上下文
            user_confirmation: 用户确认标志（可选，用于 ReviewAgent）

        Returns:
            AgentContext: 包含执行结果的上下文
        """
        context = AgentContext(
            user_input=user_input,
            chat_history=chat_history or []
        )

        # 1. Intent - 意图识别
        res = self.intent_agent.run(context)
        if not res.success:
            context.step_history.append("intent_failed")
            return context

        context.step_history.append("intent")

        # 2. 检查是否需要澄清
        if context.intent and context.intent.need_clarify:
            context.pending_clarification = True
            return context

        # 3. 根据意图类型路由
        if context.intent and context.intent.type in ["chat", "qa"]:
            return self._handle_conversation(context)
        elif context.intent and context.intent.type in ["query", "mutation"]:
            return self._handle_business_operation(context, user_confirmation)
        else:
            # 未知意图类型
            return context

    def _handle_conversation(self, context: AgentContext) -> AgentContext:
        """处理对话和知识问答

        执行对话流程：
        1. 可选的 schema 检索（为知识问答提供上下文）
        2. 调用 KnowledgeAgent 进行流式问答

        Args:
            context: 执行上下文

        Returns:
            AgentContext: 更新后的上下文，其中 execution_result 包含 generator 对象
        """
        # 检索相关schema（可选）
        retrieval_res = self.retrieval_agent.run(context)
        if retrieval_res.success:
            context.step_history.append("retrieval")

        # 流式问答
        knowledge_res = self.knowledge_agent.run(context)
        if not knowledge_res.success:
            context.step_history.append("knowledge_failed")
            return context

        context.execution_result = knowledge_res.data  # generator
        context.step_history.append("knowledge")

        return context

    def _handle_business_operation(
        self,
        context: AgentContext,
        user_confirmation: bool | None = None
    ) -> AgentContext:
        """处理业务操作（query/mutation）

        执行完整业务流程：
        1. Retrieval - 信息检索
        2. Security - 安全检查
        3. Preview - 预览操作（仅 mutation）
        4. Review - 人工审核（如果配置）
        5. Execution - 执行操作

        Args:
            context: 执行上下文
            user_confirmation: 用户确认标志

        Returns:
            AgentContext: 更新后的上下文
        """
        # 1. Retrieval - 信息检索
        retrieval_res = self.retrieval_agent.run(context)
        if retrieval_res.success:
            context.step_history.append("retrieval")

        # 3. Security - 安全检查
        if not self.security_agent.run(context).success:
            context.step_history.append("security_failed")
            return context
        context.step_history.append("security")

        # 2. Preview - 预览操作 (if mutation)
        if context.intent and context.intent.type == "mutation":
            preview_res = self.preview_agent.run(context)
            if preview_res.success:
                context.step_history.append("preview")

        # 3. Review - 人工审核 (if provided)
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

        # 4. Execution - 执行操作
        self.execution_agent.run(context)
        context.step_history.append("execution")

        return context
