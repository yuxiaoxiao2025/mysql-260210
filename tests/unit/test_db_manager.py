import pytest
from unittest.mock import MagicMock

from src.db_manager import DatabaseManager


@pytest.fixture
def db_manager():
    return DatabaseManager.__new__(DatabaseManager)


def _bind_connection(db_manager: DatabaseManager, execute_side_effect):
    conn = MagicMock()
    conn.execute.side_effect = execute_side_effect
    ctx = MagicMock()
    ctx.__enter__.return_value = conn
    ctx.__exit__.return_value = None
    db_manager.get_connection = MagicMock(return_value=ctx)
    return conn


def test_is_table_empty_fast_path_non_empty(db_manager):
    table_rows_result = MagicMock()
    table_rows_result.fetchone.return_value = (12,)
    conn = _bind_connection(db_manager, [table_rows_result])

    is_empty = db_manager.is_table_empty("parkcloud", "users")

    assert is_empty is False
    assert conn.execute.call_count == 1


def test_is_table_empty_fallback_detects_empty(db_manager):
    table_rows_result = MagicMock()
    table_rows_result.fetchone.return_value = (0,)
    fallback_result = MagicMock()
    fallback_result.fetchone.return_value = None
    conn = _bind_connection(db_manager, [table_rows_result, fallback_result])

    is_empty = db_manager.is_table_empty("parkcloud", "users")

    assert is_empty is True
    assert conn.execute.call_count == 2


def test_is_table_empty_fallback_detects_non_empty(db_manager):
    table_rows_result = MagicMock()
    table_rows_result.fetchone.return_value = (0,)
    fallback_result = MagicMock()
    fallback_result.fetchone.return_value = (1,)
    conn = _bind_connection(db_manager, [table_rows_result, fallback_result])

    is_empty = db_manager.is_table_empty("parkcloud", "users")

    assert is_empty is False
    assert conn.execute.call_count == 2


def test_is_table_empty_exception_returns_false(db_manager):
    _bind_connection(db_manager, RuntimeError("db error"))

    is_empty = db_manager.is_table_empty("parkcloud", "users")

    assert is_empty is False


def test_is_table_empty_invalid_identifier_raises(db_manager):
    with pytest.raises(ValueError):
        db_manager.is_table_empty("parkcloud", "invalid-table")
