"""Tests for SQL generator schema handling."""
import pytest
from unittest.mock import Mock
from sqlalchemy.exc import SQLAlchemyError
from src.web.services.sql_generator import SQLGenerator


class TestBuildTableContext:
    """Test _build_table_context with cross-db table names."""

    @pytest.fixture
    def mock_db(self):
        from src.db_manager import DatabaseManager
        mock = Mock(spec=DatabaseManager)
        return mock

    def test_cross_db_table_names(self, mock_db):
        """Test that cross-db table names are handled correctly."""
        mock_db.get_table_schema_cross_db.return_value = [
            {"name": "id", "type": "int", "comment": "ID"},
        ]

        generator = SQLGenerator(db_manager=mock_db)
        context = generator._build_table_context(["parkcloud.users"])

        mock_db.get_table_schema_cross_db.assert_called_once_with("parkcloud", "users")
        assert "parkcloud.users" in context

    def test_mixed_table_names(self, mock_db):
        """Test mixed simple and cross-db table names."""
        mock_db.get_table_schema_cross_db.return_value = [{"name": "id", "type": "int"}]
        mock_db.get_table_schema.return_value = [{"name": "id", "type": "int"}]

        generator = SQLGenerator(db_manager=mock_db)
        context = generator._build_table_context(["parkcloud.users", "orders"])

        mock_db.get_table_schema_cross_db.assert_called_once_with("parkcloud", "users")
        mock_db.get_table_schema.assert_called_once_with("orders")

    def test_invalid_table_names_skipped(self, mock_db, caplog):
        """Test invalid table names are skipped with warning."""
        import logging
        generator = SQLGenerator(db_manager=mock_db)

        with caplog.at_level(logging.WARNING):
            context = generator._build_table_context(["invalid-name"])

        # Should skip invalid name and log warning
        assert "Invalid" in caplog.text or context == ""
        mock_db.get_table_schema.assert_not_called()