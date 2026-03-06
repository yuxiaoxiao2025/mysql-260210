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
        namespace: Namespace identifier (typically database_name).
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
        is_template: Whether this table is a template (for park databases).
        template_for: List of databases that use this template.
        template_source: Source database name if this is a template instance.
    """

    table_name: str
    database_name: str = ""
    namespace: str = ""  # 命名空间标识 (通常是 database_name)
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

    # 园区库模板相关
    is_template: bool = False  # 是否为模板表
    template_for: List[str] = Field(default_factory=list)  # 复用此模板的库名列表
    template_source: Optional[str] = None  # 模板来源库名（实例表用）

    @property
    def qualified_name(self) -> str:
        """获取完全限定名: database.table"""
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
        version: Version of the knowledge graph schema (upgraded to 2.0).
        created_at: ISO timestamp of when the graph was created.
        updated_at: ISO timestamp of when the graph was last updated.
        tables: List of all table metadata in the knowledge graph.
<<<<<<< HEAD
        namespaces: Mapping of namespace to description or label.
        template_mapping: Mapping of park instances to template namespace.
        park_instances: List of park instance database names.
        database_classification: Mapping of database name to classification.
=======
        namespaces: Namespace index mapping {db_name: namespace_type}.
        template_mapping: Template to instance mapping.
        park_instances: List of park database instances.
        database_classification: Database classification info.
>>>>>>> feat/multi-database-namespace
    """

    version: str = "2.0"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    tables: List[TableMetadata] = Field(default_factory=list)
    namespaces: Dict[str, str] = Field(default_factory=dict)
    template_mapping: Dict[str, str] = Field(default_factory=dict)
    park_instances: List[str] = Field(default_factory=list)
    database_classification: Dict[str, str] = Field(default_factory=dict)

    # 娡型升级：命名空间支持
    namespaces: Dict[str, str] = Field(default_factory=dict)
    # {库名: 命名空间类型} - "primary" | "secondary" | "park_template" | "park_instance"
    template_mapping: Dict[str, str] = Field(default_factory=dict)
    # {园区库名: 模板库名}
    park_instances: List[str] = Field(default_factory=list)
    # 所有园区库名列表
    database_classification: Dict[str, str] = Field(default_factory=dict)
    # {库名: 分类} - "primary" | "secondary" | "park_template" | "park_instance" | "excluded"



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

    def get_table_by_qualified_name(self, qualified_name: str) -> Optional[TableMetadata]:
        """
        Get table metadata by fully qualified name.

        Args:
            qualified_name: Fully qualified name in format "database.table_name".

        Returns:
            TableMetadata if found, None otherwise.
        """
        for table in self.tables:
            if table.qualified_name == qualified_name:
                return table
        return None

    def get_tables_by_namespace(self, namespace: str) -> List[TableMetadata]:
        """
        Get all tables in a specific namespace.

        Args:
            namespace: Namespace (database name) to filter by.

        Returns:
            List of tables in the specified namespace.
        """
        return [t for t in self.tables if t.namespace == namespace]

    def get_template_instances(self, template_db: str) -> List[str]:
        """
        Get all instance databases using a specific template.

        Args:
            template_db: Template database name.

        Returns:
            List of instance database names.
        """
        return [k for k, v in self.template_mapping.items() if v == template_db]

    def get_primary_tables(self) -> List[TableMetadata]:
        """
        Get all tables from primary databases.

        Returns:
            List of tables from primary namespaces.
        """
        return [
            t for t in self.tables
            if self.database_classification.get(t.database_name) == "primary"
        ]

    def get_all_namespaces(self) -> List[str]:
        """
        Get all unique namespace names.

        Returns:
            List of unique namespace names.
        """
        return sorted(list(set(t.namespace for t in self.tables if t.namespace)))


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


# ==================== 多库命名空间模型 ====================

from enum import Enum


class DatabaseType(str, Enum):
    """数据库类型枚举"""
    PRIMARY = "primary"              # 主业务库 (parkcloud)
    SECONDARY = "secondary"          # 次要业务库 (db_parking_center, cloudinterface)
    PARK_TEMPLATE = "park_template"  # 园区库模板
    PARK_INSTANCE = "park_instance"  # 园区库实例
    EXCLUDED = "excluded"            # 排除的库


