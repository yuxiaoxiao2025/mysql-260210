# 后端集成实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将现有的业务组件（LLMClient、DatabaseManager、SchemaCache、SmartQueryEngine）连接到 FastAPI 路由，实现完整的 Web 应用功能。

**Architecture:** 采用 FastAPI 依赖注入模式管理组件生命周期，通过 `deps.py` 统一提供单例实例。前端静态文件由 FastAPI 直接服务。

**Tech Stack:** Python 3.10+, FastAPI, SQLAlchemy, DashScope (通义千问), React, Vite

---

## Task 1: 创建依赖注入模块

**Files:**
- Create: `src/api/deps.py`

**Step 1: 创建依赖注入模块**

创建文件 `src/api/deps.py`:

```python
"""
依赖注入模块 - 统一管理所有组件的实例化
"""
from functools import lru_cache
from src.db_manager import DatabaseManager
from src.llm_client import LLMClient
from src.cache.schema_cache import SchemaCache
from src.matcher.table_matcher import TableMatcher
from src.learner.preference_learner import PreferenceLearner
from src.matcher.smart_query_engine import SmartQueryEngine


@lru_cache()
def get_db() -> DatabaseManager:
    """获取数据库管理器单例"""
    return DatabaseManager()


@lru_cache()
def get_llm() -> LLMClient:
    """获取 LLM 客户端单例"""
    return LLMClient()


@lru_cache()
def get_cache() -> SchemaCache:
    """获取 Schema 缓存单例"""
    return SchemaCache(db_manager=get_db())


@lru_cache()
def get_matcher() -> TableMatcher:
    """获取表匹配器单例"""
    return TableMatcher(schema_cache=get_cache())


@lru_cache()
def get_learner() -> PreferenceLearner:
    """获取偏好学习器单例"""
    return PreferenceLearner()


@lru_cache()
def get_query_engine() -> SmartQueryEngine:
    """获取智能查询引擎单例"""
    return SmartQueryEngine(
        schema_cache=get_cache(),
        preference_learner=get_learner(),
        table_matcher=get_matcher()
    )
```

**Step 2: 验证导入正常**

```bash
cd E:\trae-pc\mysql-260210
python -c "from src.api.deps import get_query_engine; print('OK')"
```

Expected: 输出 `OK`

---

## Task 2: 更新 API 数据模型

**Files:**
- Modify: `src/api/models.py`

**Step 1: 扩展数据模型**

替换 `src/api/models.py` 内容：

```python
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
```

**Step 2: 验证模型定义**

```bash
python -c "from src.api.models import QueryAnalyzeRequest; print('OK')"
```

Expected: 输出 `OK`

---

## Task 3: 实现智能查询 API

**Files:**
- Modify: `src/api/routes/query.py`

**Step 1: 实现分析接口**

替换 `src/api/routes/query.py` 内容：

