"""
单元测试: LLMClient 流式输出功能

遵循 TDD 原则: 先写失败测试，再实现功能
"""
import json
import pytest
from unittest.mock import Mock, patch, MagicMock

from src.llm_client import LLMClient


class TestStreamingConfig:
    """测试流式输出配置"""

    def test_default_stream_disabled(self):
        """默认情况下流式输出应禁用"""
        client = LLMClient()
        assert client.enable_stream is False

    def test_stream_enabled_via_env(self, monkeypatch):
        """通过环境变量启用流式输出"""
        monkeypatch.setenv("ENABLE_STREAM", "true")
        client = LLMClient()
        assert client.enable_stream is True


class TestStreamingChunkHandling:
    """测试流式输出 chunk 处理"""

    @pytest.fixture
    def mock_stream_chunks(self):
        """模拟流式输出 chunks"""
        chunks = [
            Mock(output=Mock(choices=[Mock(message=Mock(content='{"sql": "SELECT'))])),
            Mock(output=Mock(choices=[Mock(message=Mock(content=' * FROM users'))])),
            Mock(output=Mock(choices=[Mock(message=Mock(content=' WHERE id = 1",'))])),
            Mock(output=Mock(choices=[Mock(message=Mock(content='"filename": "query"}'))])),
        ]
        return chunks

    def test_stream_chunk_merge(self, mock_stream_chunks):
        """测试流式 chunk 合并"""
        client = LLMClient()
        client.enable_stream = True

        # 模拟流式生成器
        def mock_stream_generator():
            for chunk in mock_stream_chunks:
                yield chunk

        with patch("src.llm_client.Generation.call") as mock_call:
            mock_call.return_value = mock_stream_generator()

            chunks = []
            for chunk in client.generate_sql_stream(
                user_query="查询用户信息",
                schema_context="CREATE TABLE users (id INT)"
            ):
                chunks.append(chunk)

        # 验证收集到所有 chunks
        assert len(chunks) == 4

    def test_stream_with_usage_collection(self):
        """测试流式输出 usage 收集"""
        client = LLMClient()
        client.enable_stream = True

        # 模拟带有 usage 的 chunks
        chunks = [
            Mock(
                output=Mock(choices=[Mock(message=Mock(content='{"sql": "SELECT'))]),
                usage=Mock(input_tokens=10, output_tokens=5)
            ),
            Mock(
                output=Mock(choices=[Mock(message=Mock(content=' * FROM users"}'))]),
                usage=Mock(input_tokens=0, output_tokens=3)
            ),
        ]

        def mock_stream_generator():
            for chunk in chunks:
                yield chunk

        with patch("src.llm_client.Generation.call") as mock_call:
            mock_call.return_value = mock_stream_generator()

            total_usage = {"input_tokens": 0, "output_tokens": 0}
            for chunk in client.generate_sql_stream(
                user_query="查询",
                schema_context="CREATE TABLE users (id INT)"
            ):
                if hasattr(chunk, 'usage') and chunk.usage:
                    total_usage["input_tokens"] += chunk.usage.input_tokens
                    total_usage["output_tokens"] += chunk.usage.output_tokens

        assert total_usage["input_tokens"] == 10
        assert total_usage["output_tokens"] == 8


class TestStreamingSqlGeneration:
    """测试流式 SQL 生成"""

    def test_stream_generate_sql_method_exists(self):
        """测试流式生成 SQL 方法存在"""
        client = LLMClient()
        # 方法应该存在
        assert hasattr(client, 'generate_sql_stream')

    def test_stream_generate_sql_returns_generator(self):
        """测试流式生成返回生成器"""
        client = LLMClient()
        client.enable_stream = True

        mock_response = Mock()
        mock_response.output = Mock(choices=[Mock(message=Mock(content='{"sql": "test"}'))])

        def mock_stream_generator():
            yield mock_response

        with patch("src.llm_client.Generation.call") as mock_call:
            mock_call.return_value = mock_stream_generator()

            result = client.generate_sql_stream(
                user_query="查询",
                schema_context="CREATE TABLE t (id INT)"
            )
            # 结果应该是生成器
            assert hasattr(result, '__iter__')
            assert hasattr(result, '__next__')


