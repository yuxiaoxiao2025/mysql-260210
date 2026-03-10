# 阶段三：增强功能层实施计划

> **For Claude:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现增量同步机制、知识库管理界面、原有模板转换

**Architecture:**
- 增量同步：启动时检测表结构变化，自动更新向量库
- 知识库管理：CLI命令查看/编辑概念映射
- 模板转换：将 business_knowledge.yaml 转换为概念映射

**Tech Stack:** Python 3.10+, SQLAlchemy, ChromaDB

**依赖：** 阶段一、阶段二已完成

---

## 文件结构

```
src/
├── metadata/
│   ├── schema_indexer.py            # 修改：添加版本哈希
│   └── change_detector.py           # 新建：表结构变化检测
│
├── memory/
│   └── template_converter.py        # 新建：模板转换器
│
├── cli/
│   └── knowledge_commands.py        # 新建：知识库管理命令
│
└── main.py                          # 修改：添加知识库命令

tests/
└── metadata/
    └── test_change_detector.py      # 新建
```

---

## Task 1: 创建表结构变化检测器

**Files:**
- Create: `src/metadata/change_detector.py`
- Test: `tests/metadata/test_change_detector.py`

- [ ] **Step 1: 创建变化检测器**

```python
# src/metadata/change_detector.py
"""
Database schema change detector.

Detects changes in table structure, field comments, and business semantics
to trigger automatic re-embedding when needed.
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

from sqlalchemy import text

from src.db_manager import DatabaseManager

logger = logging.getLogger(__name__)


@dataclass
class TableVersion:
    """表版本信息"""
    table_name: str
    version_hash: str
    column_count: int
    last_checked: datetime
    columns_hash: str = ""
    comment: str = ""


@dataclass
class ChangeDetectionResult:
    """变化检测结果"""
    added_tables: List[str] = field(default_factory=list)
    removed_tables: List[str] = field(default_factory=list)
    modified_tables: List[str] = field(default_factory=list)
    unchanged_tables: List[str] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.added_tables or self.removed_tables or self.modified_tables)

    @property
    def total_changes(self) -> int:
        return len(self.added_tables) + len(self.removed_tables) + len(self.modified_tables)


class SchemaChangeDetector:
    """
    表结构变化检测器

    通过计算表结构哈希来检测变化，触发增量同步。
    """

    VERSION_FILE = "data/dev/table_versions.json"

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        version_file: Optional[str] = None
    ):
        """
        初始化变化检测器。

        Args:
            db_manager: 数据库管理器
            version_file: 版本文件路径
        """
        self.db_manager = db_manager or DatabaseManager(specific_db=None)
        self.version_file = Path(version_file or self.VERSION_FILE)
        self.version_file.parent.mkdir(parents=True, exist_ok=True)

        self._versions: Dict[str, TableVersion] = {}
        self._load_versions()

        logger.info(f"SchemaChangeDetector initialized with {len(self._versions)} cached versions")

    def _load_versions(self) -> None:
        """加载版本缓存"""
        if not self.version_file.exists():
            return

        try:
            with open(self.version_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            for table_name, version_data in data.items():
                self._versions[table_name] = TableVersion(
                    table_name=table_name,
                    version_hash=version_data.get("version_hash", ""),
                    column_count=version_data.get("column_count", 0),
                    last_checked=datetime.fromisoformat(version_data["last_checked"])
                        if "last_checked" in version_data else datetime.now(),
                    columns_hash=version_data.get("columns_hash", ""),
                    comment=version_data.get("comment", ""),
                )

        except Exception as e:
            logger.warning(f"Failed to load version cache: {e}")

    def _save_versions(self) -> None:
        """保存版本缓存"""
        try:
            data = {}
            for table_name, version in self._versions.items():
                data[table_name] = {
                    "version_hash": version.version_hash,
                    "column_count": version.column_count,
                    "last_checked": version.last_checked.isoformat(),
                    "columns_hash": version.columns_hash,
                    "comment": version.comment,
                }

            with open(self.version_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.debug(f"Saved {len(data)} table versions")

        except Exception as e:
            logger.error(f"Failed to save version cache: {e}")

    def compute_table_hash(self, db_name: str, table_name: str) -> str:
        """
        计算表结构哈希。

        Args:
            db_name: 数据库名
            table_name: 表名

        Returns:
            哈希值
        """
        # 获取表结构信息
        columns_sql = """
            SELECT
                COLUMN_NAME,
                COLUMN_TYPE,
                COLUMN_COMMENT,
                IS_NULLABLE,
                COLUMN_KEY
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = :db_name AND TABLE_NAME = :table_name
            ORDER BY ORDINAL_POSITION
        """

        table_sql = """
            SELECT TABLE_COMMENT
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = :db_name AND TABLE_NAME = :table_name
        """

        hash_components = []

        with self.db_manager.get_connection() as conn:
            # 获取列信息
            columns_result = conn.execute(
                text(columns_sql),
                {"db_name": db_name, "table_name": table_name}
            )

            for row in columns_result:
                col_info = f"{row[0]}|{row[1]}|{row[2]}|{row[3]}|{row[4]}"
                hash_components.append(col_info)

            # 获取表注释
            table_result = conn.execute(
                text(table_sql),
                {"db_name": db_name, "table_name": table_name}
            )
            table_row = table_result.fetchone()
            if table_row:
                hash_components.append(f"TABLE_COMMENT:{table_row[0] or ''}")

        # 计算哈希
        hash_input = "\n".join(hash_components)
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]

    def detect_changes(
        self,
        db_name: str,
        tables: List[str]
    ) -> ChangeDetectionResult:
        """
        检测表结构变化。

        Args:
            db_name: 数据库名
            tables: 要检测的表列表

        Returns:
            变化检测结果
        """
        result = ChangeDetectionResult()

        current_tables = set(tables)
        cached_tables = set(self._versions.keys())

        # 新增的表
        result.added_tables = list(current_tables - cached_tables)

        # 已删除的表
        result.removed_tables = list(cached_tables - current_tables)

        # 检查现有表的变化
        for table_name in current_tables & cached_tables:
            current_hash = self.compute_table_hash(db_name, table_name)
            cached_hash = self._versions[table_name].version_hash

            if current_hash != cached_hash:
                result.modified_tables.append(table_name)
            else:
                result.unchanged_tables.append(table_name)

        logger.info(
            f"Change detection: {len(result.added_tables)} added, "
            f"{len(result.removed_tables)} removed, "
            f"{len(result.modified_tables)} modified"
        )

        return result

    def update_version(self, db_name: str, table_name: str) -> TableVersion:
        """
        更新表版本信息。

        Args:
            db_name: 数据库名
            table_name: 表名

        Returns:
            新的版本信息
        """
        version_hash = self.compute_table_hash(db_name, table_name)

        # 获取列数
        sql = """
            SELECT COUNT(*) as col_count
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = :db_name AND TABLE_NAME = :table_name
        """

        with self.db_manager.get_connection() as conn:
            result = conn.execute(
                text(sql),
                {"db_name": db_name, "table_name": table_name}
            )
            row = result.fetchone()
            column_count = row[0] if row else 0

        version = TableVersion(
            table_name=table_name,
            version_hash=version_hash,
            column_count=column_count,
            last_checked=datetime.now(),
        )

        self._versions[table_name] = version
        self._save_versions()

        logger.info(f"Updated version for {table_name}: {version_hash}")
        return version

    def get_tables_needing_reindex(
        self,
        db_name: str,
        tables: List[str]
    ) -> List[str]:
        """
        获取需要重新索引的表。

        Args:
            db_name: 数据库名
            tables: 表列表

        Returns:
            需要重新索引的表列表
        """
        result = self.detect_changes(db_name, tables)
        return result.added_tables + result.modified_tables

    def clear_cache(self) -> None:
        """清除版本缓存"""
        self._versions.clear()
        if self.version_file.exists():
            self.version_file.unlink()
        logger.info("Cleared version cache")
```

