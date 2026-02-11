# SQL Mutation Preview 功能实现总结

## 任务概述
实现 MySQL 数据变更操作的预览功能，包括安全校验、事务预览和两次确认流程。

## 实现内容

### 1. SQL 安全校验模块 (`src/sql_safety.py`)
- **detect_intent()**: 检测 SQL 语句的意图类型 (insert/update/delete/select/unknown)
- **validate_sql()**: 验证 SQL 语句安全性，拒绝 DROP/ALTER/TRUNCATE 等危险操作

### 2. 事务预览引擎 (`src/txn_preview.py`)
- **summarize_diff()**: 对比 Before/After DataFrame，计算插入/更新/删除的行数

### 3. CLI/HTML 预览渲染 (`src/preview_renderer.py`)
- **should_render_html()**: 根据数据行数决定使用 HTML 还是 CLI 渲染

### 4. LLM 客户端扩展 (`src/llm_client.py`)
- 扩展 `generate_sql()` 返回协议，支持：
  - `intent`: 操作意图 (query/mutation)
  - `preview_sql`: 预览 SQL
  - `key_columns`: 主键列
  - `warnings`: 警告信息
- 添加 `last_result` 属性保存最后一次生成结果

### 5. 数据库管理器 (`src/db_manager.py`)
- **execute_in_transaction()**: 在事务内执行变更操作，返回 Before/After 数据和差异摘要

### 6. CLI 主流程集成 (`main.py`)
- 危险 SQL 拒绝 (DROP/ALTER/TRUNCATE)
- DML 操作检测 (INSERT/UPDATE/DELETE)
- 两次确认流程：
  1. 第一次：执行事务预览 (commit=False)，显示差异摘要
  2. 第二次：用户确认后提交 (commit=True) 或回滚

## 测试覆盖

### 测试文件
- `tests/test_sql_safety.py`: SQL 安全校验测试 (15 tests)
- `tests/test_txn_preview.py`: 事务预览引擎测试 (6 tests)
- `tests/test_preview_renderer.py`: 预览渲染测试 (5 tests)
- `tests/test_llm_client.py`: LLM 客户端测试 (5 tests)
- `tests/test_main_logic.py`: 主流程逻辑测试 (10 tests)
- `tests/test_integration.py`: 集成测试 (3 tests)

### 测试结果
```
======================= 52 passed, 2 warnings in 2.35s ========================
```

## 遵循的设计原则

### KISS (简单至上)
- 每个模块职责单一，代码简洁
- 事务预览流程清晰：预览 -> 确认 -> 提交/回滚

### DRY (杜绝重复)
- 复用 `sql_safety` 模块进行意图检测和安全校验
- 复用 `txn_preview` 模块计算差异摘要

### SOLID 原则
- **单一职责**: 每个模块专注于特定功能
- **开闭原则**: 可通过扩展关键字列表增强安全检查
- **依赖倒置**: 主流程依赖抽象接口 (validate_sql, detect_intent)

## 使用示例

### 直接输入 SQL
```sql
UPDATE users SET name='test' WHERE id=1
```
输出：
```
⚠️  检测到数据变更操作 (INSERT/UPDATE/DELETE)
⚠️  直接输入的 SQL 缺少预览信息，建议使用自然语言模式。
❓ 仍要继续执行吗？(y/n) >
```

### 自然语言输入
```
把用户ID为1的用户名改为test
```
输出：
```
🤖 生成的 SQL: UPDATE users SET name='test' WHERE id=1
💡 思考过程: ...
❓ 是否执行此查询？(y/n) > y
🔍 正在预览变更...
📊 变更预览:
  - 插入: 0 行
  - 更新: 1 行
  - 删除: 0 行
❓ 确认要提交这些变更吗？(y/n) > y
✅ 变更已提交！
```

### 危险操作拒绝
```sql
DROP TABLE users
```
输出：
```
❌ 危险操作，拒绝执行: Disallowed keyword: drop
```

## 文件修改清单

### 修改的文件
- `main.py`: 添加安全校验和事务预览流程
- `src/llm_client.py`: 扩展返回协议，添加 last_result 属性

### 新增的文件
- `src/sql_safety.py`: SQL 安全校验模块
- `src/txn_preview.py`: 事务预览引擎模块
- `src/preview_renderer.py`: 预览渲染模块
- `tests/test_sql_safety.py`: 安全校验测试
- `tests/test_txn_preview.py`: 事务预览测试
- `tests/test_preview_renderer.py`: 预览渲染测试
- `tests/test_main_logic.py`: 主流程逻辑测试
- `tests/test_integration.py`: 集成测试

## 下一步

任务 #6 已解锁，可以进行全量测试与质量门禁检查。
