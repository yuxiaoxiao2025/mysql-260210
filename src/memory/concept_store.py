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
                # Convert datetime strings back to datetime objects
                if "created_at" in concept_data and isinstance(concept_data["created_at"], str):
                    concept_data["created_at"] = datetime.fromisoformat(concept_data["created_at"])
                if "updated_at" in concept_data and isinstance(concept_data["updated_at"], str):
                    concept_data["updated_at"] = datetime.fromisoformat(concept_data["updated_at"])

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
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)

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