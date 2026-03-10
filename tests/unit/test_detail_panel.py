"""Tests for detail_panel component."""
import sys
import importlib.util
import pytest
from unittest.mock import Mock, patch
import logging
from sqlalchemy.exc import SQLAlchemyError, NoSuchTableError

# Direct import to avoid package __init__.py which has streamlit dependency issues
spec = importlib.util.spec_from_file_location(
    "detail_panel",
    "E:/trae-pc/mysql260227/.worktrees/fix-detail-panel/src/web/components/detail_panel.py"
)
detail_panel_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(detail_panel_module)

get_table_columns = detail_panel_module.get_table_columns
_validate_identifier = detail_panel_module._validate_identifier


class TestValidateIdentifier:
    """Test _validate_identifier helper function."""

    @pytest.mark.parametrize("name,expected", [
        ("users", True),
        ("_users", True),
        ("Users123", True),
        ("parkcloud", True),
        ("", False),
        ("123users", False),  # Starts with number
        ("users-name", False),  # Contains hyphen
        ("users.name", False),  # Contains dot
        ("a" * 65, False),  # Too long (>64)
        ("a" * 64, True),  # Max length
    ])
    def test_validate_identifier(self, name, expected):
        assert _validate_identifier(name) == expected


class TestGetTableColumns:
    """Test get_table_columns function with various table name formats."""

    @pytest.fixture
    def mock_db(self):
        """Create mock DatabaseManager with spec."""
        from src.db_manager import DatabaseManager
        mock = Mock(spec=DatabaseManager)
        mock.get_table_schema_cross_db.return_value = []
        mock.get_table_schema.return_value = []
        return mock

    @pytest.mark.parametrize("table_name,expected_method,expected_args", [
        ("parkcloud.users", "get_table_schema_cross_db", ("parkcloud", "users")),
        ("users", "get_table_schema", ("users",)),
        ("a.b.c", "get_table_schema_cross_db", ("a", "b.c")),  # partition splits on first dot
    ])
    def test_table_name_parsing(self, mock_db, table_name, expected_method, expected_args):
        """Test table name parsing with parametrization."""
        # Set up return value for the expected method
        getattr(mock_db, expected_method).return_value = [
            {"name": "id", "type": "int", "comment": "PK"}
        ]

        result = get_table_columns(mock_db, table_name)

        # Verify correct method was called
        getattr(mock_db, expected_method).assert_called_once_with(*expected_args)
        assert len(result) == 1

    def test_schema_table_format_calls_cross_db(self, mock_db):
        """Test 'schema.table' format uses cross-db method."""
        mock_db.get_table_schema_cross_db.return_value = [
            {"name": "id", "type": "int", "comment": "PK"}
        ]

        result = get_table_columns(mock_db, "parkcloud.plate_icbc_agreement")

        mock_db.get_table_schema_cross_db.assert_called_once_with(
            "parkcloud", "plate_icbc_agreement"
        )
        mock_db.get_table_schema.assert_not_called()
        assert result[0]["name"] == "id"

    def test_simple_table_format_calls_standard(self, mock_db):
        """Test simple table name uses standard method."""
        mock_db.get_table_schema.return_value = [
            {"name": "id", "type": "int", "comment": "PK"}
        ]

        result = get_table_columns(mock_db, "users")

        mock_db.get_table_schema.assert_called_once_with("users")
        mock_db.get_table_schema_cross_db.assert_not_called()

    @pytest.mark.parametrize("invalid_name", [
        "",           # Empty string
        None,         # None
        123,          # Non-string
        "schema.",    # Trailing dot (empty table name)
        ".table",     # Leading dot (empty schema)
    ])
    def test_invalid_table_names(self, mock_db, invalid_name):
        """Test invalid table names return empty list."""
        result = get_table_columns(mock_db, invalid_name)
        assert result == []
        mock_db.get_table_schema.assert_not_called()
        mock_db.get_table_schema_cross_db.assert_not_called()

    def test_sqlalchemy_error_handling(self, mock_db):
        """Test SQLAlchemy errors are handled gracefully."""
        mock_db.get_table_schema_cross_db.side_effect = SQLAlchemyError("DB Error")

        result = get_table_columns(mock_db, "parkcloud.nonexistent")

        assert result == []

    def test_no_such_table_error(self, mock_db):
        """Test NoSuchTableError is handled gracefully."""
        mock_db.get_table_schema.side_effect = NoSuchTableError("Not found")

        result = get_table_columns(mock_db, "nonexistent")

        assert result == []


class TestGetTableColumnsEdgeCases:
    """Edge case tests for get_table_columns."""

    def test_logging_on_error(self, caplog):
        """Test that errors are logged."""
        mock_db = Mock()
        mock_db.get_table_schema.side_effect = SQLAlchemyError("DB Error")

        with caplog.at_level(logging.WARNING):
            get_table_columns(mock_db, "invalid_table")

        assert "Database error" in caplog.text