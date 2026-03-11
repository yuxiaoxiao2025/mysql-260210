"""Preview Agent 实现

用于预览变更操作，调用 OperationExecutor 的预览功能。
"""
from src.agents.base import BaseAgent
from src.agents.models import AgentResult
from src.agents.context import AgentContext
from src.executor.operation_executor import OperationExecutor


class PreviewAgent(BaseAgent):
    """预览 Agent

    对 mutation 类型的意图执行预览，展示将要执行的操作及其影响。
    """

    def _run_impl(self, context: AgentContext) -> AgentResult:
        """执行预览

        Args:
            context: 执行上下文

        Returns:
            AgentResult: 预览结果
        """
        # 检查意图是否存在
        if not context.intent:
            return AgentResult(success=False, message="未找到意图")

        # 只对 mutation 类型的意图执行预览
        if context.intent.type != "mutation":
            return AgentResult(
                success=True,
                message="跳过非变更操作的预览"
            )

        # 检查操作ID是否存在
        if not context.intent.operation_id:
            return AgentResult(
                success=False,
                message="缺少操作ID"
            )

        # 初始化执行器
        executor = OperationExecutor()

        # 执行预览
        preview = executor.execute_operation(
            context.intent.operation_id,
            context.intent.params,
            preview_only=True
        )

        # 保存预览数据到上下文
        context.preview_data = preview

        return AgentResult(
            success=True,
            data=preview,
            message="预览成功"
        )
