"""
Retrieval models for metadata knowledge graph system.

Provides Pydantic models for table and field-level retrieval operations.
"""

from enum import Enum
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field


class RetrievalLevel(str, Enum):
    """检索级别枚举"""
    TABLE = "table"
    FIELD = "field"


class RetrievalRequest(BaseModel):
    """检索请求模型"""
    query: str
    level: RetrievalLevel = RetrievalLevel.TABLE
    top_k: int = Field(default=5, ge=1, le=20)
    filter_tables: Optional[List[str]] = None  # Field-level filter


class TableMatch(BaseModel):
    """表级匹配结果"""
    table_name: str
    similarity_score: float  # 归一化相似度：1/(1+distance)
    description: str
    business_tags: List[str] = Field(default_factory=list)
    database_name: str = ""


class FieldMatch(BaseModel):
    """字段级匹配结果"""
    table_name: str
    field_name: str
    data_type: str
    description: str
    similarity_score: float
    is_primary_key: bool = False
    is_foreign_key: bool = False


class TableRetrievalResult(BaseModel):
    """表级检索结果"""
    query: str
    matches: List[TableMatch]
    execution_time_ms: int
    metadata: Dict = Field(default_factory=dict)
    # metadata may contain: expanded_tables, total_candidates, etc.


class FieldRetrievalResult(BaseModel):
    """字段级检索结果"""
    query: str
    matches: List[FieldMatch]
    execution_time_ms: int
    metadata: Dict = Field(default_factory=dict)


# Type alias for retrieval results
RetrievalResult = Union[TableRetrievalResult, FieldRetrievalResult]