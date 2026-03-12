"""测试 LLM 工具调用模型"""
import pytest
from src.llm_tool_models import ToolCall, ChatResponse


def test_tool_call_from_openai():
    """测试从 OpenAI 格式创建 ToolCall"""
    class MockFunction:
        name = "test_tool"
        arguments = '{"arg1": "value1"}'

    class MockToolCall:
        id = "call_123"
        function = MockFunction()

    tc = ToolCall.from_openai(MockToolCall())

    assert tc.id == "call_123"
    assert tc.name == "test_tool"
    assert tc.arguments == '{"arg1": "value1"}'


def test_chat_response_has_tool_calls():
    """测试 ChatResponse 工具调用检测"""
    response = ChatResponse(content="test")
    assert not response.has_tool_calls

    tc = ToolCall(id="1", name="tool", arguments="{}")
    response = ChatResponse(content=None, tool_calls=[tc])
    assert response.has_tool_calls


def test_chat_response_default_values():
    """测试 ChatResponse 默认值"""
    response = ChatResponse()
    assert response.content is None
    assert response.tool_calls == []
    assert response.finish_reason == "stop"
    assert not response.has_tool_calls


def test_chat_response_with_multiple_tool_calls():
    """测试 ChatResponse 多个工具调用"""
    tc1 = ToolCall(id="1", name="tool1", arguments='{"a": 1}')
    tc2 = ToolCall(id="2", name="tool2", arguments='{"b": 2}')

    response = ChatResponse(tool_calls=[tc1, tc2], finish_reason="tool_calls")
    assert response.has_tool_calls
    assert len(response.tool_calls) == 2
    assert response.finish_reason == "tool_calls"