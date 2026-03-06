# Multi-Database Namespace Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade the system to support indexing and querying across 76 databases, implementing namespace isolation (database.table) and a template mechanism for park databases to optimize storage and performance.

**Architecture:**
1.  **DatabaseManager**: Upgrade to support connection-less initialization and cross-database schema introspection.
2.  **Data Models**: Update `TableMetadata` and `KnowledgeGraph` to include `namespace`, `database_name`, and template-related fields.
3.  **GraphStore**: Upgrade vector storage to support namespace filtering and cloning.
4.  **SchemaIndexer**: Orchestrate multi-database indexing, including identifying park templates and cloning them to instances.

**Tech Stack:** Python, SQLAlchemy, Pydantic, ChromaDB

---

### Task 1: Update DatabaseManager for Cross-Database Support

**Files:**
- Modify: `src/db_manager.py`
- Test: `tests/test_db_manager_cross_db.py` (Create new)

**Step 1: Write failing test for connection URL generation**

```python
# tests/test_db_manager_cross_db.py
import pytest
from src.db_manager import DatabaseManager

def test_build_db_url_no_db():
    # Test that we can initialize without a specific database
    manager = DatabaseManager(specific_db=None)
    # The URL should end with / if no DB is specified, or at least not have a DB name
    # Adjust assertion based on actual implementation of _build_db_url
    assert manager.specific_db is None
    # Ensure we can get a connection
    with manager.get_connection() as conn:
        assert conn is not None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_db_manager_cross_db.py::test_build_db_url_no_db -v`
Expected: FAIL (likely due to connection error or URL formation)

**Step 3: Implement `_build_db_url` update**

Modify `src/db_manager.py`:
- Update `__init__` to accept `specific_db` (optional).
- Update `_build_db_url` to handle `None`.

```python
def _build_db_url(self, db_name: Optional[str] = None) -> str:
    # ... logic to build URL without DB name if db_name is None ...
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_db_manager_cross_db.py::test_build_db_url_no_db -v`
Expected: PASS

**Step 5: Write failing test for `get_all_databases`**

```python
def test_get_all_databases(db_manager):
    # This requires a live DB connection or mock
    dbs = db_manager.get_all_databases(exclude_system=True)
    assert isinstance(dbs, list)
    assert "information_schema" not in dbs
    # Assuming 'mysql' is a system db
    assert "mysql" not in dbs
```

**Step 6: Implement `get_all_databases`**

Add to `src/db_manager.py`:

```python
def get_all_databases(self, exclude_system: bool = True) -> List[str]:
    # Execute "SHOW DATABASES"
    # Filter system databases if requested
```

**Step 7: Verify `get_all_databases`**

Run: `pytest tests/test_db_manager_cross_db.py::test_get_all_databases -v`
Expected: PASS

**Step 8: Commit**

```bash
git add src/db_manager.py tests/test_db_manager_cross_db.py
git commit -m "feat: add cross-database support to DatabaseManager"
```

### Task 2: Implement Cross-Database Table Inspection

**Files:**
- Modify: `src/db_manager.py`
- Test: `tests/test_db_manager_cross_db.py`

**Step 1: Write failing test for `get_tables_in_database`**

```python
def test_get_tables_in_database(db_manager):
    # Use a known database, e.g., 'parkcloud' if available, or mock
    # For test environment, maybe create a dummy db?
    # Or just mock the execution result
    pass 
```

**Step 2: Implement `get_tables_in_database`**

Add to `src/db_manager.py`:

```python
def get_tables_in_database(self, db_name: str) -> List[str]:
    # Query information_schema.TABLES where TABLE_SCHEMA = :db_name
```

**Step 3: Write failing test for `check_tables_structure_match`**

```python
def test_check_tables_structure_match(db_manager):
    # Mock two DBs with same structure
    assert db_manager.check_tables_structure_match("db1", "db2") == True
```

**Step 4: Implement `check_tables_structure_match`**

Add to `src/db_manager.py`:

```python
def check_tables_structure_match(self, db1: str, db2: str) -> bool:
    # Compare table counts
    # Compare table names
    # Compare columns (name, type) for each table
    # Return True if all match
```

**Step 5: Verify implementation**

Run: `pytest tests/test_db_manager_cross_db.py -v`

**Step 6: Commit**

```bash
git add src/db_manager.py tests/test_db_manager_cross_db.py
git commit -m "feat: add cross-database table inspection"
```

### Task 3: Upgrade Data Models

**Files:**
- Modify: `src/metadata/models.py`
- Create: `src/metadata/classification.py`

**Step 1: Create `DatabaseClassification` model**

Create `src/metadata/classification.py`:

