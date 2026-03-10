# 阶段一：基础设施层实施计划

> **For Claude:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立知识库存储系统和上下文记忆系统，修复 Rerank 预算问题

**Architecture:**
- 知识库使用 JSON 文件存储概念映射，支持向量检索
- 上下文记忆使用内存 + 文件持久化，支持100轮对话
- Rerank 预算从 500ms 调整到 1000ms

**Tech Stack:** Python 3.10+, Pydantic, ChromaDB, DashScope

---

## 文件结构

```
src/
├── memory/                          # 新建：记忆系统模块
│   ├── __init__.py
│   ├── concept_store.py             # 概念映射存储
│   ├── context_memory.py            # 上下文记忆
│   └── memory_models.py             # 数据模型
│
├── metadata/
│   └── retrieval_pipeline.py        # 修改：Rerank 预算调整
│
└── config.py                        # 修改：新增配置项

data/
└── dev/
    └── knowledge_base/              # 新建：知识库存储目录
        ├── concepts.json            # 概念映射
        └── context_history.json     # 对话历史
```

---

## Task 1: 创建记忆系统数据模型

**Files:**
- Create: `src/memory/__init__.py`
- Create: `src/memory/memory_models.py`
- Test: `tests/memory/test_memory_models.py`

- [ ] **Step 1: 创建记忆系统模块目录**

```bash
mkdir -p E:/trae/mysql-260210/src/memory
mkdir -p E:/trae/mysql-260210/data/dev/knowledge_base
mkdir -p E:/trae/mysql-260210/tests/memory
```

- [ ] **Step 2: 创建 `__init__.py`**

```python
# src/memory/__init__.py
"""
Memory system for intelligent dialogue.

Provides concept storage and context memory for the parking database assistant.
"""

from src.memory.memory_models import (
    ConceptMapping,
    ContextEntry,
    ConversationMemory,
    ConceptStore,
)
from src.memory.concept_store import ConceptStore
from src.memory.context_memory import ContextMemory

__all__ = [
    "ConceptMapping",
    "ContextEntry",
    "ConversationMemory",
    "ConceptStore",
    "ContextMemory",
]
```

- [ ] **Step 3: 创建数据模型 `memory_models.py`**