- [ ] **Step 2: 创建测试文件**

```python
# tests/metadata/test_change_detector.py
"""
Tests for schema change detector.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from src.metadata.change_detector import (
    SchemaChangeDetector,
    TableVersion,
    ChangeDetectionResult,
)


class TestSchemaChangeDetector:
    """变化检测器测试"""

    @pytest.fixture
    def mock_db_manager(self):
        """模拟数据库管理器"""
        mock = Mock()
        mock.get_connection.return_value.__enter__ = Mock()
        mock.get_connection.return_value.__exit__ = Mock()
        return mock

    @pytest.fixture
    def temp_version_file(self, tmp_path):
        """临时版本文件"""
        return str(tmp_path / "test_versions.json")

    @pytest.fixture
    def detector(self, mock_db_manager, temp_version_file):
        """创建检测器实例"""
        return SchemaChangeDetector(
            db_manager=mock_db_manager,
            version_file=temp_version_file
        )

    def test_detect_added_tables(self, detector):
        """测试检测新增表"""
        result = detector.detect_changes("test_db", ["new_table1", "new_table2"])

        assert len(result.added_tables) == 2
        assert result.has_changes is True

    def test_detect_unchanged_tables(self, detector):
        """测试检测未变化的表"""
        # 先添加版本
        detector._versions["existing_table"] = TableVersion(
            table_name="existing_table",
            version_hash="test_hash",
            column_count=5,
            last_checked=__import__("datetime").datetime.now()
        )

        # 模拟相同的哈希
        with patch.object(detector, 'compute_table_hash', return_value="test_hash"):
            result = detector.detect_changes("test_db", ["existing_table"])

        assert len(result.unchanged_tables) == 1
        assert result.has_changes is False

    def test_update_version(self, detector, mock_db_manager):
        """测试更新版本"""
        mock_conn = Mock()
        mock_conn.execute.return_value.fetchone.return_value = [5]
        mock_db_manager.get_connection.return_value.__enter__ = Mock(return_value=mock_conn)

        with patch.object(detector, 'compute_table_hash', return_value="new_hash"):
            version = detector.update_version("test_db", "test_table")

        assert version.version_hash == "new_hash"
        assert "test_table" in detector._versions

    def test_get_tables_needing_reindex(self, detector):
        """测试获取需要重新索引的表"""
        detector._versions["old_table"] = TableVersion(
            table_name="old_table",
            version_hash="old_hash",
            column_count=3,
            last_checked=__import__("datetime").datetime.now()
        )

        with patch.object(detector, 'compute_table_hash', return_value="old_hash"):
            tables = detector.get_tables_needing_reindex(
                "test_db",
                ["old_table", "new_table"]
            )

        # new_table 是新增的，应该需要重新索引
        assert "new_table" in tables

    def test_clear_cache(self, detector):
        """测试清除缓存"""
        detector._versions["test"] = TableVersion(
            table_name="test",
            version_hash="hash",
            column_count=1,
            last_checked=__import__("datetime").datetime.now()
        )

        detector.clear_cache()

        assert len(detector._versions) == 0
```

