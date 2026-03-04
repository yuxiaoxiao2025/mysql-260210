"""
Schema Indexer for full database schema indexing.

Coordinates all metadata components to build a complete knowledge graph
from database schema information, including table metadata, column details,
foreign key relationships, and business domain classification.
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from src.db_manager import DatabaseManager
from src.metadata.domain_classifier import DomainClassifier
from src.metadata.embedding_service import EmbeddingService
from src.metadata.graph_store import GraphStore
from src.metadata.models import (
    ColumnMetadata,
    ForeignKeyRelation,
    IndexProgress,
    IndexResult,
    KnowledgeGraph,
    TableMetadata,
)

logger = logging.getLogger(__name__)


class SchemaIndexer:
    """
    Database Schema Indexer.

    Coordinates database manager, embedding service, graph store, and domain
    classifier to build a complete metadata knowledge graph. Supports batch
    processing with checkpoint/resume capability for large databases.

    Attributes:
        db_manager: Database manager for schema introspection.
        embedding_service: Service for generating text embeddings.
        graph_store: Vector storage for table and field metadata.
        domain_classifier: Classifier for business domain inference.
        env: Environment name (e.g., 'dev', 'prod').
        progress_file: Path to progress tracking file for checkpoint/resume.
    """

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        embedding_service: Optional[EmbeddingService] = None,
        graph_store: Optional[GraphStore] = None,
        env: str = "dev",
    ):
        """
        Initialize SchemaIndexer with optional dependency injection.

        Args:
            db_manager: Database manager instance (created if not provided).
            embedding_service: Embedding service instance (created if not provided).
            graph_store: Graph store instance (created if not provided).
            env: Environment name for storage paths ('dev' or 'prod').
        """
        self.db_manager = db_manager or DatabaseManager()
        self.embedding_service = embedding_service or EmbeddingService()
        self.graph_store = graph_store or GraphStore(env=env)
        self.domain_classifier = DomainClassifier()
        self.env = env
        self.progress_file = Path(f"data/{env}/index_progress.json")

        # Ensure data directory exists
        self.progress_file.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"SchemaIndexer initialized for env='{env}'")

    def index_all_tables(self, batch_size: int = 10) -> IndexResult:
        """
        Perform full indexing of all tables in the database.

        This method orchestrates the complete schema indexing workflow:
        1. Get all table names from DatabaseManager
        2. Load previous progress for checkpoint/resume
        3. Process tables in batches for efficiency
        4. Extract TableMetadata and generate embeddings
        5. Store vectors in GraphStore
        6. Save KnowledgeGraph JSON
        7. Return IndexResult with statistics

        Args:
            batch_size: Number of tables to process per batch (default: 10).

        Returns:
            IndexResult containing success status, statistics, and any failures.

        Example:
            >>> indexer = SchemaIndexer(env="dev")
            >>> result = indexer.index_all_tables(batch_size=10)
            >>> print(f"Indexed {result.indexed_tables}/{result.total_tables} tables")
        """
        start_time = time.time()
        logger.info(f"Starting full schema indexing with batch_size={batch_size}")

        # Get all table names
        try:
            all_tables = self.db_manager.get_all_tables()
        except Exception as e:
            logger.error(f"Failed to get table list: {e}")
            return IndexResult(
                success=False,
                total_tables=0,
                indexed_tables=0,
                elapsed_seconds=time.time() - start_time,
            )

        if not all_tables:
            logger.warning("No tables found in database")
            return IndexResult(
                success=True,
                total_tables=0,
                indexed_tables=0,
                elapsed_seconds=time.time() - start_time,
            )

        logger.info(f"Found {len(all_tables)} tables to index")

        # Load previous progress for checkpoint/resume
        progress = self._load_progress()
        indexed_tables = set(progress.statistics.get("indexed_tables", []))

        # Determine which tables need indexing
        tables_to_index = [t for t in all_tables if t not in indexed_tables]
        skipped_count = len(all_tables) - len(tables_to_index)

        if skipped_count > 0:
            logger.info(f"Skipping {skipped_count} already indexed tables")

        # Initialize progress tracking
        progress.status = "in_progress"
        progress.total_tables = len(all_tables)
        progress.indexed_tables = len(indexed_tables)
        progress.statistics["indexed_tables"] = list(indexed_tables)
        self._save_progress(progress)

        # Initialize knowledge graph
        knowledge_graph = KnowledgeGraph()

        # Track results
        failed_tables: List[str] = []
        total_indexed = len(indexed_tables)
        batch_number = progress.current_batch

        # Process tables in batches
        for i in range(0, len(tables_to_index), batch_size):
            batch = tables_to_index[i : i + batch_size]
            batch_number += 1

            logger.info(
                f"Processing batch {batch_number}: "
                f"{len(batch)} tables ({i + 1}-{min(i + batch_size, len(tables_to_index))} of {len(tables_to_index)})"
            )

            try:
                batch_result = self._index_batch(batch, knowledge_graph)

                # Update progress
                total_indexed += batch_result["success_count"]
                indexed_tables.update(batch_result["indexed"])
                failed_tables.extend(batch_result["failed"])

                progress.update_progress(total_indexed, batch_number)
                progress.statistics["indexed_tables"] = list(indexed_tables)
                self._save_progress(progress)

                logger.info(
                    f"Batch {batch_number} complete: "
                    f"{batch_result['success_count']} indexed, "
                    f"{len(batch_result['failed'])} failed"
                )

            except Exception as e:
                error_msg = f"Batch {batch_number} failed: {str(e)}"
                logger.error(error_msg)
                progress.add_error(error_msg)
                self._save_progress(progress)
                failed_tables.extend(batch)

        # Save knowledge graph
        try:
            self.graph_store.save_graph(knowledge_graph)
            logger.info(f"Saved knowledge graph with {len(knowledge_graph.tables)} tables")
        except Exception as e:
            logger.error(f"Failed to save knowledge graph: {e}")
            progress.add_error(f"Failed to save knowledge graph: {str(e)}")

        # Update final progress
        progress.status = "completed" if not failed_tables else "completed_with_errors"
        progress.indexed_tables = total_indexed
        self._save_progress(progress)

        elapsed_seconds = time.time() - start_time
        logger.info(
            f"Schema indexing complete: {total_indexed}/{len(all_tables)} tables "
            f"in {elapsed_seconds:.2f}s"
        )

        return IndexResult(
            success=len(failed_tables) == 0,
            total_tables=len(all_tables),
            indexed_tables=total_indexed,
            failed_tables=failed_tables,
            elapsed_seconds=elapsed_seconds,
        )

    def _extract_table_metadata(self, table_name: str) -> TableMetadata:
        """
        Extract table metadata from MySQL information_schema.

        Queries the database for table structure including columns,
        data types, comments, and primary keys.

        Args:
            table_name: Name of the table to extract metadata for.

        Returns:
            TableMetadata containing all column information and table details.

        Raises:
            Exception: If database query fails.
        """
        logger.debug(f"Extracting metadata for table: {table_name}")

        # Get table comment and database name
        table_info_sql = """
            SELECT
                TABLE_SCHEMA as database_name,
                TABLE_COMMENT as comment
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = :table_name
        """

        with self.db_manager.get_connection() as conn:
            table_info_result = conn.execute(
                text(table_info_sql), {"table_name": table_name}
            )
            table_info_row = table_info_result.fetchone()

            if not table_info_row:
                logger.warning(f"Table {table_name} not found in information_schema")
                database_name = ""
                table_comment = ""
            else:
                database_name = table_info_row[0] or ""
                table_comment = table_info_row[1] or ""

        # Get column information
        columns_sql = """
            SELECT
                COLUMN_NAME,
                COLUMN_TYPE,
                COLUMN_COMMENT,
                COLUMN_KEY
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = :table_name
            ORDER BY ORDINAL_POSITION
        """

        with self.db_manager.get_connection() as conn:
            columns_result = conn.execute(
                text(columns_sql), {"table_name": table_name}
            )
            columns_rows = columns_result.fetchall()

        # Build column metadata list
        columns: List[ColumnMetadata] = []
        for row in columns_rows:
            col_name = row[0]
            col_type = row[1]
            col_comment = row[2] or ""
            col_key = row[3] or ""

            columns.append(
                ColumnMetadata(
                    name=col_name,
                    data_type=col_type,
                    comment=col_comment,
                    is_primary_key=(col_key == "PRI"),
                )
            )

        # Extract foreign keys
        foreign_keys = self._extract_foreign_keys(table_name)

        # Update column metadata with foreign key information
        fk_columns = {fk.column_name: fk for fk in foreign_keys}
        for col in columns:
            if col.name in fk_columns:
                fk = fk_columns[col.name]
                col.is_foreign_key = True
                col.references_table = fk.referenced_table
                col.references_column = fk.referenced_column

        # Classify business domain
        business_domain = self.domain_classifier.classify(
            table_name, table_comment
        )

        # Generate schema text for embedding
        schema_text = self._generate_schema_text(
            table_name, table_comment, columns, business_domain
        )

        # Generate tags
        tags = self._generate_tags(table_name, table_comment, columns, business_domain)

        return TableMetadata(
            table_name=table_name,
            database_name=database_name,
            comment=table_comment,
            columns=columns,
            foreign_keys=foreign_keys,
            business_domain=business_domain,
            schema_text=schema_text,
            tags=tags,
        )

    def _extract_foreign_keys(self, table_name: str) -> List[ForeignKeyRelation]:
        """
        Extract foreign key relationships from information_schema.

        Queries KEY_COLUMN_USAGE to find all foreign key references
        from the specified table to other tables.

        Args:
            table_name: Name of the table to extract foreign keys for.

        Returns:
            List of ForeignKeyRelation objects representing foreign key constraints.
        """
        sql = """
            SELECT
                COLUMN_NAME,
                REFERENCED_TABLE_NAME,
                REFERENCED_COLUMN_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = :table_name
                AND REFERENCED_TABLE_NAME IS NOT NULL
        """

        foreign_keys: List[ForeignKeyRelation] = []

        try:
            with self.db_manager.get_connection() as conn:
                result = conn.execute(text(sql), {"table_name": table_name})
                rows = result.fetchall()

            for row in rows:
                foreign_keys.append(
                    ForeignKeyRelation(
                        column_name=row[0],
                        referenced_table=row[1],
                        referenced_column=row[2],
                    )
                )

            logger.debug(
                f"Found {len(foreign_keys)} foreign keys for table {table_name}"
            )

        except Exception as e:
            logger.warning(f"Failed to extract foreign keys for {table_name}: {e}")

        return foreign_keys

    def _generate_schema_text(
        self,
        table_name: str,
        comment: str,
        columns: List[ColumnMetadata],
        business_domain: str,
    ) -> str:
        """
        Generate natural language text for embedding.

        Creates a structured text representation of the table schema
        suitable for semantic similarity search.

        Args:
            table_name: Name of the table.
            comment: Table comment/description.
            columns: List of column metadata.
            business_domain: Classified business domain.

        Returns:
            Formatted string for embedding generation.

        Format:
            "表名：{table_name}。描述：{comment}。关键字段：{key_columns}。业务域：{business_domain}"
        """
        # Get key columns (primary keys and foreign keys)
        key_columns = []
        for col in columns:
            if col.is_primary_key:
                key_columns.append(f"{col.name}(主键)")
            elif col.is_foreign_key:
                key_columns.append(f"{col.name}(外键->{col.references_table})")

        key_columns_str = "、".join(key_columns) if key_columns else "无"

        parts = [
            f"表名：{table_name}",
            f"描述：{comment or '无'}",
            f"关键字段：{key_columns_str}",
            f"业务域：{business_domain}",
        ]

        return "。".join(parts)

    def _generate_field_schema_text(
        self, table_name: str, column: ColumnMetadata
    ) -> str:
        """
        Generate natural language text for a single field/column.

        Args:
            table_name: Name of the table containing the field.
            column: Column metadata.

        Returns:
            Formatted string for field embedding.

        Format:
            "{table_name}.{column_name}: {comment}"
        """
        return f"{table_name}.{column.name}: {column.comment or '无描述'}"

    def _generate_tags(
        self,
        table_name: str,
        comment: str,
        columns: List[ColumnMetadata],
        business_domain: str,
    ) -> List[str]:
        """
        Generate tags for the table based on its properties.

        Args:
            table_name: Name of the table.
            comment: Table comment/description.
            columns: List of column metadata.
            business_domain: Classified business domain.

        Returns:
            List of tag strings for categorization.
        """
        tags = []

        # Add business domain as tag
        if business_domain != "其他":
            tags.append(business_domain)

        # Add structural tags
        has_pk = any(col.is_primary_key for col in columns)
        has_fk = any(col.is_foreign_key for col in columns)

        if has_pk:
            tags.append("有主键")
        if has_fk:
            tags.append("有外键")

        # Add column-based tags
        for col in columns:
            col_name_lower = col.name.lower()
            if "time" in col_name_lower or "date" in col_name_lower:
                tags.append("时间相关")
                break

        for col in columns:
            col_name_lower = col.name.lower()
            if "status" in col_name_lower or "state" in col_name_lower:
                tags.append("状态相关")
                break

        # Deduplicate and return
        return list(dict.fromkeys(tags))

    def _index_batch(
        self, tables: List[str], knowledge_graph: KnowledgeGraph
    ) -> Dict[str, Any]:
        """
        Index a batch of tables.

        For each table in the batch:
        1. Extract TableMetadata
        2. Generate embeddings for table and fields
        3. Store in GraphStore
        4. Add to KnowledgeGraph

        Args:
            tables: List of table names to index.
            knowledge_graph: Knowledge graph to add tables to.

        Returns:
            Dictionary with 'success_count', 'indexed', and 'failed' keys.
        """
        result: Dict[str, Any] = {
            "success_count": 0,
            "indexed": [],
            "failed": [],
        }

        # Collect all texts for batch embedding
        table_texts: List[str] = []
        table_metadatas: List[TableMetadata] = []
        field_texts_by_table: Dict[str, List[str]] = {}
        field_columns_by_table: Dict[str, List[ColumnMetadata]] = {}

        for table_name in tables:
            try:
                # Extract metadata
                table_metadata = self._extract_table_metadata(table_name)
                table_metadatas.append(table_metadata)
                table_texts.append(table_metadata.schema_text)

                # Collect field texts
                field_texts = []
                field_columns = []
                for col in table_metadata.columns:
                    field_text = self._generate_field_schema_text(
                        table_name, col
                    )
                    field_texts.append(field_text)
                    field_columns.append(col)

                field_texts_by_table[table_name] = field_texts
                field_columns_by_table[table_name] = field_columns

            except Exception as e:
                logger.error(f"Failed to extract metadata for {table_name}: {e}")
                result["failed"].append(table_name)

        if not table_metadatas:
            return result

        # Generate embeddings in batch
        try:
            # Batch embed table schemas
            table_embeddings = self.embedding_service.embed_batch(table_texts)

            # Store table vectors in batch
            self.graph_store.add_tables_batch(table_metadatas, table_embeddings)

            # Store field vectors for each table
            for table_metadata in table_metadatas:
                table_name = table_metadata.table_name
                field_texts = field_texts_by_table.get(table_name, [])
                field_columns = field_columns_by_table.get(table_name, [])

                if field_texts:
                    field_embeddings = self.embedding_service.embed_batch(field_texts)
                    self.graph_store.add_fields_batch(
                        table_name, field_columns, field_embeddings
                    )

                # Add to knowledge graph
                knowledge_graph.tables.append(table_metadata)
                result["indexed"].append(table_name)
                result["success_count"] += 1

        except Exception as e:
            logger.error(f"Failed to process batch embeddings: {e}")
            # Mark all as failed if batch embedding fails
            for table_metadata in table_metadatas:
                if table_metadata.table_name not in result["indexed"]:
                    result["failed"].append(table_metadata.table_name)

        return result

    def _save_progress(self, progress: IndexProgress) -> None:
        """
        Save indexing progress to file for checkpoint/resume.

        Args:
            progress: IndexProgress object to save.
        """
        try:
            with open(self.progress_file, "w", encoding="utf-8") as f:
                json.dump(progress.model_dump(), f, ensure_ascii=False, indent=2)
            logger.debug(f"Saved progress to {self.progress_file}")
        except Exception as e:
            logger.error(f"Failed to save progress: {e}")

    def _load_progress(self) -> IndexProgress:
        """
        Load indexing progress from file for checkpoint/resume.

        Returns:
            IndexProgress object, either from file or newly created.
        """
        if not self.progress_file.exists():
            logger.debug("No existing progress file, starting fresh")
            return IndexProgress()

        try:
            with open(self.progress_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            progress = IndexProgress(**data)
            logger.info(
                f"Loaded progress: {progress.indexed_tables}/{progress.total_tables} tables, "
                f"status={progress.status}"
            )
            return progress
        except Exception as e:
            logger.warning(f"Failed to load progress file, starting fresh: {e}")
            return IndexProgress()

    def get_progress(self) -> IndexProgress:
        """
        Get current indexing progress.

        Returns:
            Current IndexProgress object.
        """
        return self._load_progress()

    def clear_progress(self) -> None:
        """
        Clear progress file to start fresh indexing.

        This does not clear the stored vectors, only the progress tracking.
        Use graph_store.clear_all() to clear vectors.
        """
        if self.progress_file.exists():
            try:
                self.progress_file.unlink()
                logger.info(f"Cleared progress file: {self.progress_file}")
            except Exception as e:
                logger.error(f"Failed to clear progress file: {e}")

    def index_single_table(self, table_name: str) -> Optional[TableMetadata]:
        """
        Index a single table.

        Useful for incremental updates or reindexing specific tables.

        Args:
            table_name: Name of the table to index.

        Returns:
            TableMetadata if successful, None otherwise.
        """
        logger.info(f"Indexing single table: {table_name}")

        try:
            # Extract metadata
            table_metadata = self._extract_table_metadata(table_name)

            # Generate table embedding
            table_embedding = self.embedding_service.embed_text(
                table_metadata.schema_text
            )

            # Store table vector
            self.graph_store.add_table(table_metadata, table_embedding)

            # Generate and store field embeddings
            for col in table_metadata.columns:
                field_text = self._generate_field_schema_text(table_name, col)
                field_embedding = self.embedding_service.embed_text(field_text)
                self.graph_store.add_field(table_name, col, field_embedding)

            logger.info(f"Successfully indexed table: {table_name}")
            return table_metadata

        except Exception as e:
            logger.error(f"Failed to index table {table_name}: {e}")
            return None