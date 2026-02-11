"""
Unit test for main flow logic - testing core logic without the full main() loop
"""
from unittest.mock import patch, MagicMock, call
import pandas as pd


def test_drop_sql_is_rejected():
    """Test that DROP TABLE is rejected by validate_sql"""
    from src.sql_safety import validate_sql

    is_valid, reason = validate_sql("DROP TABLE users")
    assert is_valid is False, "DROP TABLE should be rejected"
    assert "drop" in reason.lower()


def test_alter_sql_is_rejected():
    """Test that ALTER TABLE is rejected"""
    from src.sql_safety import validate_sql

    is_valid, reason = validate_sql("ALTER TABLE users ADD COLUMN age INT")
    assert is_valid is False, "ALTER TABLE should be rejected"
    assert "alter" in reason.lower()


def test_truncate_sql_is_rejected():
    """Test that TRUNCATE TABLE is rejected"""
    from src.sql_safety import validate_sql

    is_valid, reason = validate_sql("TRUNCATE TABLE users")
    assert is_valid is False, "TRUNCATE TABLE should be rejected"
    assert "truncate" in reason.lower()


def test_update_sql_is_accepted():
    """Test that UPDATE is accepted by validate_sql"""
    from src.sql_safety import validate_sql

    is_valid, reason = validate_sql("UPDATE users SET name='test' WHERE id=1")
    assert is_valid is True, "UPDATE should be accepted"
    assert reason == "ok"


def test_insert_sql_is_accepted():
    """Test that INSERT is accepted"""
    from src.sql_safety import validate_sql

    is_valid, reason = validate_sql("INSERT INTO users (name) VALUES ('test')")
    assert is_valid is True, "INSERT should be accepted"
    assert reason == "ok"


def test_delete_sql_is_accepted():
    """Test that DELETE is accepted"""
    from src.sql_safety import validate_sql

    is_valid, reason = validate_sql("DELETE FROM users WHERE id=1")
    assert is_valid is True, "DELETE should be accepted"
    assert reason == "ok"


def test_detect_intent_update():
    """Test detect_intent for UPDATE"""
    from src.sql_safety import detect_intent

    assert detect_intent("UPDATE users SET name='test'") == "update"


def test_detect_intent_insert():
    """Test detect_intent for INSERT"""
    from src.sql_safety import detect_intent

    assert detect_intent("INSERT INTO users VALUES (1)") == "insert"


def test_detect_intent_delete():
    """Test detect_intent for DELETE"""
    from src.sql_safety import detect_intent

    assert detect_intent("DELETE FROM users") == "delete"


def test_detect_intent_select():
    """Test detect_intent for SELECT"""
    from src.sql_safety import detect_intent

    assert detect_intent("SELECT * FROM users") == "select"


if __name__ == "__main__":
    import sys
    import pytest

    # Run tests
    exit_code = pytest.main([__file__, "-v"])
    sys.exit(exit_code)