- [ ] **Step 3: 运行测试**

```bash
cd E:/trae/mysql-260210
python -m pytest tests/metadata/test_change_detector.py -v
```

- [ ] **Step 4: 提交**

```bash
git add src/metadata/change_detector.py tests/metadata/test_change_detector.py
git commit -m "feat(metadata): add schema change detector for incremental sync"
```

---

## Task 2: 集成增量同步到启动流程

**Files:**
- Modify: `src/metadata/schema_indexer.py`
- Modify: `src/main.py`

- [ ] **Step 1: 修改 schema_indexer.py 添加增量同步方法**

在 `SchemaIndexer` 类中添加：

```python
# src/metadata/schema_indexer.py
# 在 import 部分添加：
from src.metadata.change_detector import SchemaChangeDetector

# 在 __init__ 方法中添加：
def __init__(
    self,
    db_manager: Optional[DatabaseManager] = None,
    embedding_service: Optional[EmbeddingService] = None,
    graph_store: Optional[GraphStore] = None,
    env: str = "dev",
):
    # ... 现有代码 ...
    self.change_detector = SchemaChangeDetector(db_manager=self.db_manager)

# 添加新方法：
def incremental_sync(self) -> IndexResult:
    """
    增量同步：只索引有变化的表。

    Returns:
        索引结果
    """
    start_time = time.time()
    logger.info("Starting incremental schema sync")

    current_db = self._get_current_database_name()
    if not current_db:
        logger.error("No active database for incremental sync")
        return IndexResult(
            success=False,
            total_tables=0,
            indexed_tables=0,
            elapsed_seconds=time.time() - start_time,
        )

    # 获取所有表
    all_tables = self.db_manager.get_all_tables()

    # 检测变化
    tables_to_reindex = self.change_detector.get_tables_needing_reindex(
        current_db, all_tables
    )

    if not tables_to_reindex:
        logger.info("No changes detected, skipping reindex")
        return IndexResult(
            success=True,
            total_tables=len(all_tables),
            indexed_tables=0,
            elapsed_seconds=time.time() - start_time,
        )

    logger.info(f"Detected {len(tables_to_reindex)} tables needing reindex")

    # 重新索引变化的表
    knowledge_graph = self.graph_store.load_graph()
    failed_tables = []

    for table_name in tables_to_reindex:
        try:
            # 删除旧的向量
            self.graph_store.delete_table(table_name)

            # 重新索引
            self.index_single_table(table_name)

            # 更新版本
            self.change_detector.update_version(current_db, table_name)

        except Exception as e:
            logger.error(f"Failed to reindex {table_name}: {e}")
            failed_tables.append(table_name)

    # 保存知识图谱
    self.graph_store.save_graph(knowledge_graph)

    elapsed = time.time() - start_time
    logger.info(
        f"Incremental sync complete: {len(tables_to_reindex) - len(failed_tables)}/"
        f"{len(tables_to_reindex)} tables reindexed in {elapsed:.2f}s"
    )

    return IndexResult(
        success=len(failed_tables) == 0,
        total_tables=len(all_tables),
        indexed_tables=len(tables_to_reindex) - len(failed_tables),
        failed_tables=failed_tables,
        elapsed_seconds=elapsed,
    )
```