```python
# src/memory/memory_models.py
"""
Data models for memory system.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ConceptMapping(BaseModel):
    """概念映射模型：用户说法 -> 数据库对应"""

    concept_id: str = Field(..., description="概念唯一标识")
    user_terms: List[str] = Field(default_factory=list, description="用户说法列表")
    database_mapping: Dict[str, Any] = Field(
        default_factory=dict,
        description="数据库映射信息"
    )
    description: str = Field(default="", description="概念描述")
    learned_from: str = Field(default="dialogue", description="学习来源")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    confirmed_count: int = Field(default=0, description="确认次数")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="置信度")

    def add_user_term(self, term: str) -> None:
        """添加用户说法"""
        if term not in self.user_terms:
            self.user_terms.append(term)
            self.updated_at = datetime.now()

    def confirm(self) -> None:
        """确认概念，增加置信度"""
        self.confirmed_count += 1
        self.confidence = min(1.0, 0.5 + self.confirmed_count * 0.1)
        self.updated_at = datetime.now()


class ContextEntry(BaseModel):
    """上下文条目：单轮对话记录"""

    role: str = Field(..., description="角色: user/assistant")
    content: str = Field(..., description="对话内容")
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")

    # 提取的关键信息
    mentioned_plates: List[str] = Field(default_factory=list, description="提到的车牌")
    mentioned_parks: List[str] = Field(default_factory=list, description="提到的园区")
    mentioned_concepts: List[str] = Field(default_factory=list, description="提到的概念")
    operation_performed: Optional[str] = Field(default=None, description="执行的操作")
    correction_made: Optional[str] = Field(default=None, description="纠正的内容")


class ConversationMemory(BaseModel):
    """对话记忆：管理多轮对话上下文"""

    entries: List[ContextEntry] = Field(default_factory=list, description="对话条目列表")
    max_entries: int = Field(default=100, description="最大保留条目数")

    # 快速访问的关键信息
    current_plate: Optional[str] = Field(default=None, description="当前车牌")
    current_park: Optional[str] = Field(default=None, description="当前园区")
    current_intent: Optional[str] = Field(default=None, description="当前意图")

    # 累计信息
    all_mentioned_plates: List[str] = Field(default_factory=list, description="所有提到的车牌")
    performed_operations: List[str] = Field(default_factory=list, description="执行过的操作")
    corrections: List[str] = Field(default_factory=list, description="纠正记录")

    def add_entry(self, entry: ContextEntry) -> None:
        """添加对话条目"""
        self.entries.append(entry)

        # 更新快速访问信息
        if entry.mentioned_plates:
            self.current_plate = entry.mentioned_plates[-1]
            for plate in entry.mentioned_plates:
                if plate not in self.all_mentioned_plates:
                    self.all_mentioned_plates.append(plate)

        if entry.mentioned_parks:
            self.current_park = entry.mentioned_parks[-1]

        if entry.metadata.get("intent"):
            self.current_intent = entry.metadata["intent"]

        if entry.operation_performed:
            self.performed_operations.append(entry.operation_performed)

        if entry.correction_made:
            self.corrections.append(entry.correction_made)

        # 超过限制时移除最早的条目
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries:]

    def get_recent_entries(self, n: int = 10) -> List[ContextEntry]:
        """获取最近 n 条对话"""
        return self.entries[-n:] if self.entries else []

    def get_summary(self) -> str:
        """获取对话摘要"""
        parts = []

        if self.current_plate:
            parts.append(f"最近车牌: {self.current_plate}")

        if self.current_intent:
            parts.append(f"当前需求: {self.current_intent}")

        if self.performed_operations:
            parts.append(f"已做操作: {', '.join(self.performed_operations[-3:])}")

        if self.corrections:
            parts.append(f"纠正记录: {', '.join(self.corrections[-2:])}")

        return " | ".join(parts) if parts else "暂无上下文信息"

    def clear(self) -> None:
        """清空记忆"""
        self.entries.clear()
        self.current_plate = None
        self.current_park = None
        self.current_intent = None
        self.all_mentioned_plates.clear()
        self.performed_operations.clear()
        self.corrections.clear()


class ConceptStore(BaseModel):
    """概念知识库"""

    concepts: Dict[str, ConceptMapping] = Field(default_factory=dict)
    version: str = Field(default="1.0.0")
    last_updated: datetime = Field(default_factory=datetime.now)

    def add_concept(self, concept: ConceptMapping) -> None:
        """添加概念"""
        self.concepts[concept.concept_id] = concept
        self.last_updated = datetime.now()

    def get_concept(self, concept_id: str) -> Optional[ConceptMapping]:
        """获取概念"""
        return self.concepts.get(concept_id)

    def find_by_user_term(self, term: str) -> Optional[ConceptMapping]:
        """根据用户说法查找概念"""
        term_lower = term.lower()
        for concept in self.concepts.values():
            if term_lower in [t.lower() for t in concept.user_terms]:
                return concept
        return None

    def get_all_concepts(self) -> List[ConceptMapping]:
        """获取所有概念"""
        return list(self.concepts.values())

    def delete_concept(self, concept_id: str) -> bool:
        """删除概念"""
        if concept_id in self.concepts:
            del self.concepts[concept_id]
            self.last_updated = datetime.now()
            return True
        return False
```

- [ ] **Step 4: 创建测试文件 `test_memory_models.py`**

