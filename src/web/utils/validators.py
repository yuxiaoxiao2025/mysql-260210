"""Validation utilities for database identifiers and other inputs."""
import re


def validate_identifier(name: str) -> bool:
    """Validate database identifier (table/schema name).

    MySQL identifier rules:
    - Max 64 characters
    - Start with letter or underscore
    - Contain only alphanumeric, underscore

    Args:
        name: Identifier name to validate

    Returns:
        True if valid, False otherwise
    """
    if not name or len(name) > 64:
        return False
    return bool(re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name))
