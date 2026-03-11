from src.agents.impl.review_agent import ReviewAgent
from src.agents.context import AgentContext, IntentModel
from src.agents.config import ReviewAgentConfig


def test_review_agent_needs_confirmation():
    agent = ReviewAgent(ReviewAgentConfig(name="review"))
    context = AgentContext(user_input="delete users")
    context.intent = IntentModel(type="mutation", sql="DELETE FROM users")
    context.is_safe = True

    result = agent.run(context)

    assert result.success is True
    assert result.next_action == "ask_user"
    assert "DELETE" in result.message
