# search_schema 工具增强实施计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 增强 search_schema 工具返回完整表结构信息（字段名、类型、注释），解决模型猜测字段名导致 SQL 失败的问题。

**Architecture:** 修改现有 `_tool_search_schema` 方法，添加跨库表名解析、字段信息获取、错误处理，并更新工具定义和系统提示。

**Tech Stack:** Python 3.11+, pytest, unittest.mock

---

## File Structure

```
src/react/
├── tools.py                    # 修改: 工具定义描述、SYSTEM_PROMPT
└── tool_service.py             # 修改: _tool_search_schema 方法

tests/unit/react/
└── test_tool_service.py        # 修改: 新增 6 个测试用例
```

---

## Chunk 1: 工具定义和系统提示修改

### Task 1: 更新工具定义和系统提示

**Files:**
- Modify: `src/react/tools.py`

- [ ] **Step 1: 更新 search_schema 工具定义描述**

将第 8 行的描述从：
```python
"description": "搜索数据库中与查询相关的表和字段。当你需要了解数据结构或查找相关表时使用。",
```

改为：
```python
"description": "搜索数据库中与查询相关的表，返回完整的表结构信息（包含字段名、类型、注释）。用于了解数据结构、查找正确字段名。",
```

- [ ] **Step 2: 更新 SYSTEM_PROMPT**

将第 76-98 行的 `SYSTEM_PROMPT` 替换为：

```python
SYSTEM_PROMPT = """你是智能停车数据库助手。

## 工具使用规则

1. **search_schema**:
   - 搜索相关表，返回候选表及其完整字段信息
   - 包含字段名、类型、注释
   - **重要**：写 SQL 前必须先调用此工具确认正确的字段名！

2. **execute_sql**: 执行SQL操作
   - SELECT: 直接执行
   - UPDATE/DELETE/INSERT: 需要用户确认

3. **list_operations**: 查看可用的预定义操作

4. **execute_operation**: 执行预定义操作（更安全）

## 工作流程

1. 理解用户需求
2. **先调用 search_schema 查找相关表和正确字段名**
3. 使用正确的字段名编写 SQL
4. 执行查询或操作
5. 用简洁的中文返回结果

## 重要提醒

- 写 SQL 前必须先查看表结构，确认字段名正确
- 不要猜测字段名，如不确定字段名就先用 search_schema 查询
- 不要向用户显示 SQL 语句
- 用自然语言描述操作内容"""
```

- [ ] **Step 3: 验证修改无语法错误**

```bash
python -c "from src.react.tools import MVP_TOOLS, SYSTEM_PROMPT; print('OK')"
```

预期输出: `OK`

- [ ] **Step 4: Commit**

```bash
git add src/react/tools.py
git commit -m "feat(react): 更新 search_schema 工具定义和系统提示"
```

---

## Chunk 2: 核心方法实现

### Task 2: 重写 _tool_search_schema 方法

**Files:**
- Modify: `src/react/tool_service.py:63-86`

- [ ] **Step 1: 编写测试用例 test_search_schema_returns_field_info**

在 `tests/unit/react/test_tool_service.py` 的 `TestSearchSchema` 类中添加：

```python
def test_search_schema_returns_field_info(self, tool_service):
    """测试返回字段信息"""
    # 模拟匹配结果
    mock_match = Mock()
    mock_match.table_name = "cloud_fixed_plate"
    mock_match.database_name = ""

    mock_result = Mock()
    mock_result.matches = [mock_match]
    tool_service.retrieval.search.return_value = mock_result

    # 模拟数据库返回字段信息
    tool_service.db.get_table_schema.return_value = [
        {"name": "id", "type": "bigint", "comment": "主键ID"},
        {"name": "plate", "type": "varchar(20)", "comment": "车牌号"},
        {"name": "state", "type": "int", "comment": "状态"}
    ]

    result = tool_service._tool_search_schema("车牌")

    assert "cloud_fixed_plate" in result
    assert "plate" in result
    assert "varchar(20)" in result
    assert "车牌号" in result
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/unit/react/test_tool_service.py::TestSearchSchema::test_search_schema_returns_field_info -v
```

预期: FAIL（因为字段信息未返回）

- [ ] **Step 3: 重写 _tool_search_schema 方法**

将 `src/react/tool_service.py` 第 63-86 行替换为：

