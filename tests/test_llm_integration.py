"""Integration tests for LLMClient with ContextEnhancer and TableValidator."""

import os
import pytest
from unittest.mock import MagicMock, patch

from src.llm_client import LLMClient


class TestLLMClientWithContext:
    """Test LLMClient with ContextEnhancer integration."""

    @patch.dict(os.environ, {"DASHSCOPE_API_KEY": "sk-test"})
    @patch.dict(os.environ, {"DISABLE_RETRIEVAL": "1"})
    def test_slot_tracker_extracts_plate(self):
        """Test that SlotTracker extracts plate numbers from queries."""
        client = LLMClient()

        # Test plate extraction
        slots = client.slot_tracker.extract("查询车牌沪BAB1565的信息")
        assert slots["plate"] == "沪BAB1565"

    @patch.dict(os.environ, {"DASHSCOPE_API_KEY": "sk-test"})
    @patch.dict(os.environ, {"DISABLE_RETRIEVAL": "1"})
    def test_query_rewriter_substitutes_pronouns(self):
        """Test that QueryRewriter substitutes pronouns with context values."""
        client = LLMClient()

        # Test pronoun substitution
        context = {"plate": "沪BAB1565"}
        rewritten = client.query_rewriter.rewrite("这辆车3月出入过哪些园区", context)
        assert "沪BAB1565" in rewritten
        assert "这辆车" not in rewritten

    @patch.dict(os.environ, {"DASHSCOPE_API_KEY": "sk-test"})
    @patch.dict(os.environ, {"DISABLE_RETRIEVAL": "1"})
    @patch("dashscope.Generation.call")
    def test_generate_sql_with_context(self, mock_call):
        """Test generate_sql with context parameter."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_choice = MagicMock()
        mock_choice.message.content = '''{
            "sql": "SELECT * FROM plates WHERE plate_number = '沪BAB1565'",
            "filename": "plate_query",
            "sheet_name": "车牌查询",
            "reasoning": "查询指定车牌"
        }'''

        mock_response.output.choices = [mock_choice]
        mock_call.return_value = mock_response

        client = LLMClient()
        context = {"plate": "沪BAB1565"}
        result = client.generate_sql("这辆车3月出入过哪些园区", "schema", context=context)

        # Verify the query was processed
        assert result["sql"] is not None

    @patch.dict(os.environ, {"DASHSCOPE_API_KEY": "sk-test"})
    @patch.dict(os.environ, {"DISABLE_RETRIEVAL": "1"})
    @patch("dashscope.Generation.call")
    def test_generate_sql_with_auto_extracted_plate(self, mock_call):
        """Test that plate numbers are auto-extracted from query."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_choice = MagicMock()
        mock_choice.message.content = '''{
            "sql": "SELECT * FROM plates WHERE plate = '沪ABC1234'",
            "filename": "plate_query",
            "sheet_name": "车牌查询",
            "reasoning": "查询车牌"
        }'''

        mock_response.output.choices = [mock_choice]
        mock_call.return_value = mock_response

        client = LLMClient()
        # Query contains plate number
        result = client.generate_sql("查询沪ABC1234的停车记录", "schema")

        # The slot tracker should have extracted the plate
        assert result["sql"] is not None


