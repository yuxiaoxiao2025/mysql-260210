import uuid

import pytest
from sqlalchemy import text

from src.db_manager import DatabaseManager


def test_build_db_url_no_db():
    manager = DatabaseManager(specific_db=None)
    assert manager.specific_db is None
    assert manager.db_url.endswith("/")
    with manager.get_connection() as conn:
        result = conn.execute(text("SELECT 1")).scalar()
        assert result == 1


def test_get_all_databases():
    manager = DatabaseManager()
    dbs = manager.get_all_databases(exclude_system=True)
    assert isinstance(dbs, list)
    assert "information_schema" not in dbs
    assert "mysql" not in dbs
    assert "performance_schema" not in dbs
    assert "sys" not in dbs


def test_get_tables_in_database():
    manager = DatabaseManager()
    table_name = "test_cross_db_tables"
    db_name = manager.execute_query("SELECT DATABASE() AS db_name").iloc[0][
        "db_name"
    ]

    try:
        manager.execute_update(
            f"CREATE TABLE IF NOT EXISTS `{db_name}`.`{table_name}` ("
            "id INT PRIMARY KEY AUTO_INCREMENT,"
            "name VARCHAR(50)"
            ")"
        )
        tables = manager.get_tables_in_database(db_name)
        assert table_name in tables
    finally:
        manager.execute_update(
            f"DROP TABLE IF EXISTS `{db_name}`.`{table_name}`"
        )


def test_check_tables_structure_match():
    manager = DatabaseManager()
    db1 = f"test_struct_{uuid.uuid4().hex[:8]}"
    db2 = f"test_struct_{uuid.uuid4().hex[:8]}"

    try:
        manager.execute_update(f"CREATE DATABASE `{db1}`")
        manager.execute_update(f"CREATE DATABASE `{db2}`")
        manager.execute_update(
            f"CREATE TABLE `{db1}`.`test_table` ("
            "id INT PRIMARY KEY,"
            "name VARCHAR(50)"
            ")"
        )
        manager.execute_update(
            f"CREATE TABLE `{db2}`.`test_table` ("
            "id INT PRIMARY KEY,"
            "name VARCHAR(50)"
            ")"
        )
        assert manager.check_tables_structure_match(db1, db2) is True
    finally:
        manager.execute_update(f"DROP DATABASE IF EXISTS `{db1}`")
        manager.execute_update(f"DROP DATABASE IF EXISTS `{db2}`")
