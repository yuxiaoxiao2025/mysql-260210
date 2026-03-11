from unittest.mock import MagicMock
from src.agents.orchestrator import Orchestrator
from src.agents.context import IntentModel
from src.agents.models import AgentResult


def test_orchestrator_review_ask_user_stops_before_execution():
    mock_intent = MagicMock()
    mock_retrieval = MagicMock()
    mock_security = MagicMock()
    mock_execution = MagicMock()
    mock_review = MagicMock()

    def intent_side_effect(context):
        context.intent = IntentModel(type="mutation", confidence=1.0, sql="DELETE FROM users")
        return AgentResult(success=True)

    mock_intent.run.side_effect = intent_side_effect
    mock_retrieval.run.return_value = AgentResult(success=True)
    mock_security.run.return_value = AgentResult(success=True)
    mock_review.run.return_value = AgentResult(success=True, next_action="ask_user", message="confirm")

    orch = Orchestrator(
        intent_agent=mock_intent,
        retrieval_agent=mock_retrieval,
        security_agent=mock_security,
        preview_agent=MagicMock(),
        execution_agent=mock_execution,
        review_agent=mock_review,
        knowledge_agent=MagicMock(),
    )

    context = orch.process("delete users")
    assert "review" in context.step_history
    mock_execution.run.assert_not_called()