```python
def _tool_search_schema(self, query: str) -> str:
    """搜索表结构，返回候选表及完整字段信息

    Args:
        query: 搜索关键词

    Returns:
        str: 候选表列表，每个表包含字段名、类型、注释
    """
    result = self.retrieval.search(query, top_k=5)

    if not result.matches:
        return "未找到相关的表。请尝试其他关键词。"

    # 限制返回表数量（考虑 Token 限制）
    max_tables = 3
    max_fields = 10

    lines = [f"找到 {len(result.matches)} 个相关表（显示前 {max_tables} 个）："]

    for match in result.matches[:max_tables]:
        # 跨库表名解析
        # TableMatch.database_name 默认为空字符串 ""，需检查真值
        # 不能用 is not None 判断，因为空字符串也是 truthy 的 falsy 值
        db_name = getattr(match, 'database_name', None) or None
        table_name = match.table_name

        # 处理 "db.table" 格式（当 TableMatch.database_name 为空时）
        if '.' in table_name and not db_name:
            parts = table_name.split('.', 1)
            db_name = parts[0]
            table_name = parts[1]

        display_name = f"{db_name}.{table_name}" if db_name else table_name
        lines.append(f"\n### 表：{display_name}")

        # 获取字段信息（带错误处理）
        try:
            if db_name:
                # 使用专用的跨库查询方法，参数顺序: (db_name, table_name)
                schema_info = self.db.get_table_schema_cross_db(db_name, table_name)
            else:
                schema_info = self.db.get_table_schema(table_name)

            if schema_info:
                lines.append("字段列表：")
                for col in schema_info[:max_fields]:
                    col_name = col['name']
                    col_type = col['type']
                    col_comment = col.get('comment', '')

                    # 格式：字段名 (类型) -- 注释
                    if col_comment:
                        lines.append(f"  - {col_name} ({col_type}) -- {col_comment}")
                    else:
                        lines.append(f"  - {col_name} ({col_type})")

                if len(schema_info) > max_fields:
                    lines.append(f"  ... 共 {len(schema_info)} 个字段")
            else:
                lines.append("  （表结构信息为空）")

        except Exception as e:
            logger.warning(f"获取表 {display_name} 结构失败: {e}")
            lines.append(f"  （字段信息获取失败，请尝试直接查询）")

    return "\n".join(lines)
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/unit/react/test_tool_service.py::TestSearchSchema::test_search_schema_returns_field_info -v
```

预期: PASS

- [ ] **Step 5: Commit**

```bash
git add src/react/tool_service.py tests/unit/react/test_tool_service.py
git commit -m "feat(react): 重写 _tool_search_schema 返回完整字段信息"
```

---

## Chunk 3: 完善测试用例

### Task 3: 添加完整测试覆盖

**Files:**
- Modify: `tests/unit/react/test_tool_service.py`

- [ ] **Step 1: 添加 test_search_schema_cross_db_table**

在 `TestSearchSchema` 类中添加：

```python
def test_search_schema_cross_db_table(self, tool_service):
    """测试跨库表名解析 (db.table 格式)"""
    # 模拟跨库表名
    mock_match = Mock()
    mock_match.table_name = "db_parking_center.cloud_fixed_plate"
    mock_match.database_name = ""  # 空字符串，需从 table_name 解析

    mock_result = Mock()
    mock_result.matches = [mock_match]
    tool_service.retrieval.search.return_value = mock_result

    # 模拟跨库查询
    tool_service.db.get_table_schema_cross_db.return_value = [
        {"name": "plate", "type": "varchar(20)", "comment": "车牌号"}
    ]

    result = tool_service._tool_search_schema("车牌")

    # 验证调用了跨库方法
    tool_service.db.get_table_schema_cross_db.assert_called_once_with(
        "db_parking_center", "cloud_fixed_plate"
    )
    assert "db_parking_center.cloud_fixed_plate" in result
```

- [ ] **Step 2: 添加 test_search_schema_error_handling**

```python
def test_search_schema_error_handling(self, tool_service):
    """测试错误处理 - 数据库查询失败时降级"""
    mock_match = Mock()
    mock_match.table_name = "nonexistent_table"
    mock_match.database_name = ""

    mock_result = Mock()
    mock_result.matches = [mock_match]
    tool_service.retrieval.search.return_value = mock_result

    # 模拟数据库查询失败
    tool_service.db.get_table_schema.side_effect = Exception("表不存在")

    result = tool_service._tool_search_schema("测试")

    assert "nonexistent_table" in result
    assert "字段信息获取失败" in result
```

