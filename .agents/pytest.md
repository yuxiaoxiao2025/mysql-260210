# Pytest 测试最佳实践

## 概述
使用 pytest 编写清晰、可维护的单元测试和集成测试。

## 测试结构

### 目录结构
```
mysql260227/
├── src/
│   └── module.py
└── tests/
    ├── conftest.py       # 共享 fixtures
    ├── test_module.py    # 模块测试
    └── test_integration.py
```

### 测试命名规范
- 测试文件：`test_*.py` 或 `*_test.py`
- 测试函数：`test_*`
- 测试类：`Test*`

## Fixtures

### 基础 Fixture
```python
import pytest

@pytest.fixture
def sample_data():
    """返回测试用的样本数据"""
    return [1, 2, 3, 4, 5]

def test_processing(sample_data):
    assert len(sample_data) == 5
```

### 数据库 Fixture
```python
@pytest.fixture(scope="module")
def db_connection():
    """创建数据库连接，模块级别共享"""
    conn = create_test_connection()
    yield conn
    conn.close()

@pytest.fixture
def db_session(db_connection):
    """创建测试会话，每次测试独立"""
    session = db_connection.create_session()
    yield session
    session.rollback()
```

### Mock Fixture
```python
@pytest.fixture
def mock_llm_client():
    """Mock AI 客户端"""
    client = LLMClient()
    client.api_key = "test_key"
    return client
```

## 测试模式

### AAA 模式（Arrange-Act-Assert）
```python
def test_data_export():
    # Arrange - 准备测试数据
    data = pd.DataFrame({"name": ["Alice", "Bob"]})
    exporter = ExcelExporter()

    # Act - 执行被测功能
    result = exporter.export(data, "test_output")

    # Assert - 验证结果
    assert result is not None
    assert "test_output" in result
```

### 参数化测试
```python
@pytest.mark.parametrize("input,expected", [
    (1, 2),
    (2, 4),
    (3, 6),
    (0, 0),
])
def test_multiplication(input, expected):
    assert multiply_by_two(input) == expected
```

### 异常测试
```python
def test_invalid_connection():
    with pytest.raises(ConnectionError):
        DatabaseManager.connect("invalid_host", 9999)
```

## Mocking

### 使用 monkeypatch
```python
def test_with_mock(monkeypatch):
    def mock_function():
        return "mocked_result"

    monkeypatch.setattr("module.real_function", mock_function)
    result = module.real_function()
    assert result == "mocked_result"
```

### 使用 unittest.mock
```python
from unittest.mock import MagicMock, patch

def test_with_magic_mock():
    mock_db = MagicMock()
    mock_db.execute_query.return_value = pd.DataFrame({"id": [1, 2]})

    result = mock_db.execute_query("SELECT * FROM table")
    assert len(result) == 2
    mock_db.execute_query.assert_called_once()
```

### Mock 外部 API
```python
def test_llm_generation(mocker):
    mock_response = {
        "sql": "SELECT * FROM users",
        "reasoning": "查询所有用户"
    }
    mocker.patch("src.llm_client.LLMClient._call_api", return_value=mock_response)

    client = LLMClient()
    result = client.generate_sql("查询用户", {})
    assert result["sql"] == "SELECT * FROM users"
```

## 测试标记

### 自定义标记
```python
# conftest.py
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )

# 测试文件
@pytest.mark.slow
def test_integration():
    time.sleep(10)
    assert True
```

### 运行特定标记
```bash
pytest -m slow              # 只运行 slow 测试
pytest -m "not slow"        # 排除 slow 测试
```

## 测试覆盖率

### 安装和运行
```bash
pip install pytest-cov
pytest --cov=src --cov-report=html
```

### 覆盖率目标
- 核心业务逻辑：90%+
- 工具函数：80%+
- 整体项目：70%+

## 常用命令

### 基本运行
```bash
pytest                          # 运行所有测试
pytest -v                       # 详细输出
pytest -x                       # 首次失败时停止
pytest -k "test_name"           # 运行匹配的测试
```

### 调试
```bash
pytest -s                       # 显示 print 输出
pytest --pdb                    # 失败时进入 pdb
pytest --trace                  # 进入每个测试
```

### 并行运行
```bash
pip install pytest-xdist
pytest -n 4                     # 使用 4 个进程并行运行
```

## 最佳实践

### 测试隔离
```python
# 每个测试应该是独立的
@pytest.fixture(autouse=True)
def reset_state():
    # 在每个测试前重置状态
    yield
    # 在每个测试后清理
```

### 测试可读性
```python
# 使用描述性的测试名称
def test_export_to_excel_creates_file_with_correct_name():
    pass

# 比 test_export_1() 更好
```

### 避免硬编码
```python
# 使用 fixtures 而不是硬编码
@pytest.fixture
def valid_db_config():
    return {
        "host": "localhost",
        "port": 3306,
        "user": "test_user"
    }

# 不要在测试中硬编码
def test_connection():
    config = {"host": "localhost", "port": 3306}  # 避免
```

## 常见陷阱

### 1. 测试依赖顺序
```python
# 错误：测试之间有依赖
def test_a():
    global.state = "modified"

def test_b():
    assert global.state == "modified"  # 依赖 test_a

# 正确：每个测试独立
@pytest.fixture
def clean_state():
    yield "initial"
```

### 2. Mock 过度
```python
# 错误：Mock 了被测代码
def test_calculation(monkeypatch):
    monkeypatch.setattr("module.calculate", lambda x: x * 2)
    assert module.calculate(5) == 10  # 没有测试真正的逻辑

# 正确：Mock 外部依赖
def test_with_external_api(monkeypatch):
    monkeypatch.setattr("requests.get", mock_get)
    assert module.process_data()
```

### 3. 测试覆盖率陷阱
```python
# 不要为了覆盖率写无意义的测试
def test_property():
    obj = MyClass()
    assert obj.property is not None  # 无意义
```

## conftest.py 示例
```python
import pytest
import pandas as pd
from unittest.mock import MagicMock

@pytest.fixture(scope="session")
def sample_dataframe():
    """整个测试会话共享的样本数据"""
    return pd.DataFrame({
        "id": [1, 2, 3],
        "name": ["Alice", "Bob", "Charlie"]
    })

@pytest.fixture
def mock_database():
    """Mock 数据库连接"""
    db = MagicMock()
    db.execute_query.return_value = pd.DataFrame({"result": [1]})
    return db

@pytest.fixture
def temp_file(tmp_path):
    """临时文件 fixture"""
    file = tmp_path / "test.txt"
    file.write_text("test content")
    return file
```
