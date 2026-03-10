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