- [ ] **Step 3: 添加 test_search_schema_token_limit**

```python
def test_search_schema_token_limit(self, tool_service):
    """测试 Token 限制 - 验证返回数量限制"""
    # 创建 5 个匹配结果
    matches = []
    for i in range(5):
        m = Mock()
        m.table_name = f"table_{i}"
        m.database_name = ""
        matches.append(m)

    mock_result = Mock()
    mock_result.matches = matches
    tool_service.retrieval.search.return_value = mock_result

    # 模拟返回 15 个字段
    tool_service.db.get_table_schema.return_value = [
        {"name": f"col_{j}", "type": "int", "comment": ""} for j in range(15)
    ]

    result = tool_service._tool_search_schema("测试")

    # 验证只显示 3 个表
    assert "显示前 3 个" in result
    assert "table_0" in result
    assert "table_2" in result
    assert "table_3" not in result  # 第 4 个表不显示

    # 验证字段数量限制
    assert "共 15 个字段" in result
```

- [ ] **Step 4: 添加 test_search_schema_empty_result**

```python
def test_search_schema_empty_result(self, tool_service):
    """测试无结果时的处理 - 规格文档要求的第5个测试"""
    # 模拟无匹配结果
    mock_result = Mock()
    mock_result.matches = []
    tool_service.retrieval.search.return_value = mock_result

    result = tool_service._tool_search_schema("不存在的表")

    assert "未找到相关的表" in result
```

- [ ] **Step 5: 添加 test_search_schema_with_database_name_attr**

```python
def test_search_schema_with_database_name_attr(self, tool_service):
    """测试 TableMatch.database_name 已有值的情况"""
    mock_match = Mock()
    mock_match.table_name = "cloud_fixed_plate"
    mock_match.database_name = "db_parking_center"  # 已有值

    mock_result = Mock()
    mock_result.matches = [mock_match]
    tool_service.retrieval.search.return_value = mock_result

    tool_service.db.get_table_schema_cross_db.return_value = [
        {"name": "plate", "type": "varchar(20)", "comment": "车牌号"}
    ]

    result = tool_service._tool_search_schema("车牌")

    # 验证使用 database_name 属性
    tool_service.db.get_table_schema_cross_db.assert_called_once_with(
        "db_parking_center", "cloud_fixed_plate"
    )
```

- [ ] **Step 6: 运行所有新测试**

```bash
pytest tests/unit/react/test_tool_service.py::TestSearchSchema -v
```

预期: 全部 PASS

- [ ] **Step 7: 运行完整测试套件确认无破坏**

```bash
pytest tests/unit/react/test_tool_service.py -v
```

预期: 全部 PASS

- [ ] **Step 8: Commit**

```bash
git add tests/unit/react/test_tool_service.py
git commit -m "test(react): 添加 search_schema 完整测试覆盖"
```

---

## Chunk 4: 集成验证

### Task 4: 手动测试和验证

**Files:**
- 无文件修改，仅测试

- [ ] **Step 1: 运行完整测试套件**

```bash
pytest tests/ -v --tb=short
```

预期: 全部 PASS

- [ ] **Step 2: 手动测试 - 启动应用**

```bash
python main.py
```

- [ ] **Step 3: 手动测试 - 进入 ReACT 模式**

输入:
```
react
```

- [ ] **Step 4: 手动测试 - 测试搜索功能**

输入:
```
帮我查一下沪BAB1565
```

预期:
- 模型调用 `search_schema`
- 返回结果包含字段信息（如 `plate` 字段）
- 模型使用正确字段名编写 SQL

- [ ] **Step 5: 最终 Commit（如有修复）**

如果有修复，执行：
```bash
git add -A
git commit -m "fix(react): 修复 search_schema 集成问题"
```

---

## 验收清单

- [ ] `search_schema("车牌")` 返回包含字段信息的完整表结构
- [ ] 字段信息包含：字段名、类型、注释
- [ ] 跨库表名（`db.table` 格式）能正确解析
- [ ] 数据库查询失败时能优雅降级
- [ ] 返回结果符合 Token 限制（≤3 表，每表 ≤10 字段）
- [ ] 所有单元测试通过（共 6 个新测试 + 原有测试）
- [ ] 手动测试验证功能正常

---

*本计划由 Claude Code 生成，遵循 TDD、DRY、YAGNI 原则*