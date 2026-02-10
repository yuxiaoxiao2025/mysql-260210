import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

def get_db_url():
    """
    获取数据库连接字符串
    格式: mysql+pymysql://user:password@host:port/database
    """
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    database = os.getenv("DB_NAME")
    
    if not all([host, port, user, password, database]):
        raise ValueError("Missing database configuration in environment variables.")
        
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"
