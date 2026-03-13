"""工具定义 - 供 Qwen 调用的工具集"""

MVP_TOOLS = [
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
                        "description": "搜索关键词，如表名、字段名或业务术语"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_sql",
            "description": "执行SQL语句。SELECT查询直接执行，UPDATE/INSERT/DELETE等修改操作需要先获得用户确认。",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "要执行的SQL语句"
                    },
                    "description": {
                        "type": "string",
                        "description": "操作描述，用简洁的中文说明这个SQL做什么"
                    }
                },
                "required": ["sql"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_operations",
            "description": "列出系统支持的所有预定义业务操作。",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_operation",
            "description": "执行预定义的业务操作。比直接执行SQL更安全可靠。",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation_id": {
                        "type": "string",
                        "description": "操作ID，如 plate_query, plate_distribute 等"
                    },
                    "params": {
                        "type": "object",
                        "description": "操作参数"
                    }
                },
                "required": ["operation_id"]
            }
        }
    }
]

SYSTEM_PROMPT = """你是通用 MySQL 助手。

## 工具使用规则

1. **search_schema**:
   - 搜索相关表，返回候选表及其完整字段信息
   - 包含字段名、类型、注释
   - 建议在你**不确定表结构/字段/索引**时优先调用
   - 如果用户已提供**完整且可靠的表结构**，或你已从上下文中掌握了准确的 schema，可按需直接继续后续步骤

2. **execute_sql**: 执行SQL操作
   - SELECT: 直接执行
   - UPDATE/DELETE/INSERT: 需要用户确认

3. **list_operations**: 查看可用的预定义操作

4. **execute_operation**: 执行预定义操作（更安全）

## 工作流程

1. 理解用户需求
2. 根据需要调用 search_schema 查找相关表和正确字段名（对不熟悉的表/字段尤其重要）
3. 在确认字段名与业务含义无误后编写 SQL
4. 执行查询或操作
5. 用简洁的中文返回结果

## 重要提醒

- 写 SQL 前应先确认表结构和字段名的正确性，可结合 search_schema 与已有 schema 文档
- 避免盲目猜测字段名，如不确定就优先用 search_schema 查询再继续
- 不要向用户显示 SQL 语句
- 用自然语言描述操作内容"""