- [ ] **Step 2: 修改 main.py 添加启动时增量同步**

```python
# src/main.py
# 在启动流程中添加：

def check_and_sync_schema():
    """检查并同步表结构变化"""
    from src.metadata.schema_indexer import SchemaIndexer

    indexer = SchemaIndexer()
    result = indexer.incremental_sync()

    if result.indexed_tables > 0:
        print(f"已同步 {result.indexed_tables} 个表的结构变化")
    elif result.success:
        print("表结构无变化")
    else:
        print(f"同步失败: {result.failed_tables}")

# 在 main() 函数开头调用
def main():
    print("正在检查数据库结构变化...")
    check_and_sync_schema()

    # ... 其余启动代码 ...
```

- [ ] **Step 3: 运行测试验证**

```bash
cd E:/trae/mysql-260210
python -m pytest tests/metadata/ -v -k "incremental or change"
```

- [ ] **Step 4: 提交**

```bash
git add src/metadata/schema_indexer.py src/main.py
git commit -m "feat: integrate incremental sync into startup flow"
```

---

## Task 3: 创建知识库管理命令

**Files:**
- Create: `src/cli/knowledge_commands.py`
- Modify: `src/main.py`

- [ ] **Step 1: 创建知识库管理命令**

```python
# src/cli/knowledge_commands.py
"""
Knowledge base management commands.

Provides CLI commands for viewing, editing, and managing the knowledge base.
"""

import logging
from typing import Optional

from src.memory.concept_store import ConceptStoreService
from src.memory.memory_models import ConceptMapping

logger = logging.getLogger(__name__)


class KnowledgeCommands:
    """知识库管理命令"""

    def __init__(self, concept_store: Optional[ConceptStoreService] = None):
        """
        初始化知识库命令。

        Args:
            concept_store: 概念存储服务
        """
        self.concept_store = concept_store or ConceptStoreService()

    def list_concepts(self) -> None:
        """列出所有概念映射"""
        concepts = self.concept_store.get_all_concepts()

        if not concepts:
            print("知识库为空")
            return

        print(f"\n知识库 ({len(concepts)} 个概念):")
        print("-" * 60)

        for concept in concepts:
            terms = ", ".join(concept.user_terms)
            mapping = concept.database_mapping
            confidence = f"{concept.confidence:.0%}"

            print(f"ID: {concept.concept_id}")
            print(f"  用户说法: {terms}")
            print(f"  数据库映射: {mapping}")
            print(f"  置信度: {confidence}")
            print(f"  描述: {concept.description}")
            print()

    def show_concept(self, concept_id: str) -> None:
        """显示概念详情"""
        concept = self.concept_store.get_concept(concept_id)

        if not concept:
            print(f"概念 '{concept_id}' 不存在")
            return

        print(f"\n概念详情: {concept_id}")
        print("-" * 40)
        print(f"用户说法: {', '.join(concept.user_terms)}")
        print(f"数据库映射: {concept.database_mapping}")
        print(f"描述: {concept.description}")
        print(f"置信度: {concept.confidence:.0%}")
        print(f"确认次数: {concept.confirmed_count}")
        print(f"学习来源: {concept.learned_from}")
        print(f"创建时间: {concept.created_at}")
        print(f"更新时间: {concept.updated_at}")

    def search_concepts(self, query: str) -> None:
        """搜索概念"""
        results = self.concept_store.search_concepts(query)

        if not results:
            print(f"未找到匹配 '{query}' 的概念")
            return

        print(f"\n搜索结果 ({len(results)} 个):")
        print("-" * 40)

        for concept in results:
            print(f"- {concept.concept_id}: {', '.join(concept.user_terms[:3])}")

    def add_concept(
        self,
        concept_id: str,
        user_terms: str,
        description: str,
        db_mapping: str = ""
    ) -> None:
        """添加概念"""
        # 解析用户说法
        terms_list = [t.strip() for t in user_terms.split(",")]

        # 解析数据库映射
        mapping = {}
        if db_mapping:
            for part in db_mapping.split(","):
                if "=" in part:
                    key, value = part.split("=", 1)
                    mapping[key.strip()] = value.strip()

        concept = ConceptMapping(
            concept_id=concept_id,
            user_terms=terms_list,
            database_mapping=mapping,
            description=description,
            learned_from="manual"
        )

        self.concept_store.add_concept(concept)
        print(f"已添加概念: {concept_id}")

    def delete_concept(self, concept_id: str) -> None:
        """删除概念"""
        if self.concept_store.delete_concept(concept_id):
            print(f"已删除概念: {concept_id}")
        else:
            print(f"概念 '{concept_id}' 不存在")

    def show_stats(self) -> None:
        """显示知识库统计"""
        stats = self.concept_store.get_stats()

        print("\n知识库统计:")
        print("-" * 30)
        print(f"总概念数: {stats['total_concepts']}")
        print(f"高置信度: {stats['high_confidence']}")
        print(f"近7天学习: {stats['recently_learned']}")
        print(f"存储路径: {stats['storage_path']}")

    def show_help(self) -> None:
        """显示帮助"""
        print("""
知识库管理命令:

  kb list              列出所有概念
  kb show <id>         显示概念详情
  kb search <query>    搜索概念
  kb add <id> <terms> <desc> [mapping]  添加概念
  kb delete <id>       删除概念
  kb stats             显示统计信息

示例:
  kb list
  kb show parking_lot
  kb search 园区
  kb add test_concept "测试,试验" "测试概念" "table=test_table"
  kb delete test_concept
""")
```