```python
# tests/memory/test_memory_models.py
"""
Tests for memory system data models.
"""

import pytest
from datetime import datetime

from src.memory.memory_models import (
    ConceptMapping,
    ContextEntry,
    ConversationMemory,
    ConceptStore,
)


class TestConceptMapping:
    """概念映射测试"""

    def test_create_concept(self):
        """测试创建概念"""
        concept = ConceptMapping(
            concept_id="parking_lot",
            user_terms=["园区", "场库"],
            database_mapping={"table": "parkcloud.cloud_park"},
            description="园区信息表"
        )

        assert concept.concept_id == "parking_lot"
        assert "园区" in concept.user_terms
        assert concept.confidence == 0.5

    def test_add_user_term(self):
        """测试添加用户说法"""
        concept = ConceptMapping(
            concept_id="parking_lot",
            user_terms=["园区"]
        )

        concept.add_user_term("停车场")

        assert "停车场" in concept.user_terms
        assert "园区" in concept.user_terms

    def test_confirm_increases_confidence(self):
        """测试确认增加置信度"""
        concept = ConceptMapping(concept_id="test")

        concept.confirm()
        assert concept.confidence == 0.6
        assert concept.confirmed_count == 1

        concept.confirm()
        assert concept.confidence == 0.7


class TestContextEntry:
    """上下文条目测试"""

    def test_create_entry(self):
        """测试创建对话条目"""
        entry = ContextEntry(
            role="user",
            content="查一下沪BAB1565的信息",
            mentioned_plates=["沪BAB1565"]
        )

        assert entry.role == "user"
        assert "沪BAB1565" in entry.mentioned_plates

    def test_entry_with_operation(self):
        """测试带操作记录的条目"""
        entry = ContextEntry(
            role="assistant",
            content="已查询车牌信息",
            operation_performed="plate_query",
            mentioned_plates=["沪BAB1565"]
        )

        assert entry.operation_performed == "plate_query"


class TestConversationMemory:
    """对话记忆测试"""

    def test_add_entry(self):
        """测试添加对话条目"""
        memory = ConversationMemory()

        entry = ContextEntry(
            role="user",
            content="查一下沪BAB1565",
            mentioned_plates=["沪BAB1565"]
        )
        memory.add_entry(entry)

        assert len(memory.entries) == 1
        assert memory.current_plate == "沪BAB1565"

    def test_track_multiple_plates(self):
        """测试追踪多个车牌"""
        memory = ConversationMemory()

        memory.add_entry(ContextEntry(
            role="user",
            content="查沪A12345",
            mentioned_plates=["沪A12345"]
        ))
        memory.add_entry(ContextEntry(
            role="user",
            content="再查沪B67890",
            mentioned_plates=["沪B67890"]
        ))

        assert memory.current_plate == "沪B67890"
        assert "沪A12345" in memory.all_mentioned_plates
        assert "沪B67890" in memory.all_mentioned_plates

    def test_get_summary(self):
        """测试获取摘要"""
        memory = ConversationMemory()
        memory.current_plate = "沪BAB1565"
        memory.current_intent = "查询进出场记录"
        memory.performed_operations = ["plate_query", "park_bindings"]

        summary = memory.get_summary()

        assert "沪BAB1565" in summary
        assert "查询进出场记录" in summary

    def test_max_entries_limit(self):
        """测试最大条目限制"""
        memory = ConversationMemory(max_entries=5)

        for i in range(10):
            memory.add_entry(ContextEntry(
                role="user",
                content=f"消息{i}"
            ))

        assert len(memory.entries) == 5
        assert memory.entries[0].content == "消息5"


class TestConceptStore:
    """概念知识库测试"""

    def test_add_and_get_concept(self):
        """测试添加和获取概念"""
        store = ConceptStore()

        concept = ConceptMapping(
            concept_id="internal_vehicle",
            user_terms=["内部车辆", "固定车"],
            database_mapping={"table": "cloud_fixed_plate"}
        )

        store.add_concept(concept)

        assert store.get_concept("internal_vehicle") == concept

    def test_find_by_user_term(self):
        """测试根据用户说法查找"""
        store = ConceptStore()

        store.add_concept(ConceptMapping(
            concept_id="parking_lot",
            user_terms=["园区", "场库", "停车场"]
        ))

        result = store.find_by_user_term("园区")
        assert result is not None
        assert result.concept_id == "parking_lot"

        result = store.find_by_user_term("不存在的说法")
        assert result is None

    def test_delete_concept(self):
        """测试删除概念"""
        store = ConceptStore()

        store.add_concept(ConceptMapping(concept_id="test"))
        assert store.get_concept("test") is not None

        store.delete_concept("test")
        assert store.get_concept("test") is None
```

- [ ] **Step 5: 运行测试验证模型正确**

```bash
cd E:/trae/mysql-260210
python -m pytest tests/memory/test_memory_models.py -v
```

Expected: 所有测试通过

- [ ] **Step 6: 提交**

```bash
git add src/memory/ tests/memory/
git commit -m "feat(memory): add memory system data models

- Add ConceptMapping for user term -> database mapping
- Add ContextEntry for dialogue entry tracking
- Add ConversationMemory for 100-turn context management
- Add ConceptStore for knowledge base storage"
```

---

## Task 2: 实现概念存储服务

**Files:**
- Create: `src/memory/concept_store.py`
- Test: `tests/memory/test_concept_store.py`

- [ ] **Step 1: 创建概念存储服务**

