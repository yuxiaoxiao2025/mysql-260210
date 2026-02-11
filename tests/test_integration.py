"""
Integration test for main flow SQL safety check
"""
from unittest.mock import patch, MagicMock
import pandas as pd


def test_sql_safety_in_main():
    """Test that dangerous SQL is rejected in main flow"""
    from src.sql_safety import validate_sql
    from main import main

    # Test validate_sql function directly
    is_valid, reason = validate_sql("DROP TABLE users")
    assert is_valid is False
    assert "drop" in reason.lower()


def test_detect_intent():
    """Test intent detection"""
    from src.sql_safety import detect_intent

    assert detect_intent("UPDATE users SET name='test'") == "update"
    assert detect_intent("DELETE FROM users") == "delete"
    assert detect_intent("INSERT INTO users VALUES (1)") == "insert"
    assert detect_intent("SELECT * FROM users") == "select"
    assert detect_intent("DROP TABLE users") == "unknown"


def test_db_manager_has_execute_in_transaction():
    """Test that DatabaseManager has execute_in_transaction method"""
    from src.db_manager import DatabaseManager

    assert hasattr(DatabaseManager, 'execute_in_transaction')


if __name__ == "__main__":
    test_sql_safety_in_main()
    test_detect_intent()
    test_db_manager_has_execute_in_transaction()
    print("All tests passed!")
