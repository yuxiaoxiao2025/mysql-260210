# Python 最佳实践

## 概述
遵循 PEP 8 规范和 Python 3.10+ 特性，编写清晰、可维护、类型安全的代码。

## 核心规范

### PEP 8 风格指南
- 使用 Black formatter 默认设置（88 字符行长度）
- 使用 4 个空格缩进，禁止使用 tab
- 使用有意义的描述性变量名
- 保持函数职责单一（单一职责原则）

### 类型提示（Type Hints）
- 始终为函数签名包含类型注解
- 从 `typing` 模块导入：`List`, `Dict`, `Optional`, `Union` 等
- 使用 `TypeAlias` 定义复杂类型
- 优先使用显式类型而非隐式类型

```python
from typing import List, Optional, Dict, Any
from pathlib import Path

def process_items(
    items: List[str],
    limit: Optional[int] = None
) -> List[str]:
    """处理项目到可选限制。

    Args:
        items: 要处理的项目列表
        limit: 最大处理项目数（None = 全部）

    Returns:
        处理后的项目

    Raises:
        ValueError: 如果 limit 为负数
    """
    if limit is not None and limit < 0:
        raise ValueError(f"Limit must be non-negative, got {limit}")
    return items[:limit] if limit else items
```

### 现代 Python 习惯用法
- 使用 f-strings 进行字符串格式化
- 优先使用 `pathlib.Path` 而非 `os.path`
- 使用 dataclasses 或 Pydantic 定义数据结构
- 为公共函数/类编写 docstring（Google 或 NumPy 风格）
- 使用 `@property` 定义计算属性

```python
from dataclasses import dataclass
from pathlib import Path

@dataclass
class Config:
    name: str
    version: str
    debug: bool = False

    @property
    def config_file(self) -> Path:
        """配置文件路径。"""
        return Path(f"{self.name}-{self.version}.json")

    def __post_init__(self) -> None:
        """初始化后验证配置。"""
        if not self.name:
            raise ValueError("Config name cannot be empty")

# 使用 f-strings
name = "Alice"
message = f"Hello, {name}!"
```

## 错误处理

### 健壮的错误处理
- 使用特定异常类型（`ValueError`, `TypeError`, `KeyError`）
- 提供有帮助的、可操作的错误消息
- 使用上下文管理器清理资源（`with` 语句）
- 避免裸 `except:` 子句

```python
# 正确方式
import logging

logger = logging.getLogger(__name__)

try:
    result = risky_operation()
except (ValueError, TypeError) as e:
    logger.error(f"操作失败: {e}")
    raise
except ConnectionError as e:
    logger.error(f"连接失败: {e}")
    raise

# 错误方式 - 不要使用
try:
    risky_operation()
except:
    pass
```

### 上下文管理器
```python
from contextlib import contextmanager
from typing import Iterator

@contextmanager
def open_resource(path: str) -> Iterator[Any]:
    """打开资源并自动清理。"""
    resource = FileHandle(path)
    try:
        resource.open()
        yield resource
    finally:
        resource.close()

# 使用
with open_resource("data.txt") as f:
    data = f.read()
```

## 反模式避免

### 可变默认参数
```python
# 错误
def add_item(item, items=[]):
    items.append(item)
    return items

# 正确
def add_item(item, items=None):
    if items is None:
        items = []
    items.append(item)
    return items
```

### 裸异常捕获
```python
# 错误
try:
    risky_operation()
except:
    pass

# 正确
try:
    risky_operation()
except (ValueError, TypeError) as e:
    logger.error(f"操作失败: {e}")
    raise
```

## 命名规范

```python
# 变量、函数、方法、包、模块
lower_case_with_underscores = "value"

# 类和异常
class DatabaseManager:
    pass

class ConnectionError(Exception):
    pass

# 受保护方法
def _internal_method(self):
    pass

# 私有方法
def __private_method(self):
    pass

# 常量
MAX_CONNECTIONS = 100
DEFAULT_TIMEOUT = 30
```

## 导入顺序

```python
# 系统导入
import os
import sys
from pathlib import Path
from datetime import datetime

# 第三方导入
import sqlalchemy
import pandas as pd
from dotenv import load_dotenv

# 本地源树导入
from src.db_manager import DatabaseManager
from src.llm_client import LLMClient
```

## 文档字符串

```python
def connect_database(host: str, port: int) -> bool:
    """连接到数据库。

    Args:
        host: 数据库主机地址
        port: 数据库端口号

    Returns:
        连接成功返回 True，否则返回 False

    Raises:
        ConnectionError: 连接失败时抛出
    """
    pass

class DataExporter:
    """数据导出器，支持多种格式。

    Args:
        output_dir: 输出目录路径
    """

    def __init__(self, output_dir: str):
        self.output_dir = output_dir
```

## 代码风格

```python
# 缩进：4 个空格（不要使用 tab）

# 行长度：建议 88 字符（Black 默认）
long_string = (
    "This is a very long string that spans multiple lines "
    "to keep line length within recommended limit"
)

# 使用 with 语句管理资源
with open('file.txt', 'r') as f:
    content = f.read()

# 避免冗余命名
import audio
core = audio.Core()  # 正确
core = audio.AudioCore()  # 错误 - 冗余
```

## 最佳实践

### 避免常见错误
```python
# 不要比较 True/False/None
if value:  # 正确
    pass

if value is None:  # 正确
    pass

if value == True:  # 错误
    pass

if value == None:  # 错误
    pass

# 使用列表推导式
result = [item for item in items if item > 5]  # 正确

result = []
for item in items:
    if item > 5:
        result.append(item)  # 可以，但不推荐
```

### 性能优化
```python
# 避免在循环中重复计算
for item in items:
    result = expensive_function(item)  # 每次都计算

# 缓存结果
cached_result = expensive_function(items)
for item in cached_result:
    pass

# 使用生成器处理大数据
def process_large_file(file_path):
    with open(file_path, 'r') as f:
        for line in f:  # 逐行读取，不加载整个文件
            yield process_line(line)
```

### 日志记录
```python
import logging

logger = logging.getLogger(__name__)

logger.debug("调试信息")
logger.info("常规信息")
logger.warning("警告信息")
logger.error("错误信息")
logger.critical("严重错误")
```

## 常用工具
- **代码格式化**: `black src/ tests/`
- **代码检查**: `ruff check src/ tests/`
- **类型检查**: `mypy src/`
- **导入排序**: `ruff check --select I src/`

## 推荐库
- **pydantic**: 使用类型提示的数据验证
- **httpx**: 现代 HTTP 客户端
- **rich**: 美观的终端输出
- **typer**: 带类型提示的 CLI 框架
