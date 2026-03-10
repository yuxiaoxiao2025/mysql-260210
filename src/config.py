import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

def get_db_url(db_name: Optional[str] = None, use_default_db: bool = True) -> str:
    """获取数据库连接 URL"""
    db_user = os.getenv('DB_USER', 'root')
    db_password = os.getenv('DB_PASSWORD', '')
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '3306')
    default_db_name = os.getenv('DB_NAME', 'test')
    resolved_db_name = default_db_name if db_name is None and use_default_db else db_name

    if resolved_db_name:
        return (
            f"mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/"
            f"{resolved_db_name}"
        )
    return f"mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/"

# Rerank 配置
RERANK_BUDGET_MS = 1000  # Rerank 总预算（毫秒）
FIELD_RERANK_THRESHOLD_MS = 180  # 字段级 Rerank 阈值