```python
# src/memory/concept_store.py
"""
Concept store service for knowledge base management.

Provides persistent storage and retrieval of concept mappings.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from src.memory.memory_models import ConceptMapping, ConceptStore

logger = logging.getLogger(__name__)


class ConceptStoreService:
    """
    概念存储服务

    负责概念映射的持久化存储和检索。
    """

    DEFAULT_STORAGE_PATH = "data/dev/knowledge_base/concepts.json"

    def __init__(self, storage_path: Optional[str] = None):
        """
        初始化概念存储服务。

        Args:
            storage_path: 存储文件路径，默认使用 data/dev/knowledge_base/concepts.json
        """
        self.storage_path = Path(storage_path or self.DEFAULT_STORAGE_PATH)
        self._store: Optional[ConceptStore] = None

        # 确保目录存在
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"ConceptStoreService initialized with path={self.storage_path}")

    @property
    def store(self) -> ConceptStore:
        """获取概念存储，延迟加载"""
        if self._store is None:
            self._store = self._load()
        return self._store

    def _load(self) -> ConceptStore:
        """从文件加载概念存储"""
        if not self.storage_path.exists():
            logger.info("No existing concept store, creating new one")
            return ConceptStore()

        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 重建 ConceptMapping 对象
            concepts = {}
            for concept_id, concept_data in data.get("concepts", {}).items():
                concepts[concept_id] = ConceptMapping(**concept_data)

            store = ConceptStore(
                concepts=concepts,
                version=data.get("version", "1.0.0"),
                last_updated=datetime.fromisoformat(data["last_updated"])
                    if "last_updated" in data else datetime.now()
            )

            logger.info(f"Loaded {len(concepts)} concepts from storage")
            return store

        except Exception as e:
            logger.error(f"Failed to load concept store: {e}")
            return ConceptStore()

    def _save(self) -> None:
        """保存概念存储到文件"""
        try:
            data = {
                "version": self.store.version,
                "last_updated": self.store.last_updated.isoformat(),
                "concepts": {
                    concept_id: concept.model_dump()
                    for concept_id, concept in self.store.concepts.items()
                }
            }

            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.debug(f"Saved {len(self.store.concepts)} concepts to storage")

        except Exception as e:
            logger.error(f"Failed to save concept store: {e}")
            raise

    def add_concept(self, concept: ConceptMapping) -> None:
        """
        添加概念映射。

        Args:
            concept: 要添加的概念映射
        """
        self.store.add_concept(concept)
        self._save()
        logger.info(f"Added concept: {concept.concept_id}")

    def get_concept(self, concept_id: str) -> Optional[ConceptMapping]:
        """
        获取概念映射。

        Args:
            concept_id: 概念ID

        Returns:
            概念映射，不存在则返回 None
        """
        return self.store.get_concept(concept_id)

    def find_by_user_term(self, term: str) -> Optional[ConceptMapping]:
        """
        根据用户说法查找概念。

        Args:
            term: 用户说法

        Returns:
            匹配的概念映射，未找到则返回 None
        """
        return self.store.find_by_user_term(term)

    def search_concepts(self, query: str) -> List[ConceptMapping]:
        """
        搜索概念。

        Args:
            query: 搜索关键词

        Returns:
            匹配的概念列表
        """
        results = []
        query_lower = query.lower()

        for concept in self.store.get_all_concepts():
            # 搜索用户说法
            if any(query_lower in t.lower() for t in concept.user_terms):
                results.append(concept)
                continue

            # 搜索描述
            if query_lower in concept.description.lower():
                results.append(concept)
                continue

            # 搜索数据库映射
            db_mapping = str(concept.database_mapping).lower()
            if query_lower in db_mapping:
                results.append(concept)

        return results

    def update_concept(self, concept_id: str, updates: dict) -> bool:
        """
        更新概念映射。

        Args:
            concept_id: 概念ID
            updates: 更新内容

        Returns:
            是否更新成功
        """
        concept = self.store.get_concept(concept_id)
        if not concept:
            return False

        for key, value in updates.items():
            if hasattr(concept, key):
                setattr(concept, key, value)

        concept.updated_at = datetime.now()
        self._save()

        logger.info(f"Updated concept: {concept_id}")
        return True

    def delete_concept(self, concept_id: str) -> bool:
        """
        删除概念映射。

        Args:
            concept_id: 概念ID

        Returns:
            是否删除成功
        """
        result = self.store.delete_concept(concept_id)
        if result:
            self._save()
            logger.info(f"Deleted concept: {concept_id}")
        return result

    def get_all_concepts(self) -> List[ConceptMapping]:
        """
        获取所有概念映射。

        Returns:
            所有概念映射列表
        """
        return self.store.get_all_concepts()

    def confirm_concept(self, concept_id: str) -> bool:
        """
        确认概念，增加置信度。

        Args:
            concept_id: 概念ID

        Returns:
            是否确认成功
        """
        concept = self.store.get_concept(concept_id)
        if not concept:
            return False

        concept.confirm()
        self._save()

        logger.info(f"Confirmed concept: {concept_id}, confidence={concept.confidence}")
        return True

    def is_empty(self) -> bool:
        """检查知识库是否为空"""
        return len(self.store.concepts) == 0

    def get_stats(self) -> dict:
        """获取知识库统计信息"""
        concepts = self.store.get_all_concepts()

        return {
            "total_concepts": len(concepts),
            "high_confidence": sum(1 for c in concepts if c.confidence >= 0.8),
            "recently_learned": sum(
                1 for c in concepts
                if (datetime.now() - c.created_at).days < 7
            ),
            "storage_path": str(self.storage_path),
        }
```

