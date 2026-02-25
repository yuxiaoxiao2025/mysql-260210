from pydantic import BaseModel
from typing import List, Optional, Dict, Any


# ==================== 查询相关 ====================

class QueryAnalyzeRequest(BaseModel):
    """分析查询请求"""
    query: str


class TableSuggestion(BaseModel):
    """表推荐项"""
    table: str
    recommended: bool = False
    description: str = ""
    score: float = 0.0


class QueryAnalyzeResponse(BaseModel):
    """分析查询响应"""
    needs_interaction: bool
    selected_tables: List[str] = []
    reason: str = ""
    suggestions: List[TableSuggestion] = []


class QueryConfirmRequest(BaseModel):
    """确认查询请求"""
    query: str
    selected_tables: List[str]


class QueryConfirmResponse(BaseModel):
    """确认查询响应 - 包含生成的 SQL"""
    sql: str
    filename: str = "result"
    sheet_name: str = "Sheet1"
    reasoning: str = ""
    intent: str = "query"  # query | mutation
    preview_sql: Optional[str] = None
    key_columns: List[str] = []
    warnings: List[str] = []


class QueryExecuteRequest(BaseModel):
    """执行查询请求"""
    sql: str


class QueryExecuteResponse(BaseModel):
    """执行查询响应"""
    data: List[Dict[str, Any]] = []
    row_count: int = 0
    columns: List[str] = []


# 保留旧模型以兼容
class QueryRequest(BaseModel):
    natural_language: str
    selected_tables: Optional[List[str]] = None


class QueryResponse(BaseModel):
    sql: str
    filename: str
    sheet_name: str
    reasoning: str
    needs_interaction: bool
    selected_tables: List[str]
    suggestions: List[Dict[str, Any]]


# ==================== Schema 相关 ====================

class TableInfoResponse(BaseModel):
    """表详情响应"""
    name: str
    database: str = ""
    description: str = ""
    columns: List[Dict[str, Any]] = []
    foreign_keys: List[Dict[str, str]] = []


class TableSearchResponse(BaseModel):
    """表搜索响应"""
    tables: List[TableSuggestion]


# ==================== 变更相关 ====================

class MutationPreviewRequest(BaseModel):
    """变更预览请求"""
    sql: str
    preview_sql: str
    key_columns: List[str]
    operation_type: str  # insert | update | delete


class MutationPreviewResponse(BaseModel):
    """变更预览响应"""
    operation_type: str
    summary: Dict[str, int]  # {inserted, updated, deleted}
    before_data: Optional[List[Dict]] = None
    after_data: Optional[List[Dict]] = None
    warnings: List[str] = []
    estimated_time: float = 0.0


class MutationExecuteRequest(BaseModel):
    """变更执行请求"""
    sql: str
    preview_sql: str
    key_columns: List[str]


class MutationExecuteResponse(BaseModel):
    """变更执行响应"""
    success: bool
    summary: Dict[str, int]
    message: str = ""


# ==================== 通用 ====================

class RefreshCacheRequest(BaseModel):
    """刷新缓存请求"""
    table_name: Optional[str] = None


class ErrorResponse(BaseModel):
    """错误响应"""
    error: str
    detail: str = ""
