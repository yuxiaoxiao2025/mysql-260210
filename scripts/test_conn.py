import sys
import os

# 添加项目根目录到 python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from src.config import get_db_url

def test_connection():
    print("Testing database connection...")
    try:
        db_url = get_db_url()
        # 隐藏密码打印 URL
        safe_url = db_url.split('@')[-1]
        print(f"Connecting to: ...@{safe_url}")
        
        engine = create_engine(db_url)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT VERSION()"))
            version = result.fetchone()[0]
            print(f"✅ Connection successful! MySQL Version: {version}")
            
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_connection()
