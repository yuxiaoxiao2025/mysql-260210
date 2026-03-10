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

    def test_confirm_concept(self, store_service):
        """测试确认概念增加置信度"""
        store_service.add_concept(ConceptMapping(
            concept_id="test",
            user_terms=["测试说法"],
            confidence=0.5
        ))

        store_service.confirm_concept("test")

        concept = store_service.get_concept("test")
        assert concept.confirmed_count == 1
        assert concept.confidence == 0.6

        # 再次确认
        store_service.confirm_concept("test")
        concept = store_service.get_concept("test")
        assert concept.confirmed_count == 2
        assert concept.confidence == 0.7

    def test_update_concept_whitelist(self, store_service):
        """测试更新字段白名单"""
        store_service.add_concept(ConceptMapping(
            concept_id="test",
            user_terms=["原说法"],
            description="原描述",
            confidence=0.5
        ))

        # 更新允许的字段
        store_service.update_concept("test", {
            "user_terms": ["新说法"],
            "description": "新描述"
        })

        concept = store_service.get_concept("test")
        assert concept.user_terms == ["新说法"]
        assert concept.description == "新描述"

        # 尝试更新不在白名单的字段（应该被忽略）
        store_service.update_concept("test", {"confidence": 0.99})
        concept = store_service.get_concept("test")
        assert concept.confidence == 0.5  # 未改变

    def test_get_stats(self, store_service):
        """测试获取统计信息"""
        # 空知识库
        stats = store_service.get_stats()
        assert stats["total_concepts"] == 0

        # 添加概念
        store_service.add_concept(ConceptMapping(
            concept_id="high_conf",
            user_terms=["高置信度"],
            confidence=0.9
        ))
        store_service.add_concept(ConceptMapping(
            concept_id="low_conf",
            user_terms=["低置信度"],
            confidence=0.3
        ))

        stats = store_service.get_stats()
        assert stats["total_concepts"] == 2
        assert stats["high_confidence"] == 1  # 只有 confidence >= 0.8 的

    def test_find_by_user_term_returns_highest_confidence(self, store_service):
        """测试根据用户说法查找返回最高置信度概念"""
        # 添加两个包含相同用户说法的概念
        store_service.add_concept(ConceptMapping(
            concept_id="concept_a",
            user_terms=["园区"],
            confidence=0.6
        ))
        store_service.add_concept(ConceptMapping(
            concept_id="concept_b",
            user_terms=["园区"],
            confidence=0.9
        ))

        result = store_service.find_by_user_term("园区")
        assert result is not None
        assert result.concept_id == "concept_b"  # 返回置信度更高的