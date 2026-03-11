"""Intent Agent 单元测试"""
from unittest.mock import MagicMock, patch
from src.agents.impl.intent_agent import IntentAgent
from src.agents.config import IntentAgentConfig
from src.agents.context import AgentContext


@patch("src.agents.impl.intent_agent.IntentRecognizer")
def test_intent_agent_integration(mock_recognizer_cls):
    # Setup mock - 使用 RecognizedIntent 的数据结构
    mock_instance = mock_recognizer_cls.return_value
    mock_result = MagicMock()
    mock_result.operation_id = "users_query"
    mock_result.operation_name = "查询用户"
    mock_result.confidence = 0.95
    mock_result.params = {}
    mock_result.missing_params = []
    mock_result.fallback_sql = "SELECT * FROM users"
    mock_result.reasoning = "通过关键词匹配到操作: 查询用户"
    mock_result.suggestions = []
    mock_result.is_matched = True
    mock_instance.recognize.return_value = mock_result

    agent = IntentAgent(IntentAgentConfig(name="intent"), llm_client=None, knowledge_loader=None)
    context = AgentContext(user_input="show users")
    result = agent.run(context)

    assert result.success is True
    assert context.intent.type == "query"
    assert context.intent.confidence == 0.95
    assert context.intent.sql == "SELECT * FROM users"
