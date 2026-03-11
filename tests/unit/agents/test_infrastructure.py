import pytest
from src.agents.models import AgentResult
from src.agents.context import AgentContext
from src.agents.config import BaseAgentConfig
from src.agents.base import BaseAgent


def test_agent_context_structure():
    """测试 AgentContext 基本结构"""
    ctx = AgentContext(user_input="hello")
    assert ctx.trace_id is not None
    assert ctx.step_history == []


def test_base_agent_implementation():
    """测试 BaseAgent 可子类化并实现 _run_impl"""
    class TestAgent(BaseAgent):
        def _run_impl(self, context):
            return AgentResult(success=True)

    agent = TestAgent(BaseAgentConfig(name="test"))
    assert agent.run(AgentContext(user_input="")).success is True