- [ ] **Step 2: 创建测试文件**

```python
# tests/memory/test_concept_store.py
"""
Tests for concept store service.
"""

import pytest
import tempfile
import os
from pathlib import Path

from src.memory.concept_store import ConceptStoreService
from src.memory.memory_models import ConceptMapping


class TestConceptStoreService:
    """概念存储服务测试"""

    @pytest.fixture
    def temp_storage(self, tmp_path):
        """创建临时存储路径"""
        return str(tmp_path / "test_concepts.json")

    @pytest.fixture
    def store_service(self, temp_storage):
        """创建存储服务实例"""
        return ConceptStoreService(storage_path=temp_storage)

    def test_add_and_get_concept(self, store_service):
        """测试添加和获取概念"""
        concept = ConceptMapping(
            concept_id="test_concept",
            user_terms=["测试说法"],
            database_mapping={"table": "test_table"}
        )

        store_service.add_concept(concept)

        result = store_service.get_concept("test_concept")
        assert result is not None
        assert result.concept_id == "test_concept"

    def test_find_by_user_term(self, store_service):
        """测试根据用户说法查找"""
        store_service.add_concept(ConceptMapping(
            concept_id="parking_lot",
            user_terms=["园区", "场库"]
        ))

        result = store_service.find_by_user_term("园区")
        assert result is not None
        assert result.concept_id == "parking_lot"

    def test_persistence(self, temp_storage):
        """测试持久化"""
        # 创建并添加概念
        service1 = ConceptStoreService(storage_path=temp_storage)
        service1.add_concept(ConceptMapping(
            concept_id="persist_test",
            user_terms=["持久化测试"]
        ))

        # 重新加载，验证持久化
        service2 = ConceptStoreService(storage_path=temp_storage)
        result = service2.get_concept("persist_test")

        assert result is not None
        assert "持久化测试" in result.user_terms

    def test_search_concepts(self, store_service):
        """测试搜索概念"""
        store_service.add_concept(ConceptMapping(
            concept_id="parking_lot",
            user_terms=["园区"],
            description="停车场信息"
        ))
        store_service.add_concept(ConceptMapping(
            concept_id="vehicle",
            user_terms=["车辆"],
            description="车辆信息"
        ))

        results = store_service.search_concepts("园区")
        assert len(results) == 1
        assert results[0].concept_id == "parking_lot"

    def test_delete_concept(self, store_service):
        """测试删除概念"""
        store_service.add_concept(ConceptMapping(
            concept_id="to_delete",
            user_terms=["待删除"]
        ))

        assert store_service.get_concept("to_delete") is not None

        store_service.delete_concept("to_delete")

        assert store_service.get_concept("to_delete") is None

    def test_is_empty(self, store_service):
        """测试检查空知识库"""
        assert store_service.is_empty() is True

        store_service.add_concept(ConceptMapping(
            concept_id="test",
            user_terms=["测试"]
        ))

        assert store_service.is_empty() is False
```

- [ ] **Step 3: 运行测试**

```bash
cd E:/trae/mysql-260210
python -m pytest tests/memory/test_concept_store.py -v
```

- [ ] **Step 4: 提交**

```bash
git add src/memory/concept_store.py tests/memory/test_concept_store.py
git commit -m "feat(memory): add concept store service with persistence"
```

---

## Task 3: 实现上下文记忆服务

**Files:**
- Create: `src/memory/context_memory.py`
- Test: `tests/memory/test_context_memory.py`

- [ ] **Step 1: 创建上下文记忆服务**

