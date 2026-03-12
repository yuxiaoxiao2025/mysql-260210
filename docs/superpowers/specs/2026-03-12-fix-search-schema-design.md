# 修复 search_schema 工具缺少字段信息问题

> 设计日期: 2026-03-12
> 状态: 待实施
> 优先级: P0
> 关联问题: 模型猜测字段名导致 SQL 执行失败

---

## 一、问题描述

### 1.1 问题现象

```
用户：帮我查一下沪BAB1565

模型调用 search_schema("沪BAB1565") → 返回：
找到以下相关表：
- db_parking_center.t_in_info
- p210121194329.car_inout_state
...

模型猜测字段名为 plate_no（错误！）
SQL: SELECT * FROM t_in_info WHERE plate_no = '沪BAB1565'
错误: Unknown column 'plate_no' in 'where clause'

模型重试多次仍失败 → 返回 "抱歉，我需要更多时间..."
```

### 1.2 根本原因

| 问题 | 原因 |
|------|------|
| `search_schema` 只返回表名 | 缺少字段信息 |
| 模型猜测字段名 | 无正确字段名参考 |
| 错误重试仍失败 | 仍缺少字段信息 |

---

## 二、解决方案

### 2.1 核心改动

**增强 `search_schema` 工具，返回完整表结构信息：**
- 表名
- 字段名（关键！）
- 字段类型
- 字段注释

### 2.2 设计原则

- **MVP 原则**：最小改动解决问题
- **一步到位**：一次调用获取完整信息
- **减少轮次**：避免多次工具调用
- **容错设计**：处理异常情况，保证可用性

---

## 三、详细设计

### 3.1 工具定义修改

**文件：** `src/react/tools.py`

```python
{
    "type": "function",
    "function": {
        "name": "search_schema",
        "description": "搜索数据库中与查询相关的表，返回完整的表结构信息（包含字段名、类型、注释）。用于了解数据结构、查找正确字段名。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词，如表名、字段名、业务术语（如：车牌、园区、入场）"
                }
            },
            "required": ["query"]
        }
    }
}
```

**关键变化：**
- 描述明确说明返回"完整表结构信息"
- 强调用于"查找正确字段名"

### 3.2 工具服务修改

**文件：** `src/react/tool_service.py`

**方法：** `_tool_search_schema`

**完整实现逻辑：**

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
        # TableMatch 已包含 database_name 和 table_name 字段
        db_name = getattr(match, 'database_name', None)
        table_name = match.table_name

        # 处理 "db.table" 格式
        if '.' in table_name and not db_name:
            parts = table_name.split('.', 1)
            db_name = parts[0]
            table_name = parts[1]

        display_name = f"{db_name}.{table_name}" if db_name else table_name
        lines.append(f"\n### 表：{display_name}")

        # 获取字段信息（带错误处理）
        try:
            if db_name:
                # 跨库查询
                schema_info = self.db.get_table_schema(table_name, schema=db_name)
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

**关键设计点：**

| 设计点 | 说明 |
|--------|------|
| 跨库表名解析 | 利用 `TableMatch.database_name` 或解析 `db.table` 格式 |
| Token 限制 | 最多返回 3 个表，每表最多 10 个字段 |
| 错误处理 | try-catch 包裹，失败时降级返回提示信息 |
| 字段数量提示 | 超过限制时显示总字段数 |

### 3.3 系统提示修改

**文件：** `src/react/tools.py`

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

---

## 四、影响范围

| 文件 | 改动类型 | 改动内容 |
|------|----------|----------|
| `src/react/tools.py` | 修改 | 工具定义描述、SYSTEM_PROMPT |
| `src/react/tool_service.py` | 修改 | `_tool_search_schema` 方法 |
| `tests/unit/react/test_tool_service.py` | 修改 | 新增测试用例 |

---

## 五、验收标准

### 5.1 功能验收

- [ ] `search_schema("车牌")` 返回包含字段信息的完整表结构
- [ ] 字段信息包含：字段名、类型、注释
- [ ] 跨库表名（`db.table` 格式）能正确解析
- [ ] 数据库查询失败时能优雅降级
- [ ] 返回结果符合 Token 限制（≤3 表，每表 ≤10 字段）

### 5.2 场景验收

**测试场景：**
```
用户：帮我查一下沪BAB1565

预期：
1. 模型调用 search_schema
2. 返回结果包含 plate 字段（而非 plate_no）
3. 模型使用正确字段名编写 SQL
4. 查询成功执行
```

### 5.3 单元测试验收

```python
# tests/unit/react/test_tool_service.py

def test_search_schema_returns_field_info():
    """测试返回字段信息"""

def test_search_schema_cross_db_table():
    """测试跨库表名解析 (db.table 格式)"""

def test_search_schema_error_handling():
    """测试错误处理 - 数据库查询失败时降级"""

def test_search_schema_token_limit():
    """测试 Token 限制 - 验证返回数量限制"""

def test_search_schema_empty_result():
    """测试无结果时的处理"""
```

---

## 六、替代方案（备选）

如果 `DatabaseManager.get_table_schema()` 性能不佳，可考虑：

### 6.1 利用现有知识图谱

`RetrievalAgent.get_table_details()` 已返回完整表结构：

```python
# retrieval_agent.py:263-307
def get_table_details(self, table_name: str) -> dict:
    """返回表详情，包含 columns 字段"""
```

**优势：**
- 数据已在内存中，无需数据库查询
- 响应更快

**劣势：**
- 需要确保知识图谱数据是最新的
- 首次查询可能缺少数据

---

## 七、实施计划

| 步骤 | 内容 | 时间 |
|------|------|------|
| Step 1 | 修改工具定义和系统提示 | 10分钟 |
| Step 2 | 修改 `_tool_search_schema` 方法 | 20分钟 |
| Step 3 | 编写单元测试 | 15分钟 |
| Step 4 | 手动测试验证 | 10分钟 |
| Step 5 | 提交代码 | 5分钟 |
| **总计** | | **~60分钟** |

---

*本设计基于 MVP 原则，以最小改动解决核心问题，并包含完善的错误处理和 Token 限制考虑*