"""
单元测试: LLMClient 结构化输出功能

遵循 TDD 原则: 先写失败测试，再实现功能
"""
import json
import pytest
from unittest.mock import Mock, patch, MagicMock

from src.llm_client import LLMClient


class TestStructuredOutputConfig:
    """测试结构化输出配置开关"""

    def test_default_structured_output_disabled(self):
        """默认情况下结构化输出应禁用"""
        client = LLMClient()
        assert client.enable_structured_output is False

    def test_structured_output_enabled_via_env(self, monkeypatch):
        """通过环境变量启用结构化输出"""
        monkeypatch.setenv("ENABLE_STRUCTURED_OUTPUT", "1")
        client = LLMClient()
        assert client.enable_structured_output is True

    def test_thinking_and_structured_mutual_exclusion(self, monkeypatch):
        """测试 thinking 和 structured 互斥 - 同时启用时应有警告或处理"""
        monkeypatch.setenv("ENABLE_STRUCTURED_OUTPUT", "1")
        monkeypatch.setenv("ENABLE_THINKING", "1")
        client = LLMClient()
        # 同时启用时，应该有一个优先级策略
        # 当前实现应至少能处理这种情况
        assert client.enable_structured_output is True
        assert client.enable_thinking is True


class TestStructuredOutputJsonSchema:
    """测试 JSON Schema 模式结构化输出"""

    @pytest.fixture
    def mock_schema_response(self):
        """模拟结构化输出响应"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.output = Mock()
        mock_response.output.choices = [
            Mock(message=Mock(content=json.dumps({
                "sql": "SELECT * FROM users WHERE id = 1",
                "filename": "users_query",
                "sheet_name": "Sheet1",
                "reasoning": "查询特定用户信息",
                "intent": "query",
                "preview_sql": None,
                "key_columns": [],
                "warnings": []
            })))
        ]
        return mock_response

    def test_generate_sql_with_json_schema(self, mock_schema_response):
        """测试使用 JSON Schema 生成 SQL"""
        client = LLMClient()
        client.enable_structured_output = True

        with patch("src.llm_client.Generation.call", return_value=mock_schema_response):
            result = client.generate_sql(
                user_query="查询用户ID为1的信息",
                schema_context="CREATE TABLE users (id INT, name VARCHAR(100))"
            )

        assert result["sql"] == "SELECT * FROM users WHERE id = 1"
        assert result["filename"] == "users_query"
        assert result["intent"] == "query"

    def test_generate_sql_with_json_object(self, mock_schema_response):
        """测试使用 JSON Object 模式生成 SQL"""
        client = LLMClient()
        client.enable_structured_output = True
        # JSON Object 模式不指定 schema

        with patch("src.llm_client.Generation.call", return_value=mock_schema_response):
            result = client.generate_sql(
                user_query="查询用户信息",
                schema_context="CREATE TABLE users (id INT, name VARCHAR(100))"
            )

        assert "sql" in result
        assert result["sql"] is not None

    def test_structured_output_response_format(self, mock_schema_response):
        """测试结构化输出时 API 调用包含正确的 response_format"""
        client = LLMClient()
        client.enable_structured_output = True

        with patch("src.llm_client.Generation.call") as mock_call:
            mock_call.return_value = mock_schema_response
            client.generate_sql(
                user_query="查询用户信息",
                schema_context="CREATE TABLE users (id INT)"
            )

            # 验证调用参数包含 response_format
            call_kwargs = mock_call.call_args.kwargs
            assert "response_format" in call_kwargs
            assert call_kwargs["response_format"]["type"] == "json_object"


class TestStructuredOutputErrorHandling:
    """测试结构化输出错误处理"""

    def test_json_parse_error_observability(self):
        """测试 JSON 解析失败时输出可观测错误"""
        client = LLMClient()
        client.enable_structured_output = True

        # 模拟返回无效的 JSON
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.output = Mock()
        mock_response.output.choices = [
            Mock(message=Mock(content="这不是有效的 JSON"))
        ]

        with patch("src.llm_client.Generation.call", return_value=mock_response):
            # 应该抛出异常或返回包含错误信息的结果
            with pytest.raises(Exception) as exc_info:
                client.generate_sql(
                    user_query="查询用户信息",
                    schema_context="CREATE TABLE users (id INT)"
                )

            # 错误信息应包含 JSON 解析相关信息
            error_str = str(exc_info.value).lower()
            assert "json" in error_str or "expecting value" in error_str or "decode" in error_str

    def test_malformed_json_response(self):
        """测试格式错误但可部分解析的 JSON"""
        client = LLMClient()
        client.enable_structured_output = True

        # 模拟返回部分有效的 JSON（缺少必需字段）
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.output = Mock()
        mock_response.output.choices = [
            Mock(message=Mock(content=json.dumps({
                "sql": "SELECT * FROM users"
                # 缺少其他必需字段
            })))
        ]

        with patch("src.llm_client.Generation.call", return_value=mock_response):
            result = client.generate_sql(
                user_query="查询用户信息",
                schema_context="CREATE TABLE users (id INT)"
            )

            # 应使用默认值填充缺失字段
            assert result["sql"] == "SELECT * FROM users"
            # 验证设置了默认值
            assert "intent" in result  # intent 有默认值


class TestBackwardCompatibility:
    """测试向后兼容性"""

    def test_existing_generate_sql_returns_expected_structure(self):
        """测试现有 generate_sql 返回结构不被破坏"""
        client = LLMClient()
        # 不启用结构化输出，保持原有行为
        client.enable_structured_output = False

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

            # 验证返回结构完整
            required_keys = ["sql", "filename", "sheet_name", "reasoning", "intent", "preview_sql", "key_columns", "warnings"]
            for key in required_keys:
                assert key in result, f"缺少必需字段: {key}"

    def test_recognize_intent_backward_compatibility(self):
        """测试 recognize_intent 返回结构不被破坏"""
        client = LLMClient()
        client.enable_structured_output = False

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

            required_keys = ["operation_id", "confidence", "params", "fallback_sql", "reasoning", "missing_params", "suggestions"]
            for key in required_keys:
                assert key in result, f"缺少必需字段: {key}"