- [ ] **Step 2: 在 main.py 中集成命令**

```python
# src/main.py
# 添加命令处理：

from src.cli.knowledge_commands import KnowledgeCommands

def handle_knowledge_command(args: list) -> bool:
    """处理知识库命令"""
    if not args:
        return False

    cmd = args[0]
    kb = KnowledgeCommands()

    if cmd == "list":
        kb.list_concepts()
    elif cmd == "show" and len(args) > 1:
        kb.show_concept(args[1])
    elif cmd == "search" and len(args) > 1:
        kb.search_concepts(args[1])
    elif cmd == "add" and len(args) >= 4:
        kb.add_concept(args[1], args[2], args[3], args[4] if len(args) > 4 else "")
    elif cmd == "delete" and len(args) > 1:
        kb.delete_concept(args[1])
    elif cmd == "stats":
        kb.show_stats()
    elif cmd == "help":
        kb.show_help()
    else:
        print("未知命令，输入 'kb help' 查看帮助")

    return True

# 在主循环中添加命令处理：
# if user_input.startswith("kb "):
#     handle_knowledge_command(user_input[3:].split())
#     continue
```

- [ ] **Step 3: 提交**

```bash
git add src/cli/knowledge_commands.py src/main.py
git commit -m "feat(cli): add knowledge base management commands

- kb list: list all concepts
- kb show: show concept details
- kb search: search concepts
- kb add/delete: manage concepts
- kb stats: show statistics"
```

---

## Task 4: 创建模板转换器

**Files:**
- Create: `src/memory/template_converter.py`
- Test: `tests/memory/test_template_converter.py`

- [ ] **Step 1: 创建模板转换器**

