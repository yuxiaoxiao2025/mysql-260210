"""Tests for table constraint validator."""

import pytest

from src.constraint.table_validator import TableValidator


class TestTableValidator:
    """Test cases for TableValidator."""

    def test_validate_sql_with_allowed_tables_only(self):
        """Test SQL with only allowed tables passes validation."""
        validator = TableValidator(allowed_tables=["users", "orders"])
        is_valid, error = validator.validate("SELECT * FROM users")

        assert is_valid is True
        assert error is None

    def test_validate_sql_with_disallowed_table(self):
        """Test SQL with disallowed table fails validation."""
        validator = TableValidator(allowed_tables=["users", "orders"])
        is_valid, error = validator.validate(
            "SELECT * FROM users JOIN products ON users.id = products.user_id"
        )

        assert is_valid is False
        assert "products" in error

    def test_validate_sql_with_multiple_disallowed_tables(self):
        """Test SQL with multiple disallowed tables reports first violation."""
        validator = TableValidator(allowed_tables=["users"])
        is_valid, error = validator.validate(
            "SELECT * FROM products JOIN orders ON products.id = orders.product_id"
        )

        assert is_valid is False
        assert "products" in error

    def test_validate_sql_with_subquery(self):
        """Test SQL with subquery extracts all table names."""
        validator = TableValidator(allowed_tables=["users", "orders"])
        is_valid, error = validator.validate(
            "SELECT * FROM users WHERE id IN (SELECT user_id FROM products)"
        )

        assert is_valid is False
        assert "products" in error

    def test_validate_empty_allowed_tables(self):
        """Test validator with empty allowed tables list."""
        validator = TableValidator(allowed_tables=[])
        is_valid, error = validator.validate("SELECT * FROM users")

        assert is_valid is False
        assert "users" in error

    def test_validate_invalid_sql(self):
        """Test validator handles invalid SQL gracefully."""
        validator = TableValidator(allowed_tables=["users"])
        is_valid, error = validator.validate("NOT A VALID SQL")

        assert is_valid is False
        assert error is not None

    def test_validate_case_insensitive(self):
        """Test table name validation is case insensitive."""
        validator = TableValidator(allowed_tables=["Users", "ORDERS"])
        is_valid, error = validator.validate("SELECT * FROM users JOIN Orders ON users.id = orders.user_id")

        assert is_valid is True
        assert error is None

    def test_validate_insert_statement(self):
        """Test validation works with INSERT statements."""
        validator = TableValidator(allowed_tables=["users"])
        is_valid, error = validator.validate("INSERT INTO users (name) VALUES ('test')")

        assert is_valid is True
        assert error is None

    def test_validate_update_statement(self):
        """Test validation works with UPDATE statements."""
        validator = TableValidator(allowed_tables=["users"])
        is_valid, error = validator.validate("UPDATE users SET name = 'test' WHERE id = 1")

        assert is_valid is True
        assert error is None

    def test_validate_delete_statement(self):
        """Test validation works with DELETE statements."""
        validator = TableValidator(allowed_tables=["users"])
        is_valid, error = validator.validate("DELETE FROM users WHERE id = 1")

        assert is_valid is True
        assert error is None
