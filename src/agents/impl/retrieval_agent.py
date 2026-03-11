"""Retrieval Agent 实现

集成 RetrievalPipeline，将检索结果写入 AgentContext.schema_context。
"""
from src.agents.base import BaseAgent
from src.agents.config import BaseAgentConfig
from src.agents.context import AgentContext
from src.agents.models import AgentResult
from src.metadata.retrieval_pipeline import RetrievalPipeline


class RetrievalAgent(BaseAgent):
    """检索 Agent

    封装 RetrievalPipeline，执行元数据检索并将结果映射到 AgentContext。

    Attributes:
        config: Agent 配置
        pipeline: RetrievalPipeline 实例
    """

    def __init__(self, config: BaseAgentConfig, pipeline: RetrievalPipeline = None):
        """初始化 RetrievalAgent

        Args:
            config: Agent 配置
            pipeline: 可选的 RetrievalPipeline 实例（用于测试注入）
        """
        super().__init__(config)
        self.pipeline = pipeline or RetrievalPipeline()

    def _run_impl(self, context: AgentContext) -> AgentResult:
        """执行检索

        Args:
            context: 执行上下文

        Returns:
            AgentResult: 执行结果
        """
        # 检查是否有意图信息
        if not context.intent:
            return AgentResult(
                success=True,
                message="No intent available for retrieval",
                data=None
            )

        try:
            # 调用 RetrievalPipeline 执行检索
            result = self.pipeline.search(context.user_input, top_k=10)

            # 将结果格式化为字符串写入 schema_context
            if result.matches:
                table_names = [match.table_name for match in result.matches]
                context.schema_context = ", ".join(table_names)
                return AgentResult(
                    success=True,
                    data=result,
                    message=f"Found {len(table_names)} relevant tables"
                )
            else:
                context.schema_context = ""
                return AgentResult(
                    success=True,
                    data=result,
                    message="No relevant tables found"
                )

        except Exception as e:
            return AgentResult(
                success=False,
                message=f"Retrieval failed: {str(e)}",
                data=None
            )