```python
# src/memory/context_memory.py
"""
Context memory service for dialogue history management.

Provides 100-turn conversation memory with key information extraction.
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from src.memory.memory_models import ContextEntry, ConversationMemory

logger = logging.getLogger(__name__)


# 车牌号正则表达式
PLATE_PATTERN = re.compile(
    r'[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼]'
    r'[A-Z][A-Z0-9]{4,5}[A-Z0-9]'
)


class ContextMemoryService:
    """
    上下文记忆服务

    管理对话历史，追踪关键信息（车牌、园区、意图等）。
    支持100轮对话记忆和持久化存储。
    """

    DEFAULT_STORAGE_PATH = "data/dev/knowledge_base/context_history.json"

    def __init__(
        self,
        storage_path: Optional[str] = None,
        max_entries: int = 100
    ):
        """
        初始化上下文记忆服务。

        Args:
            storage_path: 存储文件路径
            max_entries: 最大保留对话条目数
        """
        self.storage_path = Path(storage_path or self.DEFAULT_STORAGE_PATH)
        self.max_entries = max_entries
        self._memory: Optional[ConversationMemory] = None

        # 确保目录存在
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"ContextMemoryService initialized with max_entries={max_entries}")

    @property
    def memory(self) -> ConversationMemory:
        """获取对话记忆，延迟加载"""
        if self._memory is None:
            self._memory = self._load()
        return self._memory

    def _load(self) -> ConversationMemory:
        """从文件加载对话记忆"""
        if not self.storage_path.exists():
            logger.info("No existing context memory, creating new one")
            return ConversationMemory(max_entries=self.max_entries)

        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            entries = [
                ContextEntry(**entry_data)
                for entry_data in data.get("entries", [])
            ]

            memory = ConversationMemory(
                entries=entries,
                max_entries=self.max_entries,
                current_plate=data.get("current_plate"),
                current_park=data.get("current_park"),
                current_intent=data.get("current_intent"),
                all_mentioned_plates=data.get("all_mentioned_plates", []),
                performed_operations=data.get("performed_operations", []),
                corrections=data.get("corrections", []),
            )

            logger.info(f"Loaded {len(entries)} context entries")
            return memory

        except Exception as e:
            logger.error(f"Failed to load context memory: {e}")
            return ConversationMemory(max_entries=self.max_entries)

    def _save(self) -> None:
        """保存对话记忆到文件"""
        try:
            data = {
                "entries": [entry.model_dump() for entry in self.memory.entries],
                "current_plate": self.memory.current_plate,
                "current_park": self.memory.current_park,
                "current_intent": self.memory.current_intent,
                "all_mentioned_plates": self.memory.all_mentioned_plates,
                "performed_operations": self.memory.performed_operations,
                "corrections": self.memory.corrections,
                "last_saved": datetime.now().isoformat(),
            }

            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.debug(f"Saved {len(self.memory.entries)} context entries")

        except Exception as e:
            logger.error(f"Failed to save context memory: {e}")

    def add_user_message(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ContextEntry:
        """
        添加用户消息。

        Args:
            content: 消息内容
            metadata: 元数据

        Returns:
            创建的对话条目
        """
        # 提取车牌
        plates = self._extract_plates(content)

        # 创建条目
        entry = ContextEntry(
            role="user",
            content=content,
            mentioned_plates=plates,
            metadata=metadata or {}
        )

        self.memory.add_entry(entry)
        self._save()

        logger.debug(f"Added user message: {content[:50]}...")
        return entry

    def add_assistant_message(
        self,
        content: str,
        operation_performed: Optional[str] = None,
        correction_made: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ContextEntry:
        """
        添加助手消息。

        Args:
            content: 消息内容
            operation_performed: 执行的操作
            correction_made: 纠正的内容
            metadata: 元数据

        Returns:
            创建的对话条目
        """
        entry = ContextEntry(
            role="assistant",
            content=content,
            operation_performed=operation_performed,
            correction_made=correction_made,
            mentioned_plates=[self.memory.current_plate] if self.memory.current_plate else [],
            metadata=metadata or {}
        )

        self.memory.add_entry(entry)
        self._save()

        logger.debug(f"Added assistant message: {content[:50]}...")
        return entry

    def _extract_plates(self, text: str) -> List[str]:
        """从文本中提取车牌号"""
        return list(set(PLATE_PATTERN.findall(text)))

    def get_current_plate(self) -> Optional[str]:
        """获取当前车牌"""
        return self.memory.current_plate

    def get_context_summary(self) -> str:
        """获取上下文摘要"""
        return self.memory.get_summary()

    def get_recent_dialogue(self, n: int = 10) -> List[Dict[str, Any]]:
        """
        获取最近 n 轮对话。

        Args:
            n: 轮次数量

        Returns:
            对话列表
        """
        entries = self.memory.get_recent_entries(n)
        return [
            {
                "role": entry.role,
                "content": entry.content,
                "timestamp": entry.timestamp.isoformat(),
            }
            for entry in entries
        ]

    def resolve_reference(self, text: str) -> str:
        """
        解析代词引用。

        将"这辆车"替换为当前车牌。

        Args:
            text: 原始文本

        Returns:
            解析后的文本
        """
        if "这辆车" in text and self.memory.current_plate:
            return text.replace("这辆车", self.memory.current_plate)
        return text

    def record_correction(self, correction: str) -> None:
        """
        记录纠正。

        Args:
            correction: 纠正内容
        """
        self.memory.corrections.append(correction)
        self._save()
        logger.info(f"Recorded correction: {correction}")

    def record_operation(self, operation: str) -> None:
        """
        记录执行的操作。

        Args:
            operation: 操作名称
        """
        self.memory.performed_operations.append(operation)
        self._save()

    def clear(self) -> None:
        """清空对话记忆"""
        self.memory.clear()
        self._save()
        logger.info("Cleared context memory")

    def get_stats(self) -> dict:
        """获取记忆统计信息"""
        return {
            "total_entries": len(self.memory.entries),
            "current_plate": self.memory.current_plate,
            "current_intent": self.memory.current_intent,
            "all_plates_count": len(self.memory.all_mentioned_plates),
            "operations_count": len(self.memory.performed_operations),
            "corrections_count": len(self.memory.corrections),
        }
```