class DatabaseClassification(BaseModel):
    """
    数据库分类配置

    用于对多个数据库进行分类管理，支持：
    - 主业务库（需独立索引）
    - 次要业务库（需独立索引）
    - 园区库（模板 + 实例，复用 embedding）
    - 排除库（不索引）

    Attributes:
        primary_databases: 主业务库列表
        secondary_databases: 次要业务库列表
        excluded_databases: 排除的库列表
        park_prefix: 园区库名前缀
        park_template_db: 园区库模板名（自动选择第一个）
        system_databases: 系统库（自动排除）
    """

    primary_databases: List[str] = ["parkcloud"]
    secondary_databases: List[str] = ["db_parking_center", "cloudinterface"]
    excluded_databases: List[str] = ["parkstandard"]

    # 园区库配置
    park_prefix: str = "p"
    park_template_db: Optional[str] = None  # 自动选择第一个园区库

    # 系统库（自动排除）
    system_databases: List[str] = [
        "information_schema",
        "mysql",
        "performance_schema",
        "sys"
    ]

    def classify_database(self, db_name: str, available_databases: Optional[List[str]] = None) -> DatabaseType:
        """
        分类单个数据库

        Args:
            db_name: 数据库名
            available_databases: 可用数据库列表（用于选择园区库模板）

        Returns:
            DatabaseType 枚举值
        """
        # 系统库和排除库
        if db_name in self.system_databases or db_name in self.excluded_databases:
            return DatabaseType.EXCLUDED

        # 主业务库
        if db_name in self.primary_databases:
            return DatabaseType.PRIMARY

        # 次要业务库
        if db_name in self.secondary_databases:
            return DatabaseType.SECONDARY

        # 园区库
        if db_name.startswith(self.park_prefix):
            # 确定模板库
            if available_databases:
                park_dbs = sorted([db for db in available_databases if db.startswith(self.park_prefix)])
                if park_dbs:
                    template = park_dbs[0]
                    if db_name == template:
                        return DatabaseType.PARK_TEMPLATE
                    return DatabaseType.PARK_INSTANCE
            # 如果没有提供可用数据库列表，使用配置的模板
            if self.park_template_db and db_name == self.park_template_db:
                return DatabaseType.PARK_TEMPLATE
            return DatabaseType.PARK_INSTANCE

        # 默认为次要业务库
        return DatabaseType.SECONDARY

    def classify_all_databases(self, databases: List[str]) -> Dict[str, DatabaseType]:
        """
        分类所有数据库

        Args:
            databases: 数据库列表

        Returns:
            {数据库名: 分类} 字典
        """
        return {db: self.classify_database(db, databases) for db in databases}

    def get_template_database(self, available_databases: List[str]) -> Optional[str]:
        """
        获取园区库模板数据库名

        Args:
            available_databases: 可用数据库列表

        Returns:
            模板数据库名（字典序第一个园区库）
        """
        park_dbs = sorted([db for db in available_databases if db.startswith(self.park_prefix)])
        return park_dbs[0] if park_dbs else None

    def get_park_instances(self, available_databases: List[str]) -> List[str]:
        """
        获取所有园区库实例名

        Args:
            available_databases: 可用数据库列表

        Returns:
            园区库实例名列表（排除模板）
        """
        park_dbs = sorted([db for db in available_databases if db.startswith(self.park_prefix)])
        if len(park_dbs) <= 1:
            return []
        return park_dbs[1:]  # 返回除第一个外的所有园区库


class MultiDatabaseIndexProgress(BaseModel):
    """多库索引进度"""
    status: str = "pending"
    total_databases: int = 0
    indexed_databases: int = 0
    current_database: str = ""

    # 详细进度
    database_progress: Dict[str, IndexProgress] = Field(default_factory=dict)

    # 模板进度
    template_indexed: bool = False
    template_cloned: bool = False
    clone_progress: int = 0

    last_updated: str = Field(default_factory=lambda: datetime.now().isoformat())
    errors: List[str] = Field(default_factory=list)

    def get_overall_progress(self) -> float:
        """获取整体进度百分比"""
        if self.total_databases == 0:
            return 0.0
        return (self.indexed_databases / self.total_databases) * 100

    def update_database_progress(self, db_name: str, progress: IndexProgress) -> None:
        """更新单个数据库的索引进度"""
        self.database_progress[db_name] = progress
        self.last_updated = datetime.now().isoformat()


class MultiDatabaseIndexResult(BaseModel):
    """多库索引结果"""
    success: bool
    total_databases: int
    indexed_databases: int
    failed_databases: List[str] = Field(default_factory=list)

    # 分类统计
    primary_count: int = 0
    secondary_count: int = 0
    park_template_count: int = 0
    park_instance_count: int = 0

    # 表统计
    total_tables: int = 0
    embedded_tables: int = 0  # 实际生成 embedding 的表数

    elapsed_seconds: float = 0.0

    def get_database_success_rate(self) -> float:
        """获取数据库索引成功率"""
        if self.total_databases == 0:
            return 100.0 if self.success else 0.0
        return (self.indexed_databases / self.total_databases) * 100

    def get_embedding_savings_rate(self) -> float:
        """获取 embedding 节省率（园区库复用模板）"""
        if self.total_tables == 0:
            return 0.0
        # 节省的 embedding 数 = 总表数 - 实际生成 embedding 的表数
        saved = self.total_tables - self.embedded_tables
        return (saved / self.total_tables) * 100
