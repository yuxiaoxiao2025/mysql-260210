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