- [ ] **Step 2: 创建测试文件**

```python
# tests/memory/test_context_memory.py
"""
Tests for context memory service.
"""

import pytest
from datetime import datetime

from src.memory.context_memory import ContextMemoryService


class TestContextMemoryService:
    """上下文记忆服务测试"""

    @pytest.fixture
    def temp_storage(self, tmp_path):
        """创建临时存储路径"""
        return str(tmp_path / "test_context.json")

    @pytest.fixture
    def context_service(self, temp_storage):
        """创建记忆服务实例"""
        return ContextMemoryService(storage_path=temp_storage)

    def test_add_user_message(self, context_service):
        """测试添加用户消息"""
        entry = context_service.add_user_message("查一下沪BAB1565的信息")

        assert entry.role == "user"
        assert "沪BAB1565" in entry.mentioned_plates
        assert context_service.get_current_plate() == "沪BAB1565"

    def test_add_assistant_message(self, context_service):
        """测试添加助手消息"""
        context_service.add_user_message("查沪A12345")
        entry = context_service.add_assistant_message(
            "已查询车牌信息",
            operation_performed="plate_query"
        )

        assert entry.role == "assistant"
        assert entry.operation_performed == "plate_query"

    def test_resolve_reference(self, context_service):
        """测试解析代词引用"""
        context_service.add_user_message("查沪BAB1565")

        result = context_service.resolve_reference("这辆车去过哪些园区")

        assert result == "沪BAB1565去过哪些园区"

    def test_extract_plates(self, context_service):
        """测试提取车牌"""
        context_service.add_user_message("沪A12345和沪B67890都在吗")

        assert context_service.get_current_plate() == "沪B67890"

    def test_record_correction(self, context_service):
        """测试记录纠正"""
        context_service.record_correction("停过不是绑定，是进出场记录")

        stats = context_service.get_stats()
        assert stats["corrections_count"] == 1

    def test_get_recent_dialogue(self, context_service):
        """测试获取最近对话"""
        for i in range(5):
            context_service.add_user_message(f"消息{i}")

        dialogue = context_service.get_recent_dialogue(3)

        assert len(dialogue) == 3

    def test_persistence(self, temp_storage):
        """测试持久化"""
        service1 = ContextMemoryService(storage_path=temp_storage)
        service1.add_user_message("查沪BAB1565")

        service2 = ContextMemoryService(storage_path=temp_storage)
        assert service2.get_current_plate() == "沪BAB1565"

    def test_clear_memory(self, context_service):
        """测试清空记忆"""
        context_service.add_user_message("查沪A12345")
        assert context_service.get_current_plate() is not None

        context_service.clear()

        assert context_service.get_current_plate() is None
```

- [ ] **Step 3: 运行测试**

```bash
cd E:/trae/mysql-260210
python -m pytest tests/memory/test_context_memory.py -v
```

- [ ] **Step 4: 提交**

```bash
git add src/memory/context_memory.py tests/memory/test_context_memory.py
git commit -m "feat(memory): add context memory service for 100-turn dialogue"
```

---

## Task 4: 修复 Rerank 预算

**Files:**
- Modify: `src/metadata/retrieval_pipeline.py`
- Modify: `src/config.py`

- [ ] **Step 1: 修改配置文件**

```python
# src/config.py 中添加配置项
# 在文件末尾添加：

# Rerank 配置
RERANK_BUDGET_MS = 1000  # Rerank 总预算（毫秒）
FIELD_RERANK_THRESHOLD_MS = 180  # 字段级 Rerank 阈值
```

