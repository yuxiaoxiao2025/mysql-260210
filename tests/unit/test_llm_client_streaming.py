from unittest.mock import MagicMock, patch
from src.llm_client import LLMClient


def test_chat_stream_with_thinking():
    client = LLMClient()

    with patch.object(client, "client") as mock_openai:
        mock_stream = MagicMock()

        chunk1 = MagicMock()
        chunk1.choices = [MagicMock(delta=MagicMock(reasoning_content="Thinking...", content=None))]

        chunk2 = MagicMock()
        chunk2.choices = [MagicMock(delta=MagicMock(reasoning_content=None, content="Hello"))]

        mock_stream.__iter__.return_value = [chunk1, chunk2]
        mock_openai.chat.completions.create.return_value = mock_stream

        generator = client.chat_stream(
            messages=[{"role": "user", "content": "hi"}],
            enable_thinking=True
        )

        results = list(generator)
        assert len(results) == 2
        assert results[0]["type"] == "thinking"
        assert results[0]["content"] == "Thinking..."
        assert results[1]["type"] == "content"
        assert results[1]["content"] == "Hello"

        mock_openai.chat.completions.create.assert_called_with(
            model="qwen-plus",
            messages=[{"role": "user", "content": "hi"}],
            stream=True,
            extra_body={"enable_thinking": True},
            stream_options={"include_usage": True}
        )
