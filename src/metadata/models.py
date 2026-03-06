"""
Metadata knowledge graph models for parking cloud data management.

This module defines Pydantic models for representing database metadata
as a knowledge graph, enabling intelligent query planning and
business context understanding.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ColumnMetadata(BaseModel):
    """
    Field metadata for a database column.

    Attributes:
        name: Column name.
        data_type: SQL data type (e.g., 'VARCHAR(255)', 'INT', 'DATETIME').
        comment: Column description/comment from database.
        is_primary_key: Whether this column is a primary key.
        is_foreign_key: Whether this column references another table.
        references_table: The table this column references (if foreign key).
        references_column: The column this column references (if foreign key).
    """

    name: str
    data_type: str
    comment: str = ""
    is_primary_key: bool = False
    is_foreign_key: bool = False
    references_table: Optional[str] = None
    references_column: Optional[str] = None


class ForeignKeyRelation(BaseModel):
    """
    Foreign key relationship between tables.

    Attributes:
        column_name: The column name in the source table.
        referenced_table: The table being referenced.
        referenced_column: The column being referenced in the target table.
    """

    column_name: str
    referenced_table: str
    referenced_column: str


class TableMetadata(BaseModel):
    """
    Core model for table metadata in the knowledge graph.

    Attributes:
        table_name: Name of the table.
        database_name: Name of the database containing this table.
        namespace: Namespace for multi-database isolation.
        comment: Table description/comment from database.
        semantic_description: Semantic enrichment for the table.
        semantic_tags: Semantic tags derived from enrichment.
        semantic_source: Source for semantic enrichment (comment | rule | llm).
        semantic_confidence: Confidence score for semantic enrichment.
        columns: List of column metadata for this table.
        foreign_keys: List of foreign key relationships from this table.
        business_domain: Business category for this table (e.g., '车辆管理', '场库管理').
        schema_text: Natural language description of the table schema.
        tags: List of tags for categorization and search.
        is_template: Whether this table is a park template table.
        template_for: Database names this template applies to.
        template_source: Template database name this table was cloned from.
    """

    table_name: str
    database_name: str = ""
    namespace: str = ""
    comment: str = ""
    semantic_description: str | None = None
    semantic_tags: list[str] = Field(default_factory=list)
    semantic_source: str | None = None
    semantic_confidence: float | None = None
    columns: List[ColumnMetadata] = Field(default_factory=list)
    foreign_keys: List[ForeignKeyRelation] = Field(default_factory=list)
    business_domain: str = "其他"
    schema_text: str = ""
    tags: List[str] = Field(default_factory=list)
    is_template: bool = False
    template_for: List[str] = Field(default_factory=list)
    template_source: Optional[str] = None

    @property
    def qualified_name(self) -> str:
        if self.database_name:
            return f"{self.database_name}.{self.table_name}"
        return self.table_name

    def get_column(self, column_name: str) -> Optional[ColumnMetadata]:
        """
        Get column metadata by column name.

        Args:
            column_name: Name of the column to find.

        Returns:
            ColumnMetadata if found, None otherwise.
        """
        for column in self.columns:
            if column.name == column_name:
                return column
        return None

    def get_primary_keys(self) -> List[ColumnMetadata]:
        """
        Get all primary key columns for this table.

        Returns:
            List of columns that are primary keys.
        """
        return [col for col in self.columns if col.is_primary_key]

    def get_foreign_key_columns(self) -> List[ColumnMetadata]:
        """
        Get all foreign key columns for this table.

        Returns:
            List of columns that are foreign keys.
        """
        return [col for col in self.columns if col.is_foreign_key]


class KnowledgeGraph(BaseModel):
    """
    Complete knowledge graph structure for database metadata.

    This model represents the entire metadata knowledge graph,
    enabling intelligent query planning and business context
    understanding across all tables in the database.

    Attributes:
        version: Version of the knowledge graph schema.
        created_at: ISO timestamp of when the graph was created.
        updated_at: ISO timestamp of when the graph was last updated.
        tables: List of all table metadata in the knowledge graph.
        namespaces: Mapping of namespace to description or label.
        template_mapping: Mapping of park instances to template namespace.
        park_instances: List of park instance database names.
        database_classification: Mapping of database name to classification.
    """

    version: str = "2.0"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    tables: List[TableMetadata] = Field(default_factory=list)
    namespaces: Dict[str, str] = Field(default_factory=dict)
    template_mapping: Dict[str, str] = Field(default_factory=dict)
    park_instances: List[str] = Field(default_factory=list)
    database_classification: Dict[str, str] = Field(default_factory=dict)

    def get_table(self, name: str) -> Optional[TableMetadata]:
        """
        Get table metadata by table name.

        Args:
            name: Name of the table to find.

        Returns:
            TableMetadata if found, None otherwise.
        """
        for table in self.tables:
            if table.table_name == name:
                return table
        return None

    def get_foreign_keys_from(self, table_name: str) -> List[ForeignKeyRelation]:
        """
        Get all foreign key relationships originating from a table.

        Args:
            table_name: Name of the source table.

        Returns:
            List of foreign key relationships from the specified table.
        """
        table = self.get_table(table_name)
        if table is None:
            return []
        return table.foreign_keys

    def get_foreign_keys_to(self, table_name: str) -> List[Dict[str, Any]]:
        """
        Get all foreign key relationships pointing to a table.

        Args:
            table_name: Name of the target table.

        Returns:
            List of dictionaries containing source table, column, and foreign key info.
        """
        references = []
        for table in self.tables:
            for fk in table.foreign_keys:
                if fk.referenced_table == table_name:
                    references.append({
                        "source_table": table.table_name,
                        "source_column": fk.column_name,
                        "target_column": fk.referenced_column,
                    })
        return references

    def get_tables_by_domain(self, domain: str) -> List[TableMetadata]:
        """
        Get all tables in a specific business domain.

        Args:
            domain: Business domain to filter by.

        Returns:
            List of tables in the specified domain.
        """
        return [table for table in self.tables if table.business_domain == domain]

    def get_tables_by_namespace(self, namespace: str) -> List[TableMetadata]:
        """
        Get all tables in a specific namespace.

        Args:
            namespace: Namespace to filter by.

        Returns:
            List of tables in the specified namespace.
        """
        return [table for table in self.tables if table.namespace == namespace]

    def get_all_namespaces(self) -> List[str]:
        """
        Get all unique namespaces in the knowledge graph.

        Returns:
            List of unique namespace names.
        """
        namespaces = {table.namespace for table in self.tables if table.namespace}
        return sorted(list(namespaces))

    def get_tables_by_tag(self, tag: str) -> List[TableMetadata]:
        """
        Get all tables with a specific tag.

        Args:
            tag: Tag to filter by.

        Returns:
            List of tables with the specified tag.
        """
        return [table for table in self.tables if tag in table.tags]

    def get_all_domains(self) -> List[str]:
        """
        Get all unique business domains in the knowledge graph.

        Returns:
            List of unique business domain names.
        """
        domains = set()
        for table in self.tables:
            domains.add(table.business_domain)
        return sorted(list(domains))

    def get_all_tags(self) -> List[str]:
        """
        Get all unique tags in the knowledge graph.

        Returns:
            List of unique tag names.
        """
        tags = set()
        for table in self.tables:
            tags.update(table.tags)
        return sorted(list(tags))

    def update_timestamp(self) -> None:
        """Update the updated_at timestamp to current time."""
        self.updated_at = datetime.now().isoformat()


class IndexProgress(BaseModel):
    """
    Progress tracking for metadata indexing operations.

    This model tracks the progress of building the knowledge graph,
    including batch processing status and error handling.

    Attributes:
        status: Current status ('pending', 'in_progress', 'completed', 'failed').
        total_tables: Total number of tables to index.
        indexed_tables: Number of tables successfully indexed.
        current_batch: Current batch number being processed.
        last_updated: ISO timestamp of last progress update.
        errors: List of error messages encountered during indexing.
        statistics: Additional statistics about the indexing process.
    """

    status: str = "pending"
    total_tables: int = 0
    indexed_tables: int = 0
    current_batch: int = 0
    last_updated: str = Field(default_factory=lambda: datetime.now().isoformat())
    errors: List[str] = Field(default_factory=list)
    statistics: Dict[str, Any] = Field(default_factory=dict)

    def get_progress_percentage(self) -> float:
        """
        Calculate the progress percentage.

        Returns:
            Progress percentage (0-100).
        """
        if self.total_tables == 0:
            return 0.0
        return (self.indexed_tables / self.total_tables) * 100

    def is_complete(self) -> bool:
        """
        Check if indexing is complete.

        Returns:
            True if indexing is complete (success or failure), False otherwise.
        """
        return self.status in ("completed", "failed")

    def add_error(self, error: str) -> None:
        """
        Add an error message to the errors list.

        Args:
            error: Error message to add.
        """
        self.errors.append(error)
        self.last_updated = datetime.now().isoformat()

    def update_progress(self, indexed: int, batch: int) -> None:
        """
        Update indexing progress.

        Args:
            indexed: Number of tables indexed so far.
            batch: Current batch number.
        """
        self.indexed_tables = indexed
        self.current_batch = batch
        self.last_updated = datetime.now().isoformat()


class IndexResult(BaseModel):
    """
    Result of a metadata indexing operation.

    This model represents the final result of building the knowledge graph,
    including success status and summary statistics.

    Attributes:
        success: Whether the indexing operation succeeded.
        total_tables: Total number of tables that were to be indexed.
        indexed_tables: Number of tables successfully indexed.
        failed_tables: List of table names that failed to index.
        elapsed_seconds: Time elapsed during indexing in seconds.
    """

    success: bool
    total_tables: int
    indexed_tables: int
    failed_tables: List[str] = Field(default_factory=list)
    elapsed_seconds: float = 0.0

    def get_success_rate(self) -> float:
        """
        Calculate the success rate of indexing.

        Returns:
            Success rate as a percentage (0-100).
        """
        if self.total_tables == 0:
            return 100.0 if self.success else 0.0
        return (self.indexed_tables / self.total_tables) * 100

    def has_failures(self) -> bool:
        """
        Check if there were any failures during indexing.

        Returns:
            True if any tables failed to index, False otherwise.
        """
        return len(self.failed_tables) > 0