```python
from enum import Enum
from pydantic import BaseModel
from typing import List, Optional

class DatabaseType(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    PARK_TEMPLATE = "park_template"
    PARK_INSTANCE = "park_instance"
    EXCLUDED = "excluded"

class DatabaseClassification(BaseModel):
    # ... implementation from design doc ...
```

**Step 2: Update `TableMetadata` in `src/metadata/models.py`**

```python
class TableMetadata(BaseModel):
    # ... existing fields ...
    database_name: str = ""
    namespace: str = ""
    is_template: bool = False
    template_for: List[str] = []
    template_source: Optional[str] = None
    
    @property
    def qualified_name(self) -> str:
        return f"{self.database_name}.{self.table_name}" if self.database_name else self.table_name
```

**Step 3: Update `KnowledgeGraph` in `src/metadata/models.py`**

```python
class KnowledgeGraph(BaseModel):
    # ... existing fields ...
    version: str = "2.0"
    namespaces: Dict[str, str] = {}
    template_mapping: Dict[str, str] = {}
    park_instances: List[str] = []
    database_classification: Dict[str, str] = {}
    
    # Add helper methods from design doc
```

**Step 4: Commit**

```bash
git add src/metadata/models.py src/metadata/classification.py
git commit -m "feat: upgrade data models for multi-db support"
```

### Task 4: Upgrade GraphStore for Namespaces

**Files:**
- Modify: `src/metadata/graph_store.py`
- Test: `tests/test_graph_store_namespace.py` (Create new)

**Step 1: Write failing test for namespace support**

```python
# tests/test_graph_store_namespace.py
def test_add_and_search_with_namespace(graph_store):
    # Create dummy TableMetadata
    # Add with namespace "ns1"
    # Search with namespace "ns1" -> should find it
    # Search with namespace "ns2" -> should NOT find it
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_graph_store_namespace.py -v`
Expected: FAIL

**Step 3: Update `add_table` / Implement `add_table_with_namespace`**

Modify `src/metadata/graph_store.py`:
- Update `add_table` to handle namespace (or create new method).
- Ensure `ids` in ChromaDB use `namespace.table_name` format.
- Ensure `metadatas` include `namespace` field.

**Step 4: Update `search` / Implement `search_with_namespace`**

Modify `src/metadata/graph_store.py`:
- Add `namespace` parameter to search methods.
- Pass `where={"namespace": namespace}` to ChromaDB query if provided.

**Step 5: Implement `clone_namespace`**

```python
def clone_namespace(self, source_ns: str, target_ns: str):
    # Get all embeddings for source_ns
    # Create new IDs and metadata for target_ns
    # Upsert to ChromaDB (reusing embeddings)
```

**Step 6: Verify all tests**

Run: `pytest tests/test_graph_store_namespace.py -v`

**Step 7: Commit**

```bash
git add src/metadata/graph_store.py tests/test_graph_store_namespace.py
git commit -m "feat: add namespace support to GraphStore"
```

### Task 5: Upgrade SchemaIndexer for Multi-DB Orchestration

**Files:**
- Modify: `src/metadata/schema_indexer.py`
- Test: `tests/test_schema_indexer_multi.py` (Create new)

**Step 1: Update `SchemaIndexer` initialization**

Modify `src/metadata/schema_indexer.py`:
- Initialize `DatabaseManager` with `specific_db=None` to allow cross-db queries.

**Step 2: Update `_extract_table_metadata` to support arbitrary database**

Current implementation uses `DATABASE()` in SQL.
- Change SQL to use `TABLE_SCHEMA = :db_name`.
- Update method signature: `_extract_table_metadata(self, db_name: str, table_name: str)`.

**Step 3: Implement `index_database` method**

Refactor `index_all_tables` into `index_database(self, db_name: str)`.
- It should only index tables in the specified `db_name`.

**Step 4: Implement `index_all_databases`**

```python
def index_all_databases(self):
    # 1. Get all DBs
    # 2. Classify DBs
    # 3. Index primary/secondary DBs
    # 4. Pick one park template, index it
    # 5. Clone template to other park instances
    # 6. Save KnowledgeGraph
```

**Step 5: Implement `index_park_template` and `clone_template_to_instances`**

**Step 6: Verify with integration test**

Create `tests/test_schema_indexer_multi.py`:
- Mock `DatabaseManager` to simulate multiple DBs.
- Verify `index_all_databases` calls `index_database` for distinct DBs and `clone_namespace` for park instances.

**Step 7: Commit**

```bash
git add src/metadata/schema_indexer.py tests/test_schema_indexer_multi.py
git commit -m "feat: implement multi-database indexing orchestration"
```