```python
# src/memory/template_converter.py
"""
Template converter for migrating business_knowledge.yaml to concept mappings.

Converts the old fixed template format to the new concept mapping format.
"""

import logging
from pathlib import Path
from typing import Dict, List, Any

import yaml

from src.memory.memory_models import ConceptMapping
from src.memory.concept_store import ConceptStoreService

logger = logging.getLogger(__name__)


class TemplateConverter:
    """
    模板转换器

    将 business_knowledge.yaml 转换为概念映射格式。
    """

    def __init__(self, concept_store: ConceptStoreService):
        """
        初始化转换器。

        Args:
            concept_store: 概念存储服务
        """
        self.concept_store = concept_store
        logger.info("TemplateConverter initialized")

    def convert_yaml_file(self, yaml_path: str) -> int:
        """
        转换 YAML 文件。

        Args:
            yaml_path: YAML 文件路径

        Returns:
            转换的概念数量
        """
        path = Path(yaml_path)
        if not path.exists():
            logger.warning(f"YAML file not found: {yaml_path}")
            return 0

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return self.convert_yaml_data(data)

    def convert_yaml_data(self, data: Dict[str, Any]) -> int:
        """
        转换 YAML 数据。

        Args:
            data: YAML 数据

        Returns:
            转换的概念数量
        """
        count = 0

        # 转换操作定义
        operations = data.get("operations", {})
        for op_name, op_def in operations.items():
            concept = self._convert_operation(op_name, op_def)
            if concept:
                self.concept_store.add_concept(concept)
                count += 1

        # 转换字段映射
        field_mappings = data.get("field_mappings", {})
        for field_name, mapping in field_mappings.items():
            concept = self._convert_field_mapping(field_name, mapping)
            if concept:
                self.concept_store.add_concept(concept)
                count += 1

        # 转换业务规则
        business_rules = data.get("business_rules", {})
        for rule_name, rule in business_rules.items():
            concept = self._convert_business_rule(rule_name, rule)
            if concept:
                self.concept_store.add_concept(concept)
                count += 1

        logger.info(f"Converted {count} concepts from template")
        return count

    def _convert_operation(
        self,
        op_name: str,
        op_def: Dict[str, Any]
    ) -> ConceptMapping:
        """转换操作定义"""
        # 提取用户说法
        user_terms = []
        for trigger in op_def.get("triggers", []):
            if isinstance(trigger, str):
                user_terms.append(trigger)
            elif isinstance(trigger, dict):
                user_terms.extend(trigger.keys())

        if not user_terms:
            user_terms = [op_name]

        # 构建数据库映射
        db_mapping = {
            "operation": op_name,
            "type": op_def.get("type", "unknown"),
        }

        if "tables" in op_def:
            db_mapping["tables"] = op_def["tables"]

        return ConceptMapping(
            concept_id=f"op_{op_name}",
            user_terms=user_terms,
            database_mapping=db_mapping,
            description=op_def.get("description", f"操作: {op_name}"),
            learned_from="template_conversion",
            confidence=0.8,
        )

    def _convert_field_mapping(
        self,
        field_name: str,
        mapping: Dict[str, Any]
    ) -> ConceptMapping:
        """转换字段映射"""
        return ConceptMapping(
            concept_id=f"field_{field_name}",
            user_terms=[field_name],
            database_mapping={
                "table": mapping.get("table", ""),
                "column": mapping.get("column", field_name),
            },
            description=mapping.get("description", f"字段: {field_name}"),
            learned_from="template_conversion",
            confidence=0.7,
        )

    def _convert_business_rule(
        self,
        rule_name: str,
        rule: Dict[str, Any]
    ) -> ConceptMapping:
        """转换业务规则"""
        return ConceptMapping(
            concept_id=f"rule_{rule_name}",
            user_terms=[rule_name],
            database_mapping={
                "rule": rule_name,
                "condition": str(rule.get("condition", "")),
            },
            description=rule.get("description", f"规则: {rule_name}"),
            learned_from="template_conversion",
            confidence=0.6,
        )

    def get_conversion_report(self) -> Dict[str, Any]:
        """获取转换报告"""
        concepts = self.concept_store.get_all_concepts()

        by_source = {}
        for concept in concepts:
            source = concept.learned_from
            by_source[source] = by_source.get(source, 0) + 1

        return {
            "total_concepts": len(concepts),
            "by_source": by_source,
            "template_converted": by_source.get("template_conversion", 0),
        }
```

