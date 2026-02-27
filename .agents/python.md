# Python 最佳实践

## 概述
遵循 PEP 8 规范，编写清晰、可维护的 Python 代码。

## 核心规范

### 命名规范
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

### 导入规范
```python
# 系统导入
import os
import sys
from datetime import datetime

# 第三方导入
import sqlalchemy
import pandas as pd
from dotenv import load_dotenv

# 本地源树导入
from src.db_manager import DatabaseManager
from src.llm_client import LLMClient
```

### 代码风格
```python
# 缩进：4 个空格（不要使用 tab）

# 行长度：建议 80-100 字符
long_string = (
    "This is a very long string that spans multiple lines "
    "to keep line length within the recommended limit"
)

# 使用 with 语句管理资源
with open('file.txt', 'r') as f:
    content = f.read()

# 避免冗余命名
import audio
core = audio.Core()  # 正确
core = audio.AudioCore()  # 错误 - 冗余
```

### 文档字符串
```python
def connect_database(host: str, port: int) -> bool:
    """连接到数据库。

    Args:
        host: 数据库主机地址
        port: 数据库端口号

    Returns:
        连接成功返回 True，否则返回 False
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

### 错误处理
```python
# 不要使用空的 except 块
try:
    result = some_function()
except Exception as e:
    logger.error(f"操作失败: {e}")
    raise

# 使用具体的异常类型
try:
    result = db.execute(query)
except ConnectionError as e:
    logger.error(f"数据库连接失败: {e}")
    raise
except ValueError as e:
    logger.error(f"参数错误: {e}")
    raise
```

### 类型提示
```python
from typing import List, Dict, Optional

def process_data(data: List[Dict[str, any]]) -> Optional[str]:
    """处理数据并返回结果。

    Args:
        data: 要处理的数据列表

    Returns:
        处理结果，失败时返回 None
    """
    if not data:
        return None
    return "processed"
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
- **代码检查**: `flake8`
- **格式化**: `black`
- **类型检查**: `mypy`
- **导入排序**: `isort`
