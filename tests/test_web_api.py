import pytest
from fastapi.testclient import TestClient


def test_health_check():
    """测试健康检查端点"""
    import sys
    import os
    # 将项目根目录添加到模块路径
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from web_app import app
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_query_analyze_endpoint():
    """测试查询分析端点"""
    import sys
    import os
    # 将项目根目录添加到模块路径
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from web_app import app
    client = TestClient(app)
    response = client.post("/api/query/analyze", json={
        "natural_language": "查固定车"
    })
    assert response.status_code == 200
    data = response.json()
    assert "needs_interaction" in data


def test_schema_tables_endpoint():
    """测试表列表端点"""
    import sys
    import os
    # 将项目根目录添加到模块路径
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from web_app import app
    client = TestClient(app)
    response = client.get("/api/schema/tables")
    assert response.status_code == 200