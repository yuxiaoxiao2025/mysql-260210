# Pytest 测试最佳实践

## 概述
使用 pytest 编写清晰、可维护的单元测试和集成测试，目标覆盖率 80%+。

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
- 测试函数：`test_*`（清晰描述测试意图）
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

### Fixture Scopes
```python
# Function scope (默认) - 每个测试运行
@pytest.fixture(scope="function")
def user():
    return {"id": 1, "name": "Alice"}

# Class scope - 每个测试类运行一次
@pytest.fixture(scope="class")
def database():
    db = setup_database()
    yield db
    db.close()

# Module scope - 每个测试模块运行一次
@pytest.fixture(scope="module")
def api_client():
    client = APIClient()
    yield client
    client.shutdown()

# Session scope - 整个测试会话运行一次
@pytest.fixture(scope="session")
def app_config():
    return load_config()
```

### 数据库 Fixture
```python
@pytest.fixture(scope="function")
def db_connection():
    """创建数据库连接，每次测试独立"""
    conn = create_test_connection()
    yield conn
    conn.rollback()
    conn.close()
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

### Fixture 依赖
```python
@pytest.fixture
def database_connection():
    """数据库连接"""
    conn = connect_to_db()
    yield conn
    conn.close()

@pytest.fixture
def database_session(database_connection):
    """数据库会话依赖连接"""
    session = create_session(database_connection)
    yield session
    session.rollback()
    session.close()

@pytest.fixture
def user_repository(database_session):
    """用户仓库依赖会话"""
    return UserRepository(database_session)
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

# 多个参数
@pytest.mark.parametrize("operation,a,b,expected", [
    ("add", 2, 3, 5),
    ("subtract", 10, 5, 5),
    ("multiply", 4, 5, 20),
])
def test_calculator_operations(operation, a, b, expected):
    calc = Calculator()
    result = getattr(calc, operation)(a, b)
    assert result == expected

# 带自定义 ID
@pytest.mark.parametrize("input_data,expected", [
    pytest.param({"name": "Alice"}, "Alice", id="valid_name"),
    pytest.param({"name": ""}, None, id="empty_name"),
    pytest.param({}, None, id="missing_name"),
])
def test_extract_name(input_data, expected):
    result = extract_name(input_data)
    assert result == expected
```

### 异常测试
```python
def test_invalid_connection():
    with pytest.raises(ConnectionError):
        DatabaseManager.connect("invalid_host", 9999)

def test_divide_by_zero():
    with pytest.raises(ValueError, match="Cannot divide by zero"):
        divide(10, 0)
```

### 测试预期失败
```python
@pytest.mark.xfail(reason="Known bug #123")
def test_known_bug():
    assert False

@pytest.mark.skip(reason="Not implemented yet")
def test_future_feature():
    pass

@pytest.mark.skipif(sys.platform == "win32", reason="Unix-only test")
def test_unix_specific():
    pass
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

### Mock 带副作用
```python
def test_retry_on_failure(mocker):
    # 第一次失败，第二次成功
    mock_api = mocker.patch("requests.get")
    mock_api.side_effect = [
        requests.exceptions.Timeout(),  # 第一次
        mocker.Mock(json=lambda: {"status": "ok"})  # 第二次
    ]

    result = api_call_with_retry()
    assert result["status"] == "ok"
    assert mock_api.call_count == 2
```

## 测试标记

### 自定义标记
```python
# conftest.py
def pytest_configure(config):
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line("markers", "integration: marks tests as integration")
    config.addinivalue_line("markers", "unit: marks tests as unit")

# 测试文件
@pytest.mark.unit
def test_fast_unit():
    assert True

@pytest.mark.integration
@pytest.mark.slow
def test_slow_integration():
    time.sleep(10)
    assert True
```

### 运行特定标记
```bash
pytest -m slow              # 只运行 slow 测试
pytest -m "not slow"        # 排除 slow 测试
pytest -m unit               # 只运行单元测试
pytest -m "unit or integration"  # 运行单元或集成测试
```

## 测试覆盖率

### 安装和运行
```bash
pip install pytest-cov
pytest --cov=src --cov-report=html --cov-report=term-missing
pytest --cov=src --cov-fail-under=80  # 覆盖率低于 80% 则失败
```

