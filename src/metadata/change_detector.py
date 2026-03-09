"""
Schema change detector for incremental sync operations.

This module provides the ChangeDetector class for comparing current database
schema with indexed tables in the vector store, enabling incremental sync
operations.
"""

from typing import Set

from pydantic import BaseModel, Field


class ChangeDiff(BaseModel):
    """
    Result of schema comparison between current and indexed tables.

    Attributes:
        added_tables: Tables present in current schema but not in indexed.
        removed_tables: Tables present in indexed but not in current schema.
    """

    added_tables: Set[str] = Field(default_factory=set)
    removed_tables: Set[str] = Field(default_factory=set)

    def has_changes(self) -> bool:
        """
        Check if there are any changes detected.

        Returns:
            True if there are added or removed tables, False otherwise.
        """
        return bool(self.added_tables or self.removed_tables)

    def summary(self) -> str:
        """
        Get a human-readable summary of changes.

        Returns:
            Summary string describing the changes.
        """
        parts = []
        if self.added_tables:
            parts.append(f"Added: {len(self.added_tables)} tables")
        if self.removed_tables:
            parts.append(f"Removed: {len(self.removed_tables)} tables")

        if not parts:
            return "No changes detected"

        return " | ".join(parts)


class ChangeDetector:
    """
    Detector for schema changes between current database and indexed tables.

    This class compares the current database schema with what's already
    indexed in the vector store to support incremental sync operations.
    """

    def diff(
        self,
        current_tables: Set[str],
        indexed_tables: Set[str]
    ) -> ChangeDiff:
        """
        Compare current tables with indexed tables to detect changes.

        Args:
            current_tables: Set of table names currently in the database.
            indexed_tables: Set of table names already indexed in vector store.

        Returns:
            ChangeDiff object containing added and removed tables.

        Example:
            >>> detector = ChangeDetector()
            >>> diff = detector.diff(
            ...     current_tables={"users", "orders"},
            ...     indexed_tables={"users", "products"}
            ... )
            >>> diff.added_tables
            {'orders'}
            >>> diff.removed_tables
            {'products'}
        """
        added = current_tables - indexed_tables
        removed = indexed_tables - current_tables

        return ChangeDiff(
            added_tables=added,
            removed_tables=removed
        )
