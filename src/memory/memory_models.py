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
        """
        根据用户说法查找概念。

        如果多个概念包含相同的用户说法，返回置信度最高的概念。

        Args:
            term: 用户说法

        Returns:
            匹配的概念映射，未找到则返回 None
        """
        term_lower = term.lower()
        matches: List[ConceptMapping] = []

        for concept in self.concepts.values():
            if term_lower in [t.lower() for t in concept.user_terms]:
                matches.append(concept)

        if not matches:
            return None

        # 返回置信度最高的概念
        return max(matches, key=lambda c: c.confidence)

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