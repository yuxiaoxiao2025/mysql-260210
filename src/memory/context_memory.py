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
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)

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