```python
"""
智能查询 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException
from src.api.deps import get_query_engine, get_llm, get_cache, get_db, get_learner
from src.api.models import (
    QueryAnalyzeRequest,
    QueryAnalyzeResponse,
    QueryConfirmRequest,
    QueryConfirmResponse,
    QueryExecuteRequest,
    QueryExecuteResponse,
    TableSuggestion,
    QueryRequest,
    QueryResponse,
)

router = APIRouter()


@router.post("/analyze", response_model=QueryAnalyzeResponse)
async def analyze_query(
    request: QueryAnalyzeRequest,
    engine=Depends(get_query_engine)
):
    """
    分析自然语言查询，返回表推荐
    
    流程：
    1. SmartQueryEngine 分析查询
    2. 查找记忆偏好
    3. 返回是否需要交互确认
    """
    try:
        result = engine.process_query(request.query)
        
        # 转换 suggestions 格式
        suggestions = [
            TableSuggestion(
                table=s.get("table", ""),
                recommended=s.get("recommended", False),
                description=s.get("description", ""),
                score=s.get("score", 0.0)
            )
            for s in result.get("suggestions", [])
        ]
        
        return QueryAnalyzeResponse(
            needs_interaction=result.get("needs_interaction", True),
            selected_tables=result.get("selected_tables", []),
            reason=result.get("reason", ""),
            suggestions=suggestions
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


@router.post("/confirm", response_model=QueryConfirmResponse)
async def confirm_query(
    request: QueryConfirmRequest,
    engine=Depends(get_query_engine),
    llm=Depends(get_llm),
    cache=Depends(get_cache),
    learner=Depends(get_learner)
):
    """
    确认表选择并生成 SQL
    
    流程：
    1. 记录用户选择的偏好
    2. 获取选中表的 Schema 上下文
    3. 调用 LLM 生成 SQL
    """
    try:
        # 1. 记录用户选择
        entities = engine._extract_entities(request.query)
        learner.learn(entities, request.selected_tables, request.query)
        
        # 2. 构建 Schema 上下文
        schema_context = _build_schema_context(cache, request.selected_tables)
        
        # 3. 调用 LLM 生成 SQL
        llm_result = llm.generate_sql(request.query, schema_context)
        
        return QueryConfirmResponse(
            sql=llm_result.get("sql", ""),
            filename=llm_result.get("filename", "result"),
            sheet_name=llm_result.get("sheet_name", "Sheet1"),
            reasoning=llm_result.get("reasoning", ""),
            intent=llm_result.get("intent", "query"),
            preview_sql=llm_result.get("preview_sql"),
            key_columns=llm_result.get("key_columns", []),
            warnings=llm_result.get("warnings", [])
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SQL 生成失败: {str(e)}")


@router.post("/execute", response_model=QueryExecuteResponse)
async def execute_query(
    request: QueryExecuteRequest,
    db=Depends(get_db)
):
    """
    执行 SELECT 查询
    
    注意：只允许 SELECT 语句
    """
    sql_upper = request.sql.strip().upper()
    if not sql_upper.startswith("SELECT"):
        raise HTTPException(status_code=400, detail="只能执行 SELECT 查询")
    
    try:
        df = db.execute_query(request.sql)
        
        return QueryExecuteResponse(
            data=df.to_dict(orient="records"),
            row_count=len(df),
            columns=list(df.columns)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询执行失败: {str(e)}")


# 兼容旧接口
@router.post("/analyze_legacy", response_model=QueryResponse)
async def analyze_query_legacy(
    request: QueryRequest,
    engine=Depends(get_query_engine)
):
    """兼容旧版 API"""
    result = engine.process_query(request.natural_language)
    
    return QueryResponse(
        sql="",
        filename="result",
        sheet_name="Sheet1",
        reasoning=result.get("reason", ""),
        needs_interaction=result.get("needs_interaction", True),
        selected_tables=result.get("selected_tables", []),
        suggestions=result.get("suggestions", [])
    )


def _build_schema_context(cache, table_names: list) -> str:
    """
    构建用于 LLM 的 Schema 上下文
    """
    context_parts = []
    
    for table_name in table_names:
        table_info = cache.get_table_info(table_name)
        if table_info:
            columns_desc = []
            for col in table_info.get("columns", []):
                col_name = col.get("name", "")
                col_type = col.get("type", "")
                col_comment = col.get("comment", "")
                columns_desc.append(f"  - {col_name} ({col_type}): {col_comment}")
            
            context_parts.append(f"""
表: {table_name}
描述: {table_info.get('description', 'N/A')}
字段:
{chr(10).join(columns_desc)}
""")
    
    return "\n".join(context_parts)
```

**Step 2: 验证路由定义**

```bash
python -c "from src.api.routes.query import router; print(f'Routes: {[r.path for r in router.routes]}')"
```

Expected: 输出路由列表

---

## Task 4: 实现 Schema 管理 API

**Files:**
- Modify: `src/api/routes/schema.py`

