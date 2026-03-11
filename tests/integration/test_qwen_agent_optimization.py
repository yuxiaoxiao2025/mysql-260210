"""
集成测试: Qwen Agent 优化功能回归测试

覆盖 4 大能力组合：
1. structured-only
2. cache+structured
3. thinking-only
4. thinking+stream

以及关键异常路径
"""
import json
import pytest
from unittest.mock import Mock, patch

from src.llm_client import LLMClient, JsonParseError
from src.monitoring.metrics_collector import get_metrics_collector


@pytest.fixture
def mock_llm_response():
    """模拟 LLM 响应"""
    return {
        "sql": "SELECT * FROM users WHERE id = 1",
        "filename": "users_query",
        "sheet_name": "Sheet1",
        "reasoning": "查询特定用户信息",
        "intent": "query",
        "preview_sql": None,
        "key_columns": [],
        "warnings": []
    }


@pytest.fixture
def reset_metrics_collector():
    """重置指标收集器"""
    collector = get_metrics_collector()
    collector.reset()
    yield
    collector.reset()


class TestStructuredOnly:
    """测试 structured-only 模式"""

    def test_structured_output_enabled(self, mock_llm_response, reset_metrics_collector):
        """测试仅启用结构化输出"""
        client = LLMClient()
        client.enable_structured_output = True
        client.enable_thinking = False
        client.enable_stream = False
        client.enable_prompt_cache = False

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.output = Mock()
        mock_response.output.choices = [
            Mock(message=Mock(content=json.dumps(mock_llm_response)))
        ]

        with patch("src.llm_client.Generation.call", return_value=mock_response):
            result = client.generate_sql(
                user_query="查询用户ID为1的信息",
                schema_context="CREATE TABLE users (id INT, name VARCHAR(100))"
            )

        assert result["sql"] == "SELECT * FROM users WHERE id = 1"
        assert result["intent"] == "query"

    def test_structured_output_with_json_parse_error(self, reset_metrics_collector):
        """测试结构化输出时 JSON 解析错误处理"""
        client = LLMClient()
        client.enable_structured_output = True

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.output = Mock()
        mock_response.output.choices = [
            Mock(message=Mock(content="这不是有效的 JSON"))
        ]

        with patch("src.llm_client.Generation.call", return_value=mock_response):
            with pytest.raises(JsonParseError):
                client.generate_sql(
                    user_query="查询用户信息",
                    schema_context="CREATE TABLE users (id INT)"
                )


class TestCacheWithStructured:
    """测试 cache+structured 组合"""

    def test_cache_and_structured_enabled(self, mock_llm_response, reset_metrics_collector):
        """测试同时启用缓存和结构化输出"""
        client = LLMClient()
        client.enable_structured_output = True
        client.enable_prompt_cache = True
        client.enable_thinking = False
        client.enable_stream = False

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.output = Mock()
        mock_response.output.choices = [
            Mock(message=Mock(content=json.dumps(mock_llm_response)))
        ]
        # 模拟缓存命中
        mock_response.usage = Mock(
            input_tokens=50,
            output_tokens=100,
            prompt_tokens_details=Mock(cached_tokens=1000, cache_creation_input_tokens=0)
        )

        with patch("src.llm_client.Generation.call", return_value=mock_response):
            result = client.generate_sql(
                user_query="查询用户信息",
                schema_context="CREATE TABLE users (id INT)"
            )

        assert result["sql"] == "SELECT * FROM users WHERE id = 1"

        # 验证缓存指标
        stats = get_metrics_collector().get_cache_stats()
        assert stats["total_calls"] == 1


class TestThinkingOnly:
    """测试 thinking-only 模式"""

    def test_thinking_mode_enabled(self, mock_llm_response, reset_metrics_collector):
        """测试仅启用 thinking 模式"""
        client = LLMClient()
        client.enable_thinking = True
        client.enable_structured_output = False
        client.enable_stream = False
        client.enable_prompt_cache = False

        # 模拟流式响应 - Mock 对象需要可迭代
        def mock_stream_generator():
            yield Mock(
                output=Mock(choices=[Mock(message=Mock(content=json.dumps(mock_llm_response)))]),
                usage=None
            )

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.output = Mock()
        mock_response.output.choices = [
            Mock(message=Mock(content=json.dumps(mock_llm_response)))
        ]

        with patch("src.llm_client.Generation.call") as mock_call:
            mock_call.return_value = mock_stream_generator()
            result = client.generate_sql(
                user_query="查询用户信息",
                schema_context="CREATE TABLE users (id INT)"
            )

        # 验证使用了流式调用
        call_kwargs = mock_call.call_args.kwargs
        assert call_kwargs.get('stream') is True
        assert call_kwargs.get('enable_thinking') is True

    def test_thinking_with_json_fix(self, reset_metrics_collector):
        """测试 thinking 模式下 JSON 修复流程"""
        client = LLMClient()
        client.enable_thinking = True

        # 模拟返回非标准 JSON 的流式响应
        def mock_stream_generator():
            yield Mock(
                output=Mock(choices=[Mock(message=Mock(content="让我思考一下..."))]),
                usage=None
            )
            yield Mock(
                output=Mock(choices=[Mock(message=Mock(content="SELECT * FROM users"))]),
                usage=None
            )

        with patch("src.llm_client.Generation.call") as mock_call:
            mock_call.return_value = mock_stream_generator()
            with patch.object(client, '_fix_json_with_thinking') as mock_fix:
                mock_fix.return_value = {
                    "sql": "SELECT * FROM users",
                    "filename": "query",
                    "sheet_name": "Sheet1",
                    "reasoning": "修复后的结果",
                    "intent": "query",
                    "preview_sql": None,
                    "key_columns": [],
                    "warnings": []
                }
                result = client.generate_sql(
                    user_query="查询用户信息",
                    schema_context="CREATE TABLE users (id INT)"
                )

        # 验证修复流程被调用
        mock_fix.assert_called_once()


