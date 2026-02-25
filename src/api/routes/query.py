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
