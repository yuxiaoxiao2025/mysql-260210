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

**返回格式：**
```
找到 5 个相关表：

### 表：db_parking_center.cloud_fixed_plate
字段列表：
  - id (INT) -- 主键
  - plate (VARCHAR(20)) -- 车牌号
  - state (INT) -- 状态：0已下发，1未下发
  - create_time (DATETIME) -- 创建时间

### 表：p210121194329.car_inout_state
字段列表：
  - id (INT)
  - plate (VARCHAR(20)) -- 车牌
  - in_time (DATETIME) -- 入场时间
```

**关键逻辑：**
1. 调用 `self.retrieval.search()` 获取候选表
2. 对每个候选表调用 `self.db.get_table_schema()` 获取字段
3. 格式化输出，包含字段名、类型、注释

### 3.3 系统提示修改

**文件：** `src/react/tools.py`

**关键新增内容：**
```
## 重要提醒

- 写 SQL 前必须先查看表结构，确认字段名正确
- 不要猜测字段名，如不确定字段名就先用 search_schema 查询
```

---

## 四、影响范围

| 文件 | 改动类型 | 改动内容 |
|------|----------|----------|
| `src/react/tools.py` | 修改 | 工具定义描述、SYSTEM_PROMPT |
| `src/react/tool_service.py` | 修改 | `_tool_search_schema` 方法 |
| `tests/unit/react/test_tool_service.py` | 修改 | 更新测试用例 |

---

## 五、验收标准

### 5.1 功能验收

- [ ] `search_schema("车牌")` 返回包含字段信息的完整表结构
- [ ] 字段信息包含：字段名、类型、注释
- [ ] 多个候选表都能正确返回字段信息
- [ ] 表名包含 database 前缀时能正确解析

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

### 5.3 测试验收

- [ ] 单元测试通过
- [ ] 现有测试不破坏

---

## 六、实施计划

| 步骤 | 内容 | 时间 |
|------|------|------|
| Step 1 | 修改工具定义和系统提示 | 10分钟 |
| Step 2 | 修改 `_tool_search_schema` 方法 | 15分钟 |
| Step 3 | 更新单元测试 | 10分钟 |
| Step 4 | 手动测试验证 | 10分钟 |
| Step 5 | 提交代码 | 5分钟 |
| **总计** | | **~50分钟** |

---

*本设计基于 MVP 原则，以最小改动解决核心问题*