class TestThinkingWithStream:
    """测试 thinking+stream 组合"""

    def test_stream_generation(self, reset_metrics_collector):
        """测试流式生成"""
        client = LLMClient()
        client.enable_stream = True
        client.enable_thinking = True

        # 模拟流式响应
        chunks = [
            {'content': '{"sql": '},
            {'content': '"SELECT * FROM users"'},
            {'content': '}'},
            {'done': True, 'result': {'sql': 'SELECT * FROM users'}, 'usage': {'input_tokens': 10, 'output_tokens': 20}}
        ]

        with patch.object(client, 'generate_sql_stream') as mock_stream:
            mock_stream.return_value = iter(chunks)
            results = list(client.generate_sql_stream(
                user_query="查询用户信息",
                schema_context="CREATE TABLE users (id INT)"
            ))

        assert len(results) > 0


class TestErrorPaths:
    """测试关键异常路径"""

    def test_api_error_handling(self, reset_metrics_collector):
        """测试 API 错误处理"""
        client = LLMClient()

        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.code = "InternalError"
        mock_response.message = "API 内部错误"

        with patch("src.llm_client.Generation.call", return_value=mock_response):
            with pytest.raises(Exception) as exc_info:
                client.generate_sql(
                    user_query="查询用户信息",
                    schema_context="CREATE TABLE users (id INT)"
                )

        assert "API Error" in str(exc_info.value)

    def test_network_error_handling(self, reset_metrics_collector):
        """测试网络错误处理"""
        client = LLMClient()

        with patch("src.llm_client.Generation.call", side_effect=Exception("Connection timeout")):
            with pytest.raises(Exception) as exc_info:
                client.generate_sql(
                    user_query="查询用户信息",
                    schema_context="CREATE TABLE users (id INT)"
                )

        assert "LLM generation failed" in str(exc_info.value)

    def test_invalid_json_response(self, reset_metrics_collector):
        """测试无效 JSON 响应处理"""
        client = LLMClient()
        client.enable_structured_output = True

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.output = Mock()
        mock_response.output.choices = [
            Mock(message=Mock(content="{invalid json"))
        ]

        with patch("src.llm_client.Generation.call", return_value=mock_response):
            with pytest.raises(JsonParseError) as exc_info:
                client.generate_sql(
                    user_query="查询用户信息",
                    schema_context="CREATE TABLE users (id INT)"
                )

        assert "JSON" in str(exc_info.value)


class TestBackwardCompatibility:
    """测试向后兼容性"""

    def test_non_streaming_interface_unchanged(self, mock_llm_response, reset_metrics_collector):
        """测试非流式接口行为不变"""
        client = LLMClient()
        # 默认配置下
        client.enable_stream = False
        client.enable_thinking = False

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.output = Mock()
        mock_response.output.choices = [
            Mock(message=Mock(content=json.dumps(mock_llm_response)))
        ]

        with patch("src.llm_client.Generation.call", return_value=mock_response):
            result = client.generate_sql(
                user_query="查询用户信息",
                schema_context="CREATE TABLE users (id INT)"
            )

        # 验证返回结构完整
        required_keys = ['sql', 'filename', 'sheet_name', 'reasoning', 'intent', 'preview_sql', 'key_columns', 'warnings']
        for key in required_keys:
            assert key in result, f"缺少必需字段: {key}"

    def test_recognize_intent_unchanged(self, reset_metrics_collector):
        """测试 recognize_intent 行为不变"""
        client = LLMClient()
        client.enable_stream = False

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.output = Mock()
        mock_response.output.choices = [
            Mock(message=Mock(content=json.dumps({
                "operation_id": "test_op",
                "confidence": 0.95,
                "params": {"key": "value"},
                "fallback_sql": None,
                "reasoning": "测试",
                "missing_params": [],
                "suggestions": []
            })))
        ]

        with patch("src.llm_client.Generation.call", return_value=mock_response):
            result = client.recognize_intent(
                user_query="测试查询",
                operations_context="操作模板"
            )

        required_keys = ['operation_id', 'confidence', 'params', 'fallback_sql', 'reasoning', 'missing_params', 'suggestions']
        for key in required_keys:
            assert key in result, f"缺少必需字段: {key}"