**Step 1: 实现 Schema 接口**

替换 `src/api/routes/schema.py` 内容：

```python
"""
Schema 管理 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException
from src.api.deps import get_cache, get_db, get_matcher
from src.api.models import (
    TableInfoResponse,
    TableSearchResponse,
    TableSuggestion,
    RefreshCacheRequest
)

router = APIRouter()


@router.get("/tables")
async def get_all_tables(cache=Depends(get_cache)):
    """获取所有表列表"""
    try:
        tables = cache.get_all_tables()
        return {"tables": tables}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取表列表失败: {str(e)}")


@router.get("/table/{table_name}", response_model=TableInfoResponse)
async def get_table_info(table_name: str, cache=Depends(get_cache)):
    """获取单个表的详细信息"""
    try:
        table_info = cache.get_table_info(table_name)
        
        if not table_info:
            raise HTTPException(status_code=404, detail=f"表 {table_name} 不存在")
        
        return TableInfoResponse(
            name=table_name,
            database=table_info.get("database", ""),
            description=table_info.get("description", ""),
            columns=table_info.get("columns", []),
            foreign_keys=table_info.get("foreign_keys", [])
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取表信息失败: {str(e)}")


@router.get("/search", response_model=TableSearchResponse)
async def search_tables(keyword: str, limit: int = 10, matcher=Depends(get_matcher)):
    """根据关键词搜索表"""
    try:
        result = matcher.match_tables(keyword, top_k=limit)
        
        suggestions = []
        matched = result.get("groups", {}).get("matched_tables", [])
        
        for item in matched:
            suggestions.append(TableSuggestion(
                table=item.get("table_name", ""),
                recommended=item.get("recommended", False),
                description=item.get("description", ""),
                score=item.get("score", 0.0)
            ))
        
        return TableSearchResponse(tables=suggestions)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


@router.post("/refresh")
async def refresh_cache(request: RefreshCacheRequest = None, cache=Depends(get_cache)):
    """刷新 Schema 缓存"""
    try:
        if request and request.table_name:
            # 刷新单个表
            cache.invalidate(request.table_name)
            message = f"已刷新表 {request.table_name}"
        else:
            # 刷新全部
            cache.invalidate()
            message = "已刷新全部缓存"
        
        return {"success": True, "message": message}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"刷新缓存失败: {str(e)}")


@router.get("/related/{table_name}")
async def get_related_tables(table_name: str, cache=Depends(get_cache)):
    """获取与指定表关联的其他表"""
    try:
        related = cache.get_related_tables(table_name)
        return {"table": table_name, "related_tables": related}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取关联表失败: {str(e)}")
```

**Step 2: 验证路由定义**

```bash
python -c "from src.api.routes.schema import router; print(f'Routes: {[r.path for r in router.routes]}')"
```

Expected: 输出路由列表

---

## Task 5: 实现变更预览 API

**Files:**
- Modify: `src/api/routes/mutation.py`

**Step 1: 实现变更接口**

替换 `src/api/routes/mutation.py` 内容：