- [ ] **Step 2: 修改 retrieval_pipeline.py**

找到 `FIELD_RERANK_THRESHOLD_MS = 180` 和 `budget_ms: int = 500`，修改为：

```python
# src/metadata/retrieval_pipeline.py
# 修改第30-31行：

FIELD_RERANK_THRESHOLD_MS = 180

# 修改第57-63行的 __init__ 方法：

def __init__(
    self,
    budget_ms: int = 1000,  # 从 500 改为 1000
    env: str = "dev",
    agent: Optional[RetrievalAgent] = None,
    rerank_service: Optional[RerankService] = None,
):
```

- [ ] **Step 3: 运行现有测试验证修改正确**

```bash
cd E:/trae/mysql-260210
python -m pytest tests/ -v -k "retrieval"
```

- [ ] **Step 4: 提交**

```bash
git add src/metadata/retrieval_pipeline.py src/config.py
git commit -m "fix(metadata): increase rerank budget from 500ms to 1000ms

Ensures both table-level and field-level reranking can complete"
```

---

## Task 5: 创建预置概念映射

**Files:**
- Create: `data/dev/knowledge_base/concepts.json`（初始数据）

- [ ] **Step 1: 创建初始概念映射数据**

```json
{
  "version": "1.0.0",
  "last_updated": "2026-03-10T12:00:00",
  "concepts": {
    "internal_vehicle": {
      "concept_id": "internal_vehicle",
      "user_terms": ["内部车辆", "固定车", "线上固定车", "固定车辆"],
      "database_mapping": {
        "table": "parkcloud.cloud_fixed_plate",
        "description": "线上固定车辆表"
      },
      "description": "内部车辆，数据库中叫线上固定车",
      "learned_from": "initial_template",
      "confidence": 0.8,
      "confirmed_count": 3
    },
    "parking_lot": {
      "concept_id": "parking_lot",
      "user_terms": ["园区", "场库", "停车场", "园区名称"],
      "database_mapping": {
        "table": "parkcloud.cloud_park",
        "description": "园区信息表，共33个园区"
      },
      "description": "园区/场库，共33个园区",
      "learned_from": "initial_template",
      "confidence": 0.8,
      "confirmed_count": 3
    },
    "entry_exit_record": {
      "concept_id": "entry_exit_record",
      "user_terms": ["停过", "去过", "进出场", "进出记录", "出入记录"],
      "database_mapping": {
        "tables_pattern": "p_*",
        "description": "p开头的库里的进出场记录表"
      },
      "description": "进出场记录，需要遍历p开头的库",
      "learned_from": "initial_template",
      "confidence": 0.7,
      "confirmed_count": 2
    },
    "plate_distribute": {
      "concept_id": "plate_distribute",
      "user_terms": ["下发", "下发到", "同步到", "推送到"],
      "database_mapping": {
        "operation": "update_state",
        "state_value": 0,
        "description": "设置车辆状态为已下发"
      },
      "description": "下发操作，设置state=0",
      "learned_from": "initial_template",
      "confidence": 0.8,
      "confirmed_count": 3
    },
    "plate_binding": {
      "concept_id": "plate_binding",
      "user_terms": ["绑定", "绑定关系", "绑定的园区"],
      "database_mapping": {
        "table": "parkcloud.cloud_fixed_plate_park",
        "description": "车牌与园区的绑定关系表"
      },
      "description": "车牌绑定的园区",
      "learned_from": "initial_template",
      "confidence": 0.8,
      "confirmed_count": 2
    },
    "plate_query": {
      "concept_id": "plate_query",
      "user_terms": ["查车牌", "查询车牌", "车牌信息", "查一下车牌"],
      "database_mapping": {
        "operation": "plate_query",
        "description": "查询车牌基本信息"
      },
      "description": "查询车牌信息",
      "learned_from": "initial_template",
      "confidence": 0.9,
      "confirmed_count": 5
    }
  }
}
```

- [ ] **Step 2: 提交初始数据**

```bash
git add data/dev/knowledge_base/concepts.json
git commit -m "feat(knowledge): add initial concept mappings from template

Converts business_knowledge.yaml to concept mapping format"
```

---

## 阶段一完成检查

- [ ] 所有测试通过
- [ ] 概念存储服务可用
- [ ] 上下文记忆服务可用
- [ ] Rerank 预算已调整为 1000ms
- [ ] 初始概念映射已创建

**完成后进入阶段二：核心对话层**