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