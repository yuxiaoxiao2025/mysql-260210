"""Table constraint validator for SQL queries.

This module provides validation of SQL queries against a whitelist of allowed tables.
"""

from typing import Optional

from sqlglot import exp, parse
from sqlglot.errors import SqlglotError


class TableValidator:
    """Validates that SQL queries only use allowed tables.

    Attributes:
        allowed_tables: A set of table names that are permitted in SQL queries.
                       Table names are stored in lowercase for case-insensitive comparison.
    """

    def __init__(self, allowed_tables: list[str]) -> None:
        """Initialize the validator with a list of allowed table names.

        Args:
            allowed_tables: List of table names that are permitted in SQL queries.
        """
        self.allowed_tables = {table.lower() for table in allowed_tables}

    def validate(self, sql: str) -> tuple[bool, Optional[str]]:
        """Validate that all tables in the SQL query are in the allowed list.

        Args:
            sql: The SQL query string to validate.

        Returns:
            A tuple containing:
            - bool: True if all tables are allowed, False otherwise.
            - Optional[str]: Error message if validation fails, None otherwise.
        """
        try:
            parsed = parse(sql)
        except SqlglotError as e:
            return False, f"SQL parse error: {e}"
        except Exception as e:
            return False, f"Invalid SQL: {e}"

        if not parsed:
            return False, "Failed to parse SQL"

        for statement in parsed:
            if statement is None:
                continue

            for table in statement.find_all(exp.Table):
                table_name = table.name.lower()
                if table_name not in self.allowed_tables:
                    return False, f"Table '{table.name}' is not in the allowed tables list"

        return True, None
