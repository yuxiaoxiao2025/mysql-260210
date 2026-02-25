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
