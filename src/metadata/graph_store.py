"""
GraphStore for ChromaDB vector storage and JSON persistence.

Provides vector storage for table and field metadata embeddings,
enabling semantic similarity search for intelligent query planning.
"""

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings

from src.metadata.models import ColumnMetadata, KnowledgeGraph, TableMetadata

logger = logging.getLogger(__name__)


class GraphStore:
    """
    Vector storage for metadata knowledge graph.

    Combines ChromaDB for vector similarity search with JSON persistence
    for the complete knowledge graph structure.

    Attributes:
        env: Environment name (e.g., 'dev', 'prod').
        chroma_path: Path to ChromaDB persistent storage.
        json_path: Path to JSON knowledge graph file.
        backup_path: Path to backup directory.
        client: ChromaDB persistent client.
        table_collection: ChromaDB collection for table embeddings.
        field_collection: ChromaDB collection for field embeddings.
    """

    def __init__(self, env: str = "dev"):
        """
        Initialize GraphStore with environment-specific paths.

        Args:
            env: Environment name ("dev" or "prod").
        """
        self.env = env
        self.chroma_path = Path(f"data/{env}/chroma_db")
        self.json_path = Path(f"data/{env}/table_graph.json")
        self.backup_path = Path(f"data/{env}/backups")

        # Ensure directories exist
        self.chroma_path.parent.mkdir(parents=True, exist_ok=True)
        self.backup_path.mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB with persistent storage
        self.client = chromadb.PersistentClient(path=str(self.chroma_path))

        # Create collections with cosine distance
        self.table_collection = self.client.get_or_create_collection(
            name="table_metadata",
            metadata={"hnsw:space": "cosine"}
        )
        self.field_collection = self.client.get_or_create_collection(
            name="field_metadata",
            metadata={"hnsw:space": "cosine"}
        )

        logger.info(
            f"GraphStore initialized for env='{env}' "
            f"(tables={self.table_collection.count()}, fields={self.field_collection.count()})"
        )

    def add_table(self, table: TableMetadata, embedding: List[float]) -> None:
        """
        Add a table vector to the collection.

        Args:
            table: Table metadata to add.
            embedding: 1024-dimensional embedding vector.

        Raises:
            ValueError: If embedding dimension is incorrect.
        """
        if len(embedding) != 1024:
            raise ValueError(
                f"Embedding dimension must be 1024, got {len(embedding)}"
            )

        table_id = table.table_name
        metadata = {
            "database_name": table.database_name,
            "business_domain": table.business_domain,
            "comment": table.comment[:500] if table.comment else "",  # Truncate long comments
        }

        try:
            self.table_collection.upsert(
                ids=[table_id],
                embeddings=[embedding],
                metadatas=[metadata]
            )
            logger.debug(f"Added table vector: {table_id}")
        except Exception as e:
            logger.error(f"Failed to add table vector for {table_id}: {e}")
            raise

    def add_field(
        self,
        table_name: str,
        column: ColumnMetadata,
        embedding: List[float]
    ) -> None:
        """
        Add a field vector to the collection.

        Args:
            table_name: Name of the table containing this field.
            column: Column metadata to add.
            embedding: 1024-dimensional embedding vector.

        Raises:
            ValueError: If embedding dimension is incorrect.
        """
        if len(embedding) != 1024:
            raise ValueError(
                f"Embedding dimension must be 1024, got {len(embedding)}"
            )

        field_id = f"{table_name}.{column.name}"
        metadata = {
            "table_name": table_name,
            "data_type": column.data_type,
            "is_primary_key": column.is_primary_key,
            "is_foreign_key": column.is_foreign_key,
            "comment": column.comment[:200] if column.comment else "",  # Truncate
        }

        if column.is_foreign_key and column.references_table:
            metadata["references_table"] = column.references_table

        try:
            self.field_collection.upsert(
                ids=[field_id],
                embeddings=[embedding],
                metadatas=[metadata]
            )
            logger.debug(f"Added field vector: {field_id}")
        except Exception as e:
            logger.error(f"Failed to add field vector for {field_id}: {e}")
            raise

    def add_tables_batch(
        self,
        tables: List[TableMetadata],
        embeddings: List[List[float]]
    ) -> None:
        """
        Add multiple table vectors in a batch operation.

        Args:
            tables: List of table metadata.
            embeddings: List of corresponding embeddings.

        Raises:
            ValueError: If lengths don't match or embeddings have wrong dimension.
        """
        if len(tables) != len(embeddings):
            raise ValueError(
                f"Tables count ({len(tables)}) must match embeddings count ({len(embeddings)})"
            )

        if not tables:
            return

        # Validate embeddings
        for i, emb in enumerate(embeddings):
            if len(emb) != 1024:
                raise ValueError(
                    f"Embedding {i} has wrong dimension: {len(emb)}, expected 1024"
                )

        ids = [t.table_name for t in tables]
        metadatas = [
            {
                "database_name": t.database_name,
                "business_domain": t.business_domain,
                "comment": t.comment[:500] if t.comment else "",
            }
            for t in tables
        ]

        try:
            self.table_collection.upsert(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas
            )
            logger.info(f"Added {len(tables)} table vectors in batch")
        except Exception as e:
            logger.error(f"Failed to add table vectors in batch: {e}")
            raise

    def add_fields_batch(
        self,
        table_name: str,
        columns: List[ColumnMetadata],
        embeddings: List[List[float]]
    ) -> None:
        """
        Add multiple field vectors in a batch operation.

        Args:
            table_name: Name of the table containing these fields.
            columns: List of column metadata.
            embeddings: List of corresponding embeddings.

        Raises:
            ValueError: If lengths don't match or embeddings have wrong dimension.
        """
        if len(columns) != len(embeddings):
            raise ValueError(
                f"Columns count ({len(columns)}) must match embeddings count ({len(embeddings)})"
            )

        if not columns:
            return

        # Validate embeddings
        for i, emb in enumerate(embeddings):
            if len(emb) != 1024:
                raise ValueError(
                    f"Embedding {i} has wrong dimension: {len(emb)}, expected 1024"
                )

        ids = [f"{table_name}.{c.name}" for c in columns]
        metadatas = [
            {
                "table_name": table_name,
                "data_type": c.data_type,
                "is_primary_key": c.is_primary_key,
                "is_foreign_key": c.is_foreign_key,
                "comment": c.comment[:200] if c.comment else "",
            }
            for c in columns
        ]

        try:
            self.field_collection.upsert(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas
            )
            logger.info(
                f"Added {len(columns)} field vectors for table {table_name} in batch"
            )
        except Exception as e:
            logger.error(f"Failed to add field vectors in batch: {e}")
            raise

    def save_graph(self, graph: KnowledgeGraph) -> None:
        """
        Save knowledge graph to JSON file.

        Creates a backup of existing file before overwriting.

        Args:
            graph: Knowledge graph to save.
        """
        # Create backup if file exists
        if self.json_path.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self.backup_path / f"table_graph_{timestamp}.json"
            try:
                shutil.copy2(self.json_path, backup_file)
                logger.info(f"Created backup: {backup_file}")
            except Exception as e:
                logger.warning(f"Failed to create backup: {e}")

        # Update timestamp before saving
        graph.update_timestamp()

        # Write to JSON file
        try:
            with open(self.json_path, "w", encoding="utf-8") as f:
                json.dump(graph.model_dump(), f, ensure_ascii=False, indent=2)
            logger.info(f"Saved knowledge graph to {self.json_path}")
        except Exception as e:
            logger.error(f"Failed to save knowledge graph: {e}")
            raise

    def load_graph(self) -> Optional[KnowledgeGraph]:
        """
        Load knowledge graph from JSON file.

        Returns:
            KnowledgeGraph if file exists and is valid, None otherwise.
        """
        if not self.json_path.exists():
            logger.info(f"Knowledge graph file not found: {self.json_path}")
            return None

        try:
            with open(self.json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            graph = KnowledgeGraph(**data)
            logger.info(
                f"Loaded knowledge graph with {len(graph.tables)} tables from {self.json_path}"
            )
            return graph
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in knowledge graph file: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to load knowledge graph: {e}")
            return None

    def clear_all(self) -> None:
        """
        Clear all vectors from collections.

        Used for rebuilding the index. Deletes and recreates both collections.
        """
        try:
            # Delete and recreate table collection
            self.client.delete_collection("table_metadata")
            self.table_collection = self.client.get_or_create_collection(
                name="table_metadata",
                metadata={"hnsw:space": "cosine"}
            )
            logger.info("Cleared table_metadata collection")

            # Delete and recreate field collection
            self.client.delete_collection("field_metadata")
            self.field_collection = self.client.get_or_create_collection(
                name="field_metadata",
                metadata={"hnsw:space": "cosine"}
            )
            logger.info("Cleared field_metadata collection")

        except Exception as e:
            logger.error(f"Failed to clear collections: {e}")
            raise

    def query_tables(
        self,
        embedding: List[float],
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Query for similar tables based on embedding.

        Args:
            embedding: Query embedding vector (1024 dimensions).
            top_k: Number of results to return.

        Returns:
            List of dictionaries with 'id', 'distance', and 'metadata' keys.

        Raises:
            ValueError: If embedding dimension is incorrect.
        """
        if len(embedding) != 1024:
            raise ValueError(
                f"Embedding dimension must be 1024, got {len(embedding)}"
            )

        try:
            results = self.table_collection.query(
                query_embeddings=[embedding],
                n_results=top_k
            )

            # Format results
            formatted_results = []
            if results["ids"] and results["ids"][0]:
                for i, table_id in enumerate(results["ids"][0]):
                    formatted_results.append({
                        "id": table_id,
                        "distance": results["distances"][0][i],
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {}
                    })

            logger.debug(f"Found {len(formatted_results)} similar tables")
            return formatted_results

        except Exception as e:
            logger.error(f"Failed to query tables: {e}")
            raise

    def query_fields(
        self,
        embedding: List[float],
        filter_tables: Optional[List[str]] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Query for similar fields based on embedding.

        Args:
            embedding: Query embedding vector (1024 dimensions).
            filter_tables: Optional list of table names to filter results.
            top_k: Number of results to return.

        Returns:
            List of dictionaries with 'id', 'distance', and 'metadata' keys.

        Raises:
            ValueError: If embedding dimension is incorrect.
        """
        if len(embedding) != 1024:
            raise ValueError(
                f"Embedding dimension must be 1024, got {len(embedding)}"
            )

        try:
            # Build where filter if table filter is provided
            where_filter = None
            if filter_tables:
                where_filter = {"table_name": {"$in": filter_tables}}

            results = self.field_collection.query(
                query_embeddings=[embedding],
                n_results=top_k,
                where=where_filter
            )

            # Format results
            formatted_results = []
            if results["ids"] and results["ids"][0]:
                for i, field_id in enumerate(results["ids"][0]):
                    formatted_results.append({
                        "id": field_id,
                        "distance": results["distances"][0][i],
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {}
                    })

            logger.debug(
                f"Found {len(formatted_results)} similar fields"
                f"{f' (filtered by {len(filter_tables)} tables)' if filter_tables else ''}"
            )
            return formatted_results

        except Exception as e:
            logger.error(f"Failed to query fields: {e}")
            raise

    def get_table_count(self) -> int:
        """
        Get the number of tables in the collection.

        Returns:
            Number of table vectors stored.
        """
        return self.table_collection.count()

    def get_field_count(self) -> int:
        """
        Get the number of fields in the collection.

        Returns:
            Number of field vectors stored.
        """
        return self.field_collection.count()

    def delete_table(self, table_name: str) -> None:
        """
        Delete a table vector from the collection.

        Args:
            table_name: Name of the table to delete.
        """
        try:
            self.table_collection.delete(ids=[table_name])
            logger.info(f"Deleted table vector: {table_name}")
        except Exception as e:
            logger.error(f"Failed to delete table vector {table_name}: {e}")
            raise

    def delete_field(self, table_name: str, column_name: str) -> None:
        """
        Delete a field vector from the collection.

        Args:
            table_name: Name of the table containing the field.
            column_name: Name of the column to delete.
        """
        field_id = f"{table_name}.{column_name}"
        try:
            self.field_collection.delete(ids=[field_id])
            logger.info(f"Deleted field vector: {field_id}")
        except Exception as e:
            logger.error(f"Failed to delete field vector {field_id}: {e}")
            raise

    def delete_table_fields(self, table_name: str) -> None:
        """
        Delete all field vectors for a table.

        Args:
            table_name: Name of the table whose fields should be deleted.
        """
        try:
            # Query all fields for this table
            results = self.field_collection.get(
                where={"table_name": table_name}
            )

            if results["ids"]:
                self.field_collection.delete(ids=results["ids"])
                logger.info(
                    f"Deleted {len(results['ids'])} field vectors for table {table_name}"
                )
            else:
                logger.info(f"No field vectors found for table {table_name}")

        except Exception as e:
            logger.error(f"Failed to delete field vectors for table {table_name}: {e}")
            raise

    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the stored vectors.

        Returns:
            Dictionary with statistics about tables, fields, and storage paths.
        """
        return {
            "env": self.env,
            "table_count": self.get_table_count(),
            "field_count": self.get_field_count(),
            "chroma_path": str(self.chroma_path),
            "json_path": str(self.json_path),
            "json_exists": self.json_path.exists(),
            "backup_path": str(self.backup_path),
        }