- [ ] **Step 2: 创建测试文件**

```python
# tests/memory/test_template_converter.py
"""
Tests for template converter.
"""

import pytest
from unittest.mock import Mock

from src.memory.template_converter import TemplateConverter
from src.memory.concept_store import ConceptStoreService
from src.memory.memory_models import ConceptMapping


class TestTemplateConverter:
    """模板转换器测试"""

    @pytest.fixture
    def mock_concept_store(self):
        """模拟概念存储服务"""
        mock = Mock(spec=ConceptStoreService)
        mock.get_all_concepts.return_value = []
        return mock

    @pytest.fixture
    def converter(self, mock_concept_store):
        """创建转换器实例"""
        return TemplateConverter(concept_store=mock_concept_store)

    def test_convert_operation(self, converter, mock_concept_store):
        """测试转换操作定义"""
        data = {
            "operations": {
                "plate_query": {
                    "type": "query",
                    "triggers": ["查车牌", "查询车牌"],
                    "description": "查询车牌信息",
                    "tables": ["cloud_fixed_plate"]
                }
            }
        }

        count = converter.convert_yaml_data(data)

        assert count == 1
        mock_concept_store.add_concept.assert_called_once()

    def test_convert_field_mapping(self, converter, mock_concept_store):
        """测试转换字段映射"""
        data = {
            "field_mappings": {
                "内部车辆": {
                    "table": "cloud_fixed_plate",
                    "column": "plate",
                    "description": "内部车辆表"
                }
            }
        }

        count = converter.convert_yaml_data(data)

        assert count == 1

    def test_convert_multiple_sections(self, converter, mock_concept_store):
        """测试转换多个部分"""
        data = {
            "operations": {
                "test_op": {
                    "type": "query",
                    "triggers": ["测试"],
                    "description": "测试操作"
                }
            },
            "field_mappings": {
                "test_field": {
                    "table": "test_table",
                    "description": "测试字段"
                }
            }
        }

        count = converter.convert_yaml_data(data)

        assert count == 2

    def test_get_conversion_report(self, converter, mock_concept_store):
        """测试获取转换报告"""
        mock_concept_store.get_all_concepts.return_value = [
            ConceptMapping(
                concept_id="test1",
                user_terms=["测试1"],
                learned_from="template_conversion"
            ),
            ConceptMapping(
                concept_id="test2",
                user_terms=["测试2"],
                learned_from="dialogue"
            ),
        ]

        report = converter.get_conversion_report()

        assert report["total_concepts"] == 2
        assert report["template_converted"] == 1
```

- [ ] **Step 3: 运行测试**

```bash
cd E:/trae/mysql-260210
python -m pytest tests/memory/test_template_converter.py -v
```

- [ ] **Step 4: 提交**

```bash
git add src/memory/template_converter.py tests/memory/test_template_converter.py
git commit -m "feat(memory): add template converter for yaml to concept mapping"
```

---

## Task 5: 运行完整测试并提交

- [ ] **Step 1: 运行所有测试**

```bash
cd E:/trae/mysql-260210
python -m pytest tests/ -v --tb=short
```

- [ ] **Step 2: 更新 README**

```markdown
# 在 README.md 中添加：

## 知识库管理

系统启动时会自动检查表结构变化并同步。

### 命令行管理

- `kb list` - 列出所有概念映射
- `kb show <id>` - 显示概念详情
- `kb search <query>` - 搜索概念
- `kb add <id> <terms> <desc>` - 添加概念
- `kb delete <id>` - 删除概念
- `kb stats` - 显示统计信息

### 增量同步

启动时自动检测表结构变化，只重新索引有变化的表。
```

- [ ] **Step 3: 最终提交**

```bash
git add .
git commit -m "feat: complete phase 3 - enhanced features

- Add incremental schema sync on startup
- Add knowledge base management CLI commands
- Add template converter for yaml to concept mapping
- Update documentation"
```

---

## 阶段三完成检查

- [ ] 所有测试通过
- [ ] 增量同步机制可用
- [ ] 知识库管理命令可用
- [ ] 模板转换器可用
- [ ] 文档已更新

**全部三个阶段完成后，系统将实现：**
1. 启动时自动检测表结构变化
2. 首次使用时启动向导初始化知识库
3. 对话时"不懂就问"并记住答案
4. 100轮对话上下文记忆
5. 知识库可随时查看和管理