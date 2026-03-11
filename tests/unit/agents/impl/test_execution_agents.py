"""测试 PreviewAgent 和 ExecutionAgent"""
from unittest.mock import MagicMock, patch

from src.agents.impl.preview_agent import PreviewAgent
from src.agents.impl.execution_agent import ExecutionAgent
from src.agents.context import AgentContext, IntentModel
from src.agents.config import BaseAgentConfig


@patch("src.agents.impl.preview_agent.OperationExecutor")
def test_preview_agent_mutation_only(mock_executor_cls):
    """测试 PreviewAgent 只对 mutation 类型意图执行预览"""
    agent = PreviewAgent(BaseAgentConfig(name="preview"))
    context = AgentContext(user_input="drop table")
    context.intent = IntentModel(type="mutation", operation_id="op_1")

    agent.run(context)
    mock_executor_cls.return_value.execute_operation.assert_called_with(
        "op_1", {}, preview_only=True
    )


@patch("src.agents.impl.execution_agent.OperationExecutor")
def test_execution_agent_run(mock_executor_cls):
    """测试 ExecutionAgent 执行操作"""
    agent = ExecutionAgent(BaseAgentConfig(name="exec"))
    context = AgentContext(user_input="query")
    context.intent = IntentModel(type="query", operation_id="op_2")

    agent.run(context)
    mock_executor_cls.return_value.execute_operation.assert_called_with(
        "op_2", {}, preview_only=False
    )
