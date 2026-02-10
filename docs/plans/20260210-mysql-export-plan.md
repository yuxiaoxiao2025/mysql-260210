# MySQL 数据导出工具实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** 构建一个交互式 Python 工具，用于连接远程 MySQL 数据库，并根据用户自然语言需求生成美观的 Excel 报表。

**Architecture:** 
- **Core**: 使用 SQLAlchemy 管理数据库连接，支持连接池。
- **Schema**: 自动扫描并缓存数据库 Schema，用于辅助理解用户查询。
- **Data**: 使用 Pandas 进行数据处理和 DataFrame 生成。
- **Export**: 使用 XlsxWriter 生成带格式的 Excel 文件。
- **CLI**: 使用 `argparse` 或简单的 `input()` 循环进行交互。

**Tech Stack:** Python 3.10+, SQLAlchemy, PyMySQL, Pandas, XlsxWriter, python-dotenv (安全管理凭证)

---

### Task 1: 项目初始化与环境配置

**Files:**
- Create: `requirements.txt`
- Create: `.env` (从 mysql.md 提取凭证，并在 .gitignore 中排除)
- Create: `.gitignore`
- Create: `src/__init__.py`
- Create: `src/config.py`

**Step 1: 创建 .gitignore**
添加 `__pycache__/`, `.env`, `output/`, `*.pyc`, `.venv/` 等常见忽略项。

**Step 2: 创建 requirements.txt**
包含 `SQLAlchemy`, `PyMySQL`, `pandas`, `XlsxWriter`, `python-dotenv`, `openpyxl`。

**Step 3: 创建 .env 文件**
从 `mysql.md` 中提取数据库连接信息，写入 `.env` 文件。
格式：
```
DB_HOST=101.231.132.10
DB_PORT=33306
DB_USER=haplink
DB_PASSWORD=ER#$R353e4Aba3
DB_NAME=cloudinterface
```

**Step 4: 创建配置加载模块 src/config.py**
编写代码使用 `dotenv` 加载环境变量，并提供 `get_db_url()` 函数返回 SQLAlchemy 连接字符串。

**Step 5: 安装依赖**
运行 `pip install -r requirements.txt`。

**Step 6: 验证连接**
编写临时脚本 `scripts/test_conn.py` 尝试连接数据库并打印版本号。

---

### Task 2: 数据库连接与 Schema 扫描

**Files:**
- Create: `src/db_manager.py`
- Create: `tests/test_db_manager.py`

**Step 1: 编写 DatabaseManager 类**
在 `src/db_manager.py` 中实现 `DatabaseManager` 类。
- `__init__`: 初始化 engine。
- `get_connection`: 获取连接。
- `execute_query(sql)`: 执行 SQL 返回 Pandas DataFrame。

**Step 2: 实现 Schema 扫描功能**
添加 `get_all_tables()` 和 `get_table_schema(table_name)` 方法。
- 使用 `inspect(engine)` 获取表名和列信息。
- 将 Schema 信息保存为简单的文本或 JSON 格式，便于后续查阅（暂时打印到控制台或保存到 logs）。

**Step 3: 编写测试**
在 `tests/test_db_manager.py` 中编写测试，验证能否连接、查询和获取 Schema。

**Step 4: 运行测试**
运行 `pytest` 确保功能正常。

---

### Task 3: 报表生成与美化模块

**Files:**
- Create: `src/exporter.py`
- Create: `tests/test_exporter.py`

**Step 1: 编写 ExcelExporter 类**
在 `src/exporter.py` 中实现 `ExcelExporter` 类。
- `export(dataframe, filename, sheet_name)`: 接收 DataFrame 并导出。

**Step 2: 实现美化逻辑**
使用 `XlsxWriter` 引擎：
- 设置表头样式（背景色、加粗、边框）。
- 设置数据行样式（隔行变色）。
- 自动调整列宽。
- 冻结首行。
- 启用自动筛选。

**Step 3: 编写测试**
创建 mock DataFrame，调用 `export` 方法，生成 `output/test_export.xlsx`。

**Step 4: 手动验证**
打开生成的 Excel 文件检查样式是否符合预期。

---

### Task 4: 交互式主程序

**Files:**
- Create: `main.py`

**Step 1: 编写主循环**
实现一个简单的 REPL (Read-Eval-Print Loop)：
1. 启动时初始化 `DatabaseManager`。
2. 打印欢迎信息和可用表列表。
3. 进入循环：
    - 提示用户输入 SQL 查询（或自然语言需求，暂时先支持直接 SQL 或预定义命令）。
    - 接收输入。
    - 如果是 'exit'/'quit' 则退出。
    - 执行查询。
    - 调用 `ExcelExporter` 导出。
    - 打印结果路径。

**Step 2: 集成测试**
运行 `python main.py`，尝试执行简单的 `SELECT * FROM config LIMIT 5`，验证流程全通。

---

### Task 5: (可选) 基础自然语言解析模拟

*注：真正的自然语言转 SQL 需要 LLM 支持。在此阶段，我们可以实现简单的关键词匹配或预定义模板，作为“智能”的雏形。*

**Files:**
- Modify: `main.py`

**Step 1: 添加简单的命令解析**
如果用户输入不是 SQL（不以 SELECT 开头），尝试解析为特定指令，例如：
- "导出 config 表" -> `SELECT * FROM config`
- "查询所有表" -> 列出所有表名

**Step 2: 完善用户提示**
引导用户如何输入。