class TestStreamingWithThinking:
    """测试流式输出与深度思考结合"""

    def test_stream_with_thinking_enabled(self):
        """测试启用 thinking 时走流式输出"""
        client = LLMClient()
        client.enable_stream = True
        client.enable_thinking = True

        # 模拟 thinking 和普通响应 chunks
        chunks = [
            Mock(
                output=Mock(choices=[
                    Mock(
                        message=Mock(content='让我思考一下'),
                        finish_reason=None
                    )
                ]),
                usage=None
            ),
            Mock(
                output=Mock(choices=[
                    Mock(
                        content='{"sql": "SELECT * FROM users"}',
                        finish_reason='stop'
                    )
                ]),
                usage=Mock(input_tokens=20, output_tokens=15)
            ),
        ]

        def mock_stream_generator():
            for chunk in chunks:
                yield chunk

        with patch("src.llm_client.Generation.call") as mock_call:
            mock_call.return_value = mock_stream_generator()

            # 应该能处理 thinking 模式
            collected = list(client.generate_sql_stream(
                user_query="查询用户",
                schema_context="CREATE TABLE users (id INT)"
            ))

            assert len(collected) == 2


class TestStreamingErrorHandling:
    """测试流式输出错误处理"""

    def test_stream_interrupt_handling(self):
        """测试客户端中断时安全收尾"""
        client = LLMClient()
        client.enable_stream = True

        def mock_stream_generator():
            yield Mock(output=Mock(choices=[Mock(message=Mock(content='{"sql": "'))]))
            # 模拟中断
            raise GeneratorExit("客户端中断")

        with patch("src.llm_client.Generation.call") as mock_call:
            mock_call.return_value = mock_stream_generator()

            try:
                for _ in client.generate_sql_stream(
                    user_query="查询",
                    schema_context="CREATE TABLE t (id INT)"
                ):
                    pass
            except GeneratorExit:
                pass  # 预期中的异常

            # 应该安全处理，不抛出未捕获异常

    def test_stream_api_error_handling(self):
        """测试流式 API 错误处理"""
        client = LLMClient()
        client.enable_stream = True

        def mock_stream_generator():
            yield Mock(output=Mock(choices=[Mock(message=Mock(content='{"sql": "'))]))
            raise Exception("API 错误")

        with patch("src.llm_client.Generation.call") as mock_call:
            mock_call.return_value = mock_stream_generator()

            with pytest.raises(Exception) as exc_info:
                for _ in client.generate_sql_stream(
                    user_query="查询",
                    schema_context="CREATE TABLE t (id INT)"
                ):
                    pass

            assert "API" in str(exc_info.value) or "stream" in str(exc_info.value).lower()


class TestStreamChunkFormat:
    """测试流式 chunk 格式"""

    def test_chunk_contains_required_fields(self):
        """测试 chunk 包含必需字段"""
        client = LLMClient()
        client.enable_stream = True

        mock_chunk = Mock()
        mock_chunk.output = Mock()
        mock_chunk.output.choices = [
            Mock(
                message=Mock(content='{"sql": "SELECT 1"}'),
                finish_reason=None
            )
        ]
        mock_chunk.usage = Mock(input_tokens=10, output_tokens=5)

        def mock_stream_generator():
            yield mock_chunk

        with patch("src.llm_client.Generation.call") as mock_call:
            mock_call.return_value = mock_stream_generator()

            for chunk in client.generate_sql_stream(
                user_query="查询",
                schema_context="CREATE TABLE t (id INT)"
            ):
                # chunk 应该有 output 字段
                assert hasattr(chunk, 'output')
                assert hasattr(chunk.output, 'choices')


class TestNonStreamingInterfaceUnchanged:
    """测试非流式接口保持不变"""

    def test_non_stream_generate_sql_unchanged(self):
        """测试非流式 generate_sql 行为不变"""
        client = LLMClient()
        client.enable_stream = False

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.output = Mock()
        mock_response.output.choices = [
            Mock(message=Mock(content=json.dumps({
                "sql": "SELECT * FROM users",
                "filename": "query",
                "sheet_name": "Sheet1",
                "reasoning": "测试",
                "intent": "query",
                "preview_sql": None,
                "key_columns": [],
                "warnings": []
            })))
        ]

        with patch("src.llm_client.Generation.call", return_value=mock_response):
            result = client.generate_sql(
                user_query="查询用户",
                schema_context="CREATE TABLE users (id INT)"
            )

            # 非流式调用应返回完整结果
            assert isinstance(result, dict)
            assert result["sql"] == "SELECT * FROM users"
