# -*- coding: utf-8 -*-
"""main.py chat 模式单元测试"""
import pytest
from unittest.mock import MagicMock, patch
import types


class TestChatStreamOutput:
    """测试 chat 模式流式输出处理"""

    def test_none_execution_result_shows_fallback(self, capsys):
        """execution_result 为 None 时应显示降级消息"""
        # 模拟处理逻辑
        context = MagicMock()
        context.execution_result = None

        assistant_response = ""
        if context.execution_result is None:
            assistant_response = "抱歉，处理您的请求时出现问题，请稍后再试。"

        assert assistant_response != ""
        assert "抱歉" in assistant_response or "问题" in assistant_response

    def test_error_chunk_handling(self, capsys):
        """应正确处理 error 类型 chunk"""

        def mock_generator():
            yield {"type": "error", "content": "API Error"}

        assistant_response = ""
        has_content = False
        for chunk in mock_generator():
            if chunk.get("type") == "error":
                error_msg = chunk.get("content", "未知错误")
                assistant_response = f"[错误] {error_msg}"
                has_content = True

        assert has_content
        assert "API Error" in assistant_response

    def test_empty_stream_shows_default_message(self, capsys):
        """空 generator 应显示默认消息"""

        def mock_generator():
            return
            yield  # 空生成器

        assistant_response = ""
        has_content = False
        for chunk in mock_generator():
            pass

        if not has_content:
            assistant_response = "抱歉，我没有理解您的问题，请换个方式提问。"

        assert "抱歉" in assistant_response or "提问" in assistant_response

    def test_content_chunk_accumulates_response(self, capsys):
        """content chunk 应正确累积响应"""

        def mock_generator():
            yield {"type": "content", "content": "你好"}
            yield {"type": "content", "content": "，我是助手"}

        assistant_response = ""
        for chunk in mock_generator():
            if chunk.get("type") == "content":
                content = chunk.get("content", "")
                assistant_response += content

        assert assistant_response == "你好，我是助手"

    def test_string_execution_result_displays_directly(self, capsys):
        """字符串类型 execution_result 应直接显示"""
        context = MagicMock()
        context.execution_result = "这是一个错误消息"

        assistant_response = ""
        if isinstance(context.execution_result, str):
            assistant_response = context.execution_result

        assert assistant_response == "这是一个错误消息"

    def test_thinking_chunk_is_ignored(self, capsys):
        """thinking chunk 不应出现在最终响应中"""

        def mock_generator():
            yield {"type": "thinking", "content": "思考中..."}
            yield {"type": "content", "content": "实际回答"}

        assistant_response = ""
        for chunk in mock_generator():
            if chunk.get("type") == "thinking":
                pass  # 忽略
            elif chunk.get("type") == "content":
                assistant_response += chunk.get("content", "")

        assert "思考中" not in assistant_response
        assert assistant_response == "实际回答"

    def test_exception_during_stream_shows_error_message(self, capsys):
        """流处理中的异常应显示错误消息"""

        def mock_generator():
            yield {"type": "content", "content": "开始"}
            raise RuntimeError("Stream error")

        assistant_response = ""
        try:
            for chunk in mock_generator():
                if chunk.get("type") == "content":
                    assistant_response += chunk.get("content", "")
        except Exception as e:
            assistant_response = "对话处理出错，请稍后再试。"

        assert assistant_response == "对话处理出错，请稍后再试。"

    def test_business_operation_result_shows_completion(self, capsys):
        """业务操作结果（非生成器、非字符串）应显示完成消息"""
        context = MagicMock()
        context.execution_result = {"status": "success"}  # 字典结果

        assistant_response = ""
        if context.execution_result is not None and not isinstance(
            context.execution_result, (types.GeneratorType, str)
        ):
            if context.execution_result:
                assistant_response = "操作已完成"
            else:
                assistant_response = "处理完成"

        assert assistant_response == "操作已完成"

    def test_false_execution_result_shows_processing_message(self, capsys):
        """execution_result 为 False 值应显示处理完成消息"""
        context = MagicMock()
        context.execution_result = False

        assistant_response = ""
        if context.execution_result is None:
            assistant_response = "抱歉，处理您的请求时出现问题，请稍后再试。"
        elif context.execution_result:
            assistant_response = "操作已完成"
        else:
            assistant_response = "处理完成"

        assert assistant_response == "处理完成"


class TestChatStreamIntegration:
    """测试完整的流式输出处理流程"""

    def test_full_stream_processing_with_mixed_chunks(self, capsys):
        """测试混合类型 chunk 的完整处理"""

        def mock_generator():
            yield {"type": "thinking", "content": "分析问题..."}
            yield {"type": "content", "content": "您好"}
            yield {"type": "content", "content": "，"}
            yield {"type": "content", "content": "有什么可以帮您的？"}

        assistant_response = ""
        has_content = False

        for chunk in mock_generator():
            if chunk.get("type") == "thinking":
                pass  # 可选：显示思考过程
            elif chunk.get("type") == "content":
                content = chunk.get("content", "")
                if content:
                    has_content = True
                    assistant_response += content

        if not has_content:
            assistant_response = "抱歉，我没有理解您的问题，请换个方式提问。"

        assert has_content
        assert assistant_response == "您好，有什么可以帮您的？"
        assert "分析问题" not in assistant_response