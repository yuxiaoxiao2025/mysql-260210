"""Retrieval Agent 单元测试"""
from unittest.mock import MagicMock, patch
import pytest
from src.agents.impl.retrieval_agent import RetrievalAgent
from src.agents.config import BaseAgentConfig
from src.agents.context import AgentContext, IntentModel


@patch("src.agents.impl.retrieval_agent.RetrievalPipeline")
def test_retrieval_agent_search(mock_pipeline_cls):
    """测试 RetrievalAgent 调用 RetrievalPipeline 并将结果写入 context"""
    # Setup mock
    mock_pipeline = mock_pipeline_cls.return_value
    mock_result = MagicMock()
    mock_result.matches = [
        MagicMock(table_name="table_users"),
        MagicMock(table_name="table_orders"),
    ]
    mock_pipeline.search.return_value = mock_result

    agent = RetrievalAgent(BaseAgentConfig(name="retrieval"))
    context = AgentContext(user_input="find users")
    context.intent = IntentModel(type="query", params={"keywords": "users"})

    result = agent.run(context)

    assert result.success is True
    assert "table_users" in context.schema_context
    mock_pipeline.search.assert_called_once_with("find users", top_k=10)


@patch("src.agents.impl.retrieval_agent.RetrievalPipeline")
def test_retrieval_agent_no_intent(mock_pipeline_cls):
    """测试当 context.intent 为 None 时的处理"""
    mock_pipeline = mock_pipeline_cls.return_value

    agent = RetrievalAgent(BaseAgentConfig(name="retrieval"))
    context = AgentContext(user_input="find users")
    context.intent = None

    result = agent.run(context)

    assert result.success is True
    assert "No intent" in result.message
    mock_pipeline.search.assert_not_called()


@patch("src.agents.impl.retrieval_agent.RetrievalPipeline")
def test_retrieval_agent_empty_matches(mock_pipeline_cls):
    """测试当检索结果为空时的处理"""
    mock_pipeline = mock_pipeline_cls.return_value
    mock_result = MagicMock()
    mock_result.matches = []
    mock_pipeline.search.return_value = mock_result

    agent = RetrievalAgent(BaseAgentConfig(name="retrieval"))
    context = AgentContext(user_input="find something")
    context.intent = IntentModel(type="query", params={"keywords": "something"})

    result = agent.run(context)

    assert result.success is True
    assert "No relevant tables" in result.message
    assert context.schema_context == ""


@patch("src.agents.impl.retrieval_agent.RetrievalPipeline")
def test_retrieval_agent_pipeline_error(mock_pipeline_cls):
    """测试当 RetrievalPipeline 抛出异常时的处理"""
    mock_pipeline = mock_pipeline_cls.return_value
    mock_pipeline.search.side_effect = Exception("Pipeline error")

    agent = RetrievalAgent(BaseAgentConfig(name="retrieval"))
    context = AgentContext(user_input="find users")
    context.intent = IntentModel(type="query", params={"keywords": "users"})

    result = agent.run(context)

    assert result.success is False
    assert "Pipeline error" in result.message
