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
from src.sql_safety import (
    detect_intent,
    has_multiple_statements,
    has_where_clause,
    validate_sql
)

router = APIRouter()


def _check_mutation_sql_safety(sql: str) -> tuple:
    """
    检查 SQL 安全性
    返回: (is_safe, error_message)
    """
    is_valid, error_msg = validate_sql(sql)
    if not is_valid:
        return False, f"禁止执行不安全 SQL: {error_msg}"

    if has_multiple_statements(sql):
        return False, "不允许执行多语句"

    intent = detect_intent(sql)
    if intent in {"delete", "update"} and not has_where_clause(sql):
        return False, "DELETE/UPDATE 操作必须包含 WHERE 条件"

    if intent not in {"insert", "update", "delete"}:
        return False, "仅允许 INSERT/UPDATE/DELETE 变更语句"

    return True, ""


def _check_preview_sql_safety(sql: str) -> tuple:
    is_valid, error_msg = validate_sql(sql)
    if not is_valid:
        return False, f"禁止执行不安全 SQL: {error_msg}"
    if has_multiple_statements(sql):
        return False, "预览 SQL 不允许多语句"
    if detect_intent(sql) != "select":
        return False, "预览 SQL 必须是 SELECT 查询"
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
    is_safe, error_msg = _check_mutation_sql_safety(request.sql)
    if not is_safe:
        raise HTTPException(status_code=400, detail=error_msg)
    preview_safe, preview_error = _check_preview_sql_safety(request.preview_sql)
    if not preview_safe:
        raise HTTPException(status_code=400, detail=preview_error)
    
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
    is_safe, error_msg = _check_mutation_sql_safety(request.sql)
    if not is_safe:
        raise HTTPException(status_code=400, detail=error_msg)
    preview_safe, preview_error = _check_preview_sql_safety(request.preview_sql)
    if not preview_safe:
        raise HTTPException(status_code=400, detail=preview_error)
    
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
