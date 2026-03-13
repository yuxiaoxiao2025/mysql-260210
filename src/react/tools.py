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
    },
    {
        "type": "function",
        "function": {
            "name": "list_tables",
            "description": "列出当前数据库中的部分表名，用于让你了解有哪些可用表。",
            "parameters": {
                "type": "object",
                "properties": {
                    "db_name": {
                        "type": "string",
                        "description": "可选，指定数据库名；不提供时使用当前默认数据库"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "describe_table",
            "description": "查看指定表的结构信息（字段名、类型、注释），用于快速理解单张表结构。",
            "parameters": {
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "表名（不带反引号）"
                    },
                    "db_name": {
                        "type": "string",
                        "description": "可选，指定数据库名；不提供时使用当前默认数据库或连接库"
                    }
                },
                "required": ["table_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_indexes",
            "description": "查看某个表在 information_schema.statistics 中的索引元数据，返回索引名、列顺序、唯一性、类型等摘要信息。",
            "parameters": {
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "要查看索引的表名"
                    },
                    "db_name": {
                        "type": "string",
                        "description": "可选，指定数据库名；不提供时使用当前默认数据库或连接库"
                    }
                },
                "required": ["table_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "explain_sql",
            "description": "对只读 SQL（SELECT/SHOW/DESC/DESCRIBE/EXPLAIN/WITH）执行 EXPLAIN，并返回执行计划摘要（possible_keys/key/rows/是否全表扫描等），不展示 SQL 原文。",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "需要分析的只读 SQL 语句"
                    },
                    "purpose": {
                        "type": "string",
                        "description": "可选，对这次分析目的的简要说明，例如“检查是否走索引”"
                    }
                },
                "required": ["sql"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_readonly_sql",
            "description": "在严格只读白名单（SELECT/SHOW/DESC/DESCRIBE/EXPLAIN/WITH）下执行 SQL，返回 DataFrame 摘要（总行数 + 前几行），不展示 SQL 原文。",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "要执行的只读 SQL 语句"
                    },
                    "purpose": {
                        "type": "string",
                        "description": "可选，本次查询的业务目的说明，方便审计和后续解释"
                    }
                },
                "required": ["sql"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_skills",
            "description": "查找可以安装的 skills 插件（例如通过 npx skills find），用于在能力不足时探索可用扩展。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词，例如“mysql index”或“react ui”"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "install_skill",
            "description": "安装指定的 skill（例如通过 npx skills add），用于在确认后为系统增加新能力。",
            "parameters": {
                "type": "object",
                "properties": {
                    "spec": {
                        "type": "string",
                        "description": "skill 标识或安装 spec，例如仓库路径或 npm 包名"
                    },
                    "global_install": {
                        "type": "boolean",
                        "description": "是否以全局方式安装，默认 True",
                        "default": True
                    }
                },
                "required": ["spec"]
            }
        }
    }
    ,
    {
        "type": "function",
        "function": {
            "name": "list_capabilities",
            "description": "汇总当前可用工具、预定义操作与 skills 状态，便于回答“你可以干什么”。",
            "parameters": {
                "type": "object",
                "properties": {}
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

## 策略建议（软规则）

- 默认**不展示 SQL**，优先用自然语言解释结论与数据要点；只有在用户明确要求时才展示 SQL。
- 当需要理解表结构、索引或性能时，优先使用结构类工具（`describe_table`/`list_indexes`/`explain_sql`）辅助判断，再决定是否需要执行查询。
- 当你发现当前工具不足以完成任务时，可以先调用 `find_skills` 搜索可用扩展，必要时再调用 `install_skill` 安装后继续。

## 重要提醒

- 写 SQL 前应先确认表结构和字段名的正确性，可结合 search_schema 与已有 schema 文档
- 避免盲目猜测字段名，如不确定就优先用 search_schema 查询再继续
- 不要向用户显示 SQL 语句
- 用自然语言描述操作内容"""