### pytest.ini 配置
```ini
[pytest]
minversion = 7.0
python_files = test_*.py *_test.py
python_classes = Test*
python_functions = test_*
testpaths = tests
addopts =
    -v
    --strict-markers
    --cov=src
    --cov-report=html
    --cov-report=term-missing
    --cov-fail-under=80

markers =
    unit: Unit tests
    integration: Integration tests
    slow: Slow-running tests
```

### 覆盖率目标
- 核心业务逻辑：90%+
- 工具函数：80%+
- 整体项目：80%+

## 常用命令

### 基本运行
```bash
pytest                          # 运行所有测试
pytest -v                       # 详细输出
pytest -s                       # 显示 print 输出
pytest -x                       # 首次失败时停止
pytest -k "test_name"           # 运行匹配的测试
pytest tests/test_module.py      # 运行特定文件
pytest tests/test_module.py::test_specific  # 运行特定测试
```

### 调试
```bash
pytest -s                       # 显示 print 输出
pytest --pdb                    # 失败时进入 pdb
pytest --trace                  # 进入每个测试
pytest -l                       # 显示局部变量
```

### 并行运行
```bash
pip install pytest-xdist
pytest -n 4                     # 使用 4 个进程并行运行
pytest -n auto                  # 自动选择进程数
```

### 其他选项
```bash
pytest --lf                    # 只运行上次失败的测试
pytest --ff                    # 先运行失败的测试
pytest -q                       # 简化输出
pytest -vv                      # 超详细输出
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

### 测试一件事
```python
# 错误：测试多个东西
def test_user_workflow():
    user = create_user()
    assert user.id is not None
    updated = update_user(user.id, name="New")
    assert updated.name == "New"

# 正确：分离测试
def test_user_creation():
    user = create_user()
    assert user.id is not None

def test_user_update():
    user = create_user()
    updated = update_user(user.id, name="New")
    assert updated.name == "New"
```

### Mock 外部依赖
```python
# 正确：Mock 外部 API
def test_fetch_user_data(mocker):
    mocker.patch("requests.get", return_value=mock_response)
    result = fetch_user_data(user_id=1)
    assert result["name"] == "Alice"

# 错误：真实 API 调用
def test_fetch_user_data():
    result = fetch_user_data(user_id=1)  # 真实 HTTP 请求！
    assert result["name"] == "Alice"
```

## 常见陷阱

### 1. 测试依赖顺序
```python
# 错误：测试之间有依赖
class TestUserWorkflow:
    user_id = None

    def test_create_user(self):
        user = create_user()
        TestUserWorkflow.user_id = user.id

    def test_update_user(self):
        # 如果 test_create_user 没运行则失败！
        update_user(TestUserWorkflow.user_id, name="New")

# 正确：每个测试独立
@pytest.fixture
def created_user():
    return create_user()

def test_create_user(created_user):
    assert created_user.id is not None

def test_update_user(created_user):
    update_user(created_user.id, name="New")
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

### 4. 不清理资源
```python
# 错误：数据库未清理
def test_user_creation():
    db = setup_database()
    user = create_user(db)
    assert user.id is not None

# 正确：使用 fixture 清理
@pytest.fixture
def db():
    database = setup_database()
    yield database
    database.close()

def test_user_creation(db):
    user = create_user(db)
    assert user.id is not None
```

## conftest.py 示例
```python
import pytest
import pandas as pd
from unittest.mock import MagicMock
import tempfile
import shutil

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

@pytest.fixture
def temp_directory():
    """创建临时目录"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)

@pytest.fixture
def mock_llm_client(mocker):
    """Mock LLM 客户端"""
    mock_response = {
        "sql": "SELECT * FROM users",
        "reasoning": "Test"
    }
    return mocker.patch("src.llm_client.LLMClient._call_api", return_value=mock_response)

def pytest_configure(config):
    """配置自定义标记"""
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line("markers", "integration: marks tests as integration")
    config.addinivalue_line("markers", "unit: marks tests as unit")
```

## 禁止事项

- 禁止测试之间有依赖关系
- 禁止 Mock 被测试的代码
- 禁止为了覆盖率写无意义的测试
- 禁止不清理临时资源
- 禁止在测试中使用硬编码值
- 禁止测试实现细节而非行为
- 禁止使用裸 `except:` 捕获所有异常