```python
"""
变更预览与执行 API 路由
"""
import time
from fastapi import APIRouter, Depends, HTTPException
from src.api.deps import get_db
from src.api.models import (
    MutationPreviewRequest,
    MutationPreviewResponse,
    MutationExecuteRequest,
    MutationExecuteResponse
)
from src.preview.diff_renderer import DiffRenderer

router = APIRouter()


# 危险 SQL 关键词
DANGEROUS_KEYWORDS = ["DROP", "TRUNCATE", "ALTER TABLE", "GRANT", "REVOKE"]


def _check_sql_safety(sql: str) -> tuple[bool, str]:
    """
    检查 SQL 安全性
    返回: (is_safe, error_message)
    """
    sql_upper = sql.upper()
    
    # 检查危险关键词
    for keyword in DANGEROUS_KEYWORDS:
        if keyword in sql_upper:
            return False, f"禁止执行包含 {keyword} 的操作"
    
    # 检查 DELETE/UPDATE 是否有 WHERE 条件
    if sql_upper.strip().startswith("DELETE") or sql_upper.strip().startswith("UPDATE"):
        if "WHERE" not in sql_upper:
            return False, "DELETE/UPDATE 操作必须包含 WHERE 条件"
    
    return True, ""


@router.post("/preview", response_model=MutationPreviewResponse)
async def preview_mutation(request: MutationPreviewRequest, db=Depends(get_db)):
    """
    预览变更操作（不提交事务）
    
    流程：
    1. 安全检查
    2. 执行事务预览（自动回滚）
    3. 渲染 Before/After 对比
    """
    # 1. 安全检查
    is_safe, error_msg = _check_sql_safety(request.sql)
    if not is_safe:
        raise HTTPException(status_code=400, detail=error_msg)
    
    start_time = time.time()
    
    try:
        # 2. 执行预览（commit=False 自动回滚）
        result = db.execute_in_transaction(
            mutation_sql=request.sql,
            preview_sql=request.preview_sql,
            key_columns=request.key_columns,
            commit=False  # 预览不提交
        )
        
        # 3. 渲染对比
        renderer = DiffRenderer()
        diff_result = renderer.render_diff(
            before_df=result["before"],
            after_df=result["after"],
            operation_type=request.operation_type,
            key_columns=request.key_columns
        )
        
        elapsed_time = time.time() - start_time
        
        # 添加行数警告
        warnings = diff_result.get("warnings", [])
        total_affected = sum(result["diff_summary"].values())
        if total_affected > 100:
            warnings.append(f"⚠️ 此操作将影响 {total_affected} 行数据")
        
        return MutationPreviewResponse(
            operation_type=request.operation_type,
            summary=result["diff_summary"],
            before_data=result["before"].to_dict(orient="records") if not result["before"].empty else None,
            after_data=result["after"].to_dict(orient="records") if not result["after"].empty else None,
            warnings=warnings,
            estimated_time=elapsed_time
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"预览失败: {str(e)}")


@router.post("/execute", response_model=MutationExecuteResponse)
async def execute_mutation(request: MutationExecuteRequest, db=Depends(get_db)):
    """
    执行变更操作（提交事务）
    
    注意：此操作会真正修改数据！
    """
    # 安全检查
    is_safe, error_msg = _check_sql_safety(request.sql)
    if not is_safe:
        raise HTTPException(status_code=400, detail=error_msg)
    
    try:
        result = db.execute_in_transaction(
            mutation_sql=request.sql,
            preview_sql=request.preview_sql,
            key_columns=request.key_columns,
            commit=True  # 确认后提交
        )
        
        return MutationExecuteResponse(
            success=True,
            summary=result["diff_summary"],
            message=f"变更已提交: {result['diff_summary']}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"执行失败: {str(e)}")
```

**Step 2: 验证路由定义**

```bash
python -c "from src.api.routes.mutation import router; print(f'Routes: {[r.path for r in router.routes]}')"
```

Expected: 输出路由列表

---

## Task 6: 配置静态文件服务

**Files:**
- Modify: `web_app.py`

**Step 1: 添加静态文件服务**

替换 `web_app.py` 内容：

