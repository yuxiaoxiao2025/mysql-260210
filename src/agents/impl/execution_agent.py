"""Execution Agent 实现

用于执行操作，调用 OperationExecutor 的执行功能。
"""
from src.agents.base import BaseAgent
from src.agents.models import AgentResult
from src.agents.context import AgentContext
from src.executor.operation_executor import OperationExecutor


class ExecutionAgent(BaseAgent):
    """执行 Agent

    执行用户意图指定的操作，支持查询和变更操作。
    """

    def _run_impl(self, context: AgentContext) -> AgentResult:
        """执行操作

        Args:
            context: 执行上下文

        Returns:
            AgentResult: 执行结果
        """
        # 检查意图是否存在
        if not context.intent:
            return AgentResult(success=False, message="未找到意图")

        # 检查操作ID是否存在
        if not context.intent.operation_id:
            return AgentResult(
                success=False,
                message="缺少操作ID"
            )

        # 初始化执行器
        executor = OperationExecutor()

        # 执行操作
        result = executor.execute_operation(
            context.intent.operation_id,
            context.intent.params,
            preview_only=False
        )

        # 保存执行结果到上下文
        context.execution_result = result

        return AgentResult(
            success=True,
            data=result,
            message="执行成功" if result.success else "执行失败"
        )
