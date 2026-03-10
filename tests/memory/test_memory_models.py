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