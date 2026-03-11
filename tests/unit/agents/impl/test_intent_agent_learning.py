from unittest.mock import MagicMock
from src.agents.impl.intent_agent import IntentAgent
from src.agents.context import AgentContext
from src.agents.config import IntentAgentConfig


def test_intent_agent_clarification():
    mock_recognizer = MagicMock()
    mock_recognizer.recognize.return_value.is_matched = False
    mock_recognizer.recognize.return_value.reasoning = "Unknown concept: 'ROI'"
    mock_recognizer.recognize.return_value.operation_id = None
    mock_recognizer.recognize.return_value.confidence = 0.0
    mock_recognizer.recognize.return_value.params = {}
    mock_recognizer.recognize.return_value.fallback_sql = None
    mock_recognizer.recognize.return_value.missing_params = []

    agent = IntentAgent(IntentAgentConfig(name="intent"), llm_client=MagicMock(), knowledge_loader=MagicMock())
    agent.recognizer = mock_recognizer

    context = AgentContext(user_input="Calculate ROI")
    result = agent.run(context)

    assert result.success is True
    assert context.intent.need_clarify is True
    assert "ROI" in context.intent.reasoning
