# MySQL260227 - 漕河泾停车云数据导出工具

## 项目概述
基于 SQLAlchemy 和 MySQL 的数据导出工具，支持 SQL 查询和 AI 自然语言查询，将结果导出为 Excel 文件。

## 技术栈
- **语言**: Python 3
- **数据库**: MySQL (PyMySQL 连接器)
- **ORM**: SQLAlchemy
- **测试**: pytest
- **数据处理**: pandas
- **Excel**: openpyxl, XlsxWriter
- **AI**: dashscope (通义千问)
- **环境**: python-dotenv

## 禁止事项
- 禁止在代码中硬编码数据库凭据（必须使用环境变量）
- 禁止使用 tab 缩进，必须使用 4 个空格
- 禁止直接执行用户输入的 SQL，必须先验证或使用参数化查询
- 禁止使用 `from module import *` 导入方式
- 禁止提交 `.env` 文件或任何包含密钥的文件
- 禁止在生产代码中使用 `print` 进行调试，应使用 logging
- 禁止不关闭数据库连接或文件句柄

## 核心规范

### 命名规范
- **变量、函数、方法、包、模块**: `lower_case_with_underscores`
- **类和异常**: `CapWords`
- **受保护方法**: `_single_leading_underscore(self, ...)`
- **私有方法**: `__double_leading_underscore(self, ...)`
- **常量**: `ALL_CAPS_WITH_UNDERSCORES`

### 导入顺序
```python
# 系统导入
import os
import sys

# 第三方导入
import sqlalchemy
import pandas
from dotenv import load_dotenv

# 本地源树导入
from src.db_manager import DatabaseManager
from src.llm_client import LLMClient
```

### 数据库操作
- 使用 SQLAlchemy Core 构建查询（非 ORM）
- 使用 `with` 语句管理数据库连接
- 使用参数化查询防止 SQL 注入
- 确保正确处理连接池和事务

### 测试规范
- 测试文件命名：`test_*.py` 或 `*_test.py`
- 测试函数命名：`test_*`
- 使用 `@pytest.fixture` 创建共享测试数据
- 使用 `monkeypatch` 或 `unittest.mock` 进行隔离测试
- 测试覆盖率目标：80%+

## 常用命令
| 操作 | 命令 |
|------|------|
| 安装依赖 | `pip install -r requirements.txt` |
| 运行测试 | `pytest` |
| 运行测试（详细输出） | `pytest -v` |
| 测试覆盖率 | `pytest --cov=src` |
| 运行程序 | `python main.py` |
| 代码检查 | `flake8 src/ tests/` |

## 目录结构
```
mysql260227/
├── src/                    # 源代码目录
│   ├── __init__.py
│   ├── config.py          # 配置管理
│   ├── db_manager.py      # 数据库管理
│   ├── llm_client.py      # AI 客户端
│   └── ...
├── tests/                  # 测试目录
│   ├── test_llm_client.py
│   └── test_main_flow.py
├── scripts/                # 脚本目录
│   └── test_conn.py
├── main.py                 # 程序入口
├── requirements.txt        # 依赖列表
├── .env.example            # 环境变量示例
└── .gitignore              # Git 忽略文件
```

## 详细规范
- **Python**: @.agents/python.md
- **Pytest**: @.agents/pytest.md
- **SQLAlchemy**: @.agents/sqlalchemy.md