class TestLLMClientWithTableValidator:
    """Test LLMClient with TableValidator integration."""

    @patch.dict(os.environ, {"DASHSCOPE_API_KEY": "sk-test"})
    @patch.dict(os.environ, {"DISABLE_RETRIEVAL": "1"})
    def test_table_validator_initialization(self):
        """Test TableValidator is initialized with allowed tables."""
        client = LLMClient(allowed_tables=["users", "orders", "products"])

        assert client.table_validator is not None
        assert client.table_validator.allowed_tables == {"users", "orders", "products"}

    @patch.dict(os.environ, {"DASHSCOPE_API_KEY": "sk-test"})
    @patch.dict(os.environ, {"DISABLE_RETRIEVAL": "1"})
    def test_table_validator_without_allowed_tables(self):
        """Test that validator is None when no allowed tables provided."""
        client = LLMClient()

        assert client.table_validator is None

    @patch.dict(os.environ, {"DASHSCOPE_API_KEY": "sk-test"})
    @patch.dict(os.environ, {"DISABLE_RETRIEVAL": "1"})
    @patch("dashscope.Generation.call")
    def test_generate_sql_with_valid_table(self, mock_call):
        """Test SQL generation with valid table passes validation."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_choice = MagicMock()
        mock_choice.message.content = '''{
            "sql": "SELECT * FROM users WHERE id = 1",
            "filename": "user_query",
            "sheet_name": "用户查询",
            "reasoning": "查询用户"
        }'''

        mock_response.output.choices = [mock_choice]
        mock_call.return_value = mock_response

        client = LLMClient(allowed_tables=["users", "orders"])
        result = client.generate_sql("查询用户", "schema")

        assert result["sql"] == "SELECT * FROM users WHERE id = 1"
        assert result["intent"] == "query"

    @patch.dict(os.environ, {"DASHSCOPE_API_KEY": "sk-test"})
    @patch.dict(os.environ, {"DISABLE_RETRIEVAL": "1"})
    @patch("dashscope.Generation.call")
    def test_generate_sql_with_invalid_table(self, mock_call):
        """Test SQL generation with invalid table fails validation."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_choice = MagicMock()
        mock_choice.message.content = '''{
            "sql": "SELECT * FROM products WHERE id = 1",
            "filename": "product_query",
            "sheet_name": "产品查询",
            "reasoning": "查询产品"
        }'''

        mock_response.output.choices = [mock_choice]
        mock_call.return_value = mock_response

        client = LLMClient(allowed_tables=["users", "orders"])
        result = client.generate_sql("查询产品", "schema")

        # Should return error result
        assert result["sql"] is None
        assert result["intent"] == "error"
        assert "products" in str(result["warnings"])

    @patch.dict(os.environ, {"DASHSCOPE_API_KEY": "sk-test"})
    @patch.dict(os.environ, {"DISABLE_RETRIEVAL": "1"})
    @patch("dashscope.Generation.call")
    def test_generate_sql_with_join_multiple_tables(self, mock_call):
        """Test SQL generation with JOIN across allowed tables."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_choice = MagicMock()
        mock_choice.message.content = '''{
            "sql": "SELECT u.*, o.id FROM users u JOIN orders o ON u.id = o.user_id",
            "filename": "user_orders",
            "sheet_name": "用户订单",
            "reasoning": "查询用户和订单"
        }'''

        mock_response.output.choices = [mock_choice]
        mock_call.return_value = mock_response

        client = LLMClient(allowed_tables=["users", "orders"])
        result = client.generate_sql("查询用户订单", "schema")

        # Should pass validation
        assert result["sql"] is not None
        assert result["intent"] == "query"

    @patch.dict(os.environ, {"DASHSCOPE_API_KEY": "sk-test"})
    @patch.dict(os.environ, {"DISABLE_RETRIEVAL": "1"})
    @patch("dashscope.Generation.call")
    def test_generate_sql_case_insensitive_table_validation(self, mock_call):
        """Test that table validation is case-insensitive."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_choice = MagicMock()
        mock_choice.message.content = '''{
            "sql": "SELECT * FROM USERS WHERE id = 1",
            "filename": "user_query",
            "sheet_name": "用户查询",
            "reasoning": "查询用户"
        }'''

        mock_response.output.choices = [mock_choice]
        mock_call.return_value = mock_response

        client = LLMClient(allowed_tables=["users", "orders"])
        result = client.generate_sql("查询用户", "schema")

        # Should pass validation (case insensitive)
        assert result["sql"] is not None


class TestLLMClientIntegration:
    """Test full integration of ContextEnhancer and TableValidator."""

    @patch.dict(os.environ, {"DASHSCOPE_API_KEY": "sk-test"})
    @patch.dict(os.environ, {"DISABLE_RETRIEVAL": "1"})
    @patch("dashscope.Generation.call")
    def test_full_integration_with_context_and_validation(self, mock_call):
        """Test full integration: context enhancement + table validation."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_choice = MagicMock()
        mock_choice.message.content = '''{
            "sql": "SELECT * FROM cloud_fixed_plate WHERE plate_no = '沪BAB1565'",
            "filename": "plate_query",
            "sheet_name": "车牌查询",
            "reasoning": "查询指定车牌"
        }'''

        mock_response.output.choices = [mock_choice]
        mock_call.return_value = mock_response

        client = LLMClient(allowed_tables=["cloud_fixed_plate", "parking_records"])
        context = {"plate": "沪BAB1565"}

        result = client.generate_sql("这辆车3月出入过哪些园区", "schema", context=context)

        # Should succeed with both context enhancement and table validation
        assert result["sql"] is not None
        assert result["intent"] == "query"

    @patch.dict(os.environ, {"DASHSCOPE_API_KEY": "sk-test"})
    @patch.dict(os.environ, {"DISABLE_RETRIEVAL": "1"})
    def test_context_components_initialized(self):
        """Test that context components are properly initialized."""
        client = LLMClient()

        assert client.slot_tracker is not None
        assert client.query_rewriter is not None
        assert isinstance(client.slot_tracker.extract("沪A12345"), dict)
