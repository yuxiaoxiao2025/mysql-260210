from unittest.mock import MagicMock
from src.agents.impl.knowledge_agent import KnowledgeAgent
from src.agents.context import AgentContext, IntentModel
from src.agents.config import BaseAgentConfig


def test_knowledge_agent_run():
    mock_llm = MagicMock()
    mock_llm.chat_stream.return_value = [
        {"type": "thinking", "content": "Thinking..."},
        {"type": "content", "content": "Answer"},
    ]

    agent = KnowledgeAgent(BaseAgentConfig(name="knowledge"), llm_client=mock_llm)
    context = AgentContext(user_input="ask something")
    context.intent = IntentModel(type="qa", confidence=1.0)
    context.schema_context = "Table: users"

    result = agent.run(context)

    assert result.success is True
    assert hasattr(result.data, "__iter__")
    chunks = list(result.data)
    assert len(chunks) == 2