```python
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from src.api.routes import query, schema, mutation

app = FastAPI(
    title="MySQL 数据导出工具",
    version="2.0",
    description="AI 驱动的 MySQL 数据查询与导出工具"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 路由
app.include_router(query.router, prefix="/api/query", tags=["智能查询"])
app.include_router(schema.router, prefix="/api/schema", tags=["Schema管理"])
app.include_router(mutation.router, prefix="/api/mutation", tags=["变更操作"])


# 健康检查
@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# API 文档
@app.get("/api")
async def api_info():
    return {
        "name": "MySQL 数据导出工具 API",
        "version": "2.0",
        "docs": "/docs",
        "endpoints": {
            "query": "/api/query",
            "schema": "/api/schema",
            "mutation": "/api/mutation"
        }
    }


# 静态文件服务（生产环境）
FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "frontend", "dist")

if os.path.exists(FRONTEND_DIST):
    # 挂载静态资源
    assets_path = os.path.join(FRONTEND_DIST, "assets")
    if os.path.exists(assets_path):
        app.mount("/assets", StaticFiles(directory=assets_path), name="assets")
    
    # SPA 回退路由 - 所有非 API 路由返回 index.html
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """
        服务前端 SPA
        所有非 API 路由都返回 index.html，让前端路由处理
        """
        # API 路由不走这里
        if full_path.startswith("api/") or full_path == "health":
            return None
        
        index_path = os.path.join(FRONTEND_DIST, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return {"error": "Frontend not built. Run 'npm run build' in frontend/"}
```

**Step 2: 验证 FastAPI 启动**

```bash
python -c "from web_app import app; print(f'App title: {app.title}')"
```

Expected: 输出 `App title: MySQL 数据导出工具`

---

## Task 7: 构建前端

**Files:**
- Build: `frontend/dist/`

**Step 1: 安装依赖并构建**

```bash
cd E:\trae-pc\mysql-260210\frontend
npm install
npm run build
```

Expected: 生成 `frontend/dist/` 目录

**Step 2: 验证构建产物**

```bash
dir E:\trae-pc\mysql-260210\frontend\dist
```

Expected: 存在 `index.html` 和 `assets/` 目录

---

## Task 8: 集成测试

**Step 1: 启动服务**

```bash
cd E:\trae-pc\mysql-260210
uvicorn web_app:app --host 0.0.0.0 --port 8000 --reload
```

**Step 2: 测试 API 端点**

```bash
# 健康检查
curl http://127.0.0.1:8000/health

# 获取表列表
curl http://127.0.0.1:8000/api/schema/tables

# 分析查询
curl -X POST http://127.0.0.1:8000/api/query/analyze \
  -H "Content-Type: application/json" \
  -d '{"query": "查所有固定车"}'
```

**Step 3: 访问前端**

打开浏览器访问: http://127.0.0.1:8000

Expected: 显示前端页面，可以进行查询操作

---

## Task 9: 提交代码

**Step 1: 查看变更**

```bash
cd E:\trae-pc\mysql-260210
git status
git diff
```

**Step 2: 提交**

```bash
git add src/api/deps.py src/api/models.py src/api/routes/ web_app.py docs/plans/2026-02-25-*
git commit -m "feat: 完成后端集成 - 连接真实 LLM API 和数据库

- 添加依赖注入模块 (deps.py)
- 实现智能查询 API (analyze/confirm/execute)
- 实现 Schema 管理 API (tables/table/search/refresh)
- 实现变更预览 API (preview/execute)
- 配置静态文件服务
- 添加 SQL 安全检查
- 构建前端静态文件"
```

---

## 检查清单

| 检查项 | 命令 | 预期结果 |
|--------|------|---------|
| 依赖注入正常 | `python -c "from src.api.deps import get_query_engine; print('OK')"` | OK |
| API 模型正常 | `python -c "from src.api.models import *; print('OK')"` | OK |
| FastAPI 启动正常 | `uvicorn web_app:app --port 8000` | 服务启动 |
| 健康检查 | `curl http://127.0.0.1:8000/health` | `{"status":"healthy"}` |
| 前端可访问 | 浏览器访问 http://127.0.0.1:8000 | 显示页面 |
| 查询 API | POST /api/query/analyze | 返回分析结果 |

---

## 预期成果

完成后：
1. ✅ 单一入口访问: http://127.0.0.1:8000
2. ✅ 自然语言查询 → 智能匹配表 → LLM 生成 SQL → 返回结果
3. ✅ 变更操作必须预览确认
4. ✅ 系统记忆用户偏好
