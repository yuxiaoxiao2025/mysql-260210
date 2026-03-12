# 统一 ReACT 架构设计方案（方案B）

> 设计日期: 2026-03-12
> 状态: 草案，待讨论
> 分支建议: `feature/unified-react-architecture`

---

## 一、设计背景

### 1.1 当前架构的问题

**现状**：两套架构并存

```
chat/qa → KnowledgeAgent → LLM流式输出（有问题，返回None）
query/mutation → Agent Pipeline（6个Agent：Intent→Retrieval→Security→Preview→Review→Execution）
```

**问题**：
1. **架构分裂**：两套流程，维护成本高
2. **KnowledgeAgent 不工作**：返回 None，用户无法进行对话
3. **Agent Pipeline 过于僵化**：固定流程，无法灵活应对不同场景
4. **没有发挥模型能力**：过度依赖模板和规则，限制了 Qwen 的推理能力

### 1.2 方案对比

| 维度 | 方案A（分裂架构） | 方案B（统一ReACT） |
|------|-------------------|-------------------|
| 架构复杂度 | 两套流程 | 一套流程 |
| 灵活性 | 低（硬编码流程） | 高（模型自主决策） |
| 代码量 | 多（6个Agent类） | 少（1个ReACT循环） |
| 扩展性 | 加Agent需改流程 | 加工具即可 |
| 模型能力利用 | 低 | 高 |
| 实施风险 | 低 | 中 |
| 改动范围 | 小 | 大 |

### 1.3 设计目标

1. **统一架构**：所有意图类型使用同一套 ReACT 循环
2. **工具化**：将现有 Agent 能力封装为工具，供模型调用
3. **简化流程**：减少硬编码，让模型自主决策
4. **修复 None 问题**：确保对话模式正常工作
5. **保持安全**：关键操作仍需确认机制

---

## 二、架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                           CLI / Web 入口                             │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        ReACT Orchestrator                            │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │                    ReACT 循环                                  │ │
│  │                                                               │ │
│  │   Thought: 分析用户意图                                       │ │
│  │      ↓                                                        │ │
│  │   Action: 选择并调用工具                                       │ │
│  │      ↓                                                        │ │
│  │   Observation: 观察工具结果                                    │ │
│  │      ↓                                                        │ │
│  │   ... 循环直到完成 ...                                        │ │
│  │      ↓                                                        │ │
│  │   Output: 流式输出最终答案                                     │ │
│  │                                                               │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                  │                                  │
│                                  ▼                                  │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │                      工具层 (Tools)                            │ │
│  │                                                               │ │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐            │ │
│  │  │ 信息查询类  │ │ 业务操作类  │ │ 安全控制类  │            │ │
│  │  ├─────────────┤ ├─────────────┤ ├─────────────┤            │ │
│  │  │search_schema│ │list_ops     │ │check_safety │            │ │
│  │  │list_tables  │ │execute_op   │ │confirm_op   │            │ │
│  │  │describe_tbl │ │preview_op   │ │             │            │ │
│  │  │execute_sql  │ │             │ │             │            │ │
│  │  └─────────────┘ └─────────────┘ └─────────────┘            │ │
│  │                                                               │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                  │                                  │
│                                  ▼                                  │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │                      服务层 (Services)                         │ │
│  │                                                               │ │
│  │  RetrievalPipeline │ OperationExecutor │ DatabaseManager     │ │
│  │  KnowledgeLoader   │ SQLValidator       │ SchemaLoader       │ │
│  │                                                               │ │
│  └───────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 核心变化

**Before（现有架构）**：
```
用户输入 → IntentAgent → RetrievalAgent → SecurityAgent → PreviewAgent → ReviewAgent → ExecutionAgent
          (6个Agent类，硬编码流程)
```

**After（统一ReACT）**：
```
用户输入 → ReACTOrchestrator → 工具调用循环 → 输出
          (1个编排器，模型自主决策调用哪些工具)
```

---

## 三、工具设计

### 3.1 工具分类

| 类别 | 工具名 | 功能 | 对应现有组件 |
|------|--------|------|--------------|
| **信息查询** | search_schema | 搜索表结构 | RetrievalAgent |
| | list_tables | 列出所有表 | - |
| | describe_table | 查看表详情 | - |
| | execute_sql | 执行只读SQL | - |
| | get_knowledge | 查询知识库 | KnowledgeLoader |
| **业务操作** | list_operations | 列出可用操作 | - |
| | get_operation_help | 查看操作详情 | - |
| | preview_operation | 预览操作影响 | PreviewAgent |
| | execute_operation | 执行业务操作 | ExecutionAgent |
| **安全控制** | check_sql_safety | 检查SQL安全性 | SecurityAgent |
| | confirm_operation | 请求用户确认 | ReviewAgent |

### 3.2 工具详细定义

```python
UNIFIED_TOOLS = [
    # ==================== 信息查询类 ====================
    {
        "type": "function",
        "function": {
            "name": "search_schema",
            "description": "搜索数据库中与查询相关的表和字段。用于理解数据结构。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词或问题描述"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_tables",
            "description": "列出数据库中所有的表名。",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "describe_table",
            "description": "获取指定表的详细结构，包括字段名、类型、注释等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "table_name": {"type": "string", "description": "表名"}
                },
                "required": ["table_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_sql",
            "description": "执行只读SELECT查询。仅用于查询数据，不能修改。",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {"type": "string", "description": "SELECT语句"}
                },
                "required": ["sql"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_knowledge",
            "description": "查询业务知识库，获取业务规则、操作流程等信息。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "查询问题"}
                },
                "required": ["query"]
            }
        }
    },

    # ==================== 业务操作类 ====================
    {
        "type": "function",
        "function": {
            "name": "list_operations",
            "description": "列出系统支持的所有业务操作，如车牌下发、查询等。",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_operation_help",
            "description": "获取特定业务操作的详细说明，包括参数、示例等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation_id": {"type": "string", "description": "操作ID"}
                },
                "required": ["operation_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "preview_operation",
            "description": "预览操作执行后的影响，展示将要变更的数据。用于确认操作安全性。",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation_id": {"type": "string", "description": "操作ID"},
                    "params": {"type": "object", "description": "操作参数"}
                },
                "required": ["operation_id", "params"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_operation",
            "description": "执行业务操作。注意：数据修改操作需要先调用confirm_operation获得用户确认。",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation_id": {"type": "string", "description": "操作ID"},
                    "params": {"type": "object", "description": "操作参数"},
                    "confirmed": {"type": "boolean", "description": "是否已获得用户确认（mutation操作必须）"}
                },
                "required": ["operation_id", "params"]
            }
        }
    },

    # ==================== 安全控制类 ====================
    {
        "type": "function",
        "function": {
            "name": "check_sql_safety",
            "description": "检查SQL语句的安全性，识别危险操作。",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {"type": "string", "description": "要检查的SQL语句"}
                },
                "required": ["sql"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "confirm_operation",
            "description": "向用户请求操作确认。当执行数据修改操作前必须调用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "展示给用户的确认信息"}
                },
                "required": ["message"]
            }
        }
    }
]
```

### 3.3 工具实现示例

```python
class UnifiedToolService:
    """统一工具服务 - 封装所有工具的实现"""

    def __init__(
        self,
        db_manager: DatabaseManager,
        retrieval_pipeline: RetrievalPipeline,
        operation_executor: OperationExecutor,
        knowledge_loader: KnowledgeLoader
    ):
        self.db = db_manager
        self.retrieval = retrieval_pipeline
        self.executor = operation_executor
        self.knowledge = knowledge_loader

    def execute(self, tool_name: str, args: dict) -> str:
        """执行工具并返回结果字符串"""
        method = getattr(self, f"_tool_{tool_name}", None)
        if not method:
            return f"错误：未知工具 {tool_name}"
        try:
            return method(**args)
        except Exception as e:
            return f"工具执行失败：{str(e)}"

    # ==================== 信息查询类 ====================

    def _tool_search_schema(self, query: str) -> str:
        """搜索表结构"""
        result = self.retrieval.search(query, top_k=5)
        if not result.matches:
            return "未找到相关的表。"

        lines = ["找到以下相关表："]
        for match in result.matches:
            lines.append(f"- {match.table_name}: {match.description or '无描述'}")
        return "\n".join(lines)

    def _tool_list_tables(self) -> str:
        """列出所有表"""
        tables = self.db.get_all_tables()
        return "数据库中的表：\n" + "\n".join(f"- {t}" for t in tables[:20])

    def _tool_describe_table(self, table_name: str) -> str:
        """查看表结构"""
        schema = self.db.get_table_schema(table_name)
        lines = [f"表 {table_name} 的结构："]
        for col in schema:
            lines.append(f"- {col['name']}: {col['type']} ({col['comment'] or '无注释'})")
        return "\n".join(lines)

    def _tool_execute_sql(self, sql: str) -> str:
        """执行只读SQL"""
        # 安全检查
        if not sql.strip().upper().startswith("SELECT"):
            return "错误：只能执行SELECT语句。"

        df = self.db.execute_query(sql)
        if df.empty:
            return "查询结果为空。"

        return f"查询返回 {len(df)} 行数据：\n" + df.head(10).to_string()

    def _tool_get_knowledge(self, query: str) -> str:
        """查询知识库"""
        operations = self.knowledge.get_all_operations()
        # 简单搜索
        matches = [op for op in operations if query.lower() in op.name.lower() or query.lower() in op.description.lower()]
        if not matches:
            return "知识库中未找到相关信息。"

        lines = ["知识库中的相关操作："]
        for op in matches[:5]:
            lines.append(f"- {op.name}: {op.description}")
        return "\n".join(lines)

    # ==================== 业务操作类 ====================

    def _tool_list_operations(self) -> str:
        """列出所有操作"""
        operations = self.knowledge.get_all_operations()
        lines = ["系统支持的业务操作："]
        for op in operations:
            lines.append(f"- {op.id}: {op.name} - {op.description}")
        return "\n".join(lines)

    def _tool_get_operation_help(self, operation_id: str) -> str:
        """获取操作帮助"""
        op = self.knowledge.get_operation(operation_id)
        if not op:
            return f"未找到操作：{operation_id}"

        lines = [f"操作：{op.name}", f"ID：{op.id}", f"描述：{op.description}"]
        if op.params:
            lines.append("参数：")
            for p in op.params:
                lines.append(f"  - {p.name}: {p.description}")
        return "\n".join(lines)

    def _tool_preview_operation(self, operation_id: str, params: dict) -> str:
        """预览操作"""
        result = self.executor.execute_operation(operation_id, params, preview_only=True)
        if not result.success:
            return f"预览失败：{result.error}"

        lines = ["操作预览："]
        if result.previews:
            for preview in result.previews:
                lines.append(f"- 影响表：{preview.table_name}")
                lines.append(f"  变更行数：{preview.affected_rows}")
        return "\n".join(lines)

    def _tool_execute_operation(self, operation_id: str, params: dict, confirmed: bool = False) -> str:
        """执行操作"""
        op = self.knowledge.get_operation(operation_id)
        if not op:
            return f"未找到操作：{operation_id}"

        # 检查是否需要确认
        if op.is_mutation() and not confirmed:
            return "错误：数据修改操作需要先调用 confirm_operation 获得用户确认。"

        result = self.executor.execute_operation(
            operation_id, params, preview_only=False, auto_commit=True
        )

        if result.success:
            return f"操作成功：{result.summary}"
        else:
            return f"操作失败：{result.error}"

    # ==================== 安全控制类 ====================

    def _tool_check_sql_safety(self, sql: str) -> str:
        """检查SQL安全性"""
        from src.sql_safety import validate_direct_query_sql
        is_safe, reason = validate_direct_query_sql(sql)
        if is_safe:
            return "SQL安全检查通过。"
        else:
            return f"SQL安全检查未通过：{reason}"

    def _tool_confirm_operation(self, message: str) -> str:
        """请求用户确认"""
        # 返回特殊标记，由 Orchestrator 处理用户交互
        return f"__NEED_CONFIRM__: {message}"
```

---

## 四、ReACT Orchestrator 设计

### 4.1 核心类

```python
class UnifiedReACTOrchestrator:
    """统一 ReACT 编排器

    所有用户输入都通过 ReACT 循环处理：
    - Thought: 模型分析用户意图
    - Action: 模型选择调用工具
    - Observation: 模型观察工具结果
    - 循环直到模型输出最终答案
    """

    def __init__(
        self,
        llm_client: LLMClient,
        tool_service: UnifiedToolService,
        max_iterations: int = 10
    ):
        self.llm = llm_client
        self.tools = tool_service
        self.max_iterations = max_iterations

    def process(
        self,
        user_input: str,
        chat_history: list[dict] | None = None
    ) -> Generator[dict, None, None]:
        """处理用户输入，流式输出结果

        Yields:
            {"type": "thinking", "content": "..."}  # 思考过程
            {"type": "action", "tool": "...", "args": {...}}  # 工具调用
            {"type": "observation", "content": "..."}  # 工具结果
            {"type": "content", "content": "..."}  # 最终输出
            {"type": "confirm_required", "message": "..."}  # 需要用户确认
        """
        pass

    def continue_with_confirmation(
        self,
        chat_history: list[dict],
        confirmed: bool
    ) -> Generator[dict, None, None]:
        """用户确认后继续执行"""
        pass
```

### 4.2 ReACT 循环流程

```
用户输入 "下发车牌 沪ABC1234 到 国际商务中心"
        │
        ▼
┌───────────────────────────────────────────────────────────────┐
│ Iteration 1                                                    │
│                                                               │
│ Thought: 用户要执行车牌下发操作，我需要先了解这个操作。       │
│ Action: get_operation_help("plate_distribute")               │
│ Observation: 操作需要 plate 和 location 参数...              │
└───────────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────────┐
│ Iteration 2                                                    │
│                                                               │
│ Thought: 参数已从用户输入提取，需要预览操作影响。             │
│ Action: preview_operation("plate_distribute", {...})         │
│ Observation: 将影响 1 行数据，车牌状态变为"已下发"...        │
└───────────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────────┐
│ Iteration 3                                                    │
│                                                               │
│ Thought: 这是数据修改操作，需要请求用户确认。                 │
│ Action: confirm_operation("确认将车牌 沪ABC1234 下发到...")  │
│ Observation: __NEED_CONFIRM__                                 │
└───────────────────────────────────────────────────────────────┘
        │
        ▼
   [等待用户确认]
        │
        ▼
┌───────────────────────────────────────────────────────────────┐
│ Iteration 4 (用户确认后继续)                                   │
│                                                               │
│ Thought: 用户已确认，执行操作。                               │
│ Action: execute_operation("plate_distribute", {...}, confirmed=True)
│ Observation: 操作成功，已更新 1 条记录。                     │
└───────────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────────┐
│ Final Output                                                   │
│                                                               │
│ "车牌 沪ABC1234 已成功下发到 国际商务中心。"                  │
└───────────────────────────────────────────────────────────────┘
```

### 4.3 用户确认机制

**问题**：ReACT 循环是同步的，如何处理用户确认？

**方案**：中断-恢复模式

```python
def process(self, user_input, chat_history=None):
    messages = chat_history or []
    messages.append({"role": "user", "content": user_input})

    for iteration in range(self.max_iterations):
        response = self.llm.chat_with_tools(messages, tools=UNIFIED_TOOLS)

        if response.tool_calls:
            for tool_call in response.tool_calls:
                result = self.tools.execute(tool_call.function.name, args)

                # 检查是否需要用户确认
                if result.startswith("__NEED_CONFIRM__"):
                    # 中断循环，返回确认请求
                    yield {
                        "type": "confirm_required",
                        "message": result.replace("__NEED_CONFIRM__:", "").strip(),
                        "state": {
                            "messages": messages,
                            "iteration": iteration
                        }
                    }
                    return  # 中断，等待用户确认

                # 记录工具调用
                messages.append({"role": "assistant", "tool_calls": [tool_call]})
                messages.append({"role": "tool", "content": result})

                yield {"type": "observation", "content": result}

        else:
            # 没有工具调用，输出最终答案
            yield {"type": "content", "content": response.content}
            return

def continue_with_confirmation(self, state, confirmed):
    """用户确认后继续"""
    messages = state["messages"]

    # 添加确认结果
    if confirmed:
        messages.append({"role": "user", "content": "用户确认执行"})
    else:
        messages.append({"role": "user", "content": "用户取消操作"})
        yield {"type": "content", "content": "操作已取消。"}
        return

    # 继续循环
    # ...
```

---

## 五、系统提示词设计

### 5.1 核心理念

**简化规则，让模型自由推理**，而不是用复杂模板限制。

### 5.2 提示词设计

```python
UNIFIED_SYSTEM_PROMPT = """你是智能停车数据库助手，帮助用户管理停车数据。

## 你的能力

你可以调用以下工具获取信息和执行操作：

**信息查询**：
- search_schema: 搜索数据库表和字段
- list_tables: 列出所有表
- describe_table: 查看表结构
- execute_sql: 执行只读查询
- get_knowledge: 查询业务知识库

**业务操作**：
- list_operations: 查看可用的业务操作
- get_operation_help: 查看操作详情
- preview_operation: 预览操作影响
- execute_operation: 执行操作

**安全控制**：
- check_sql_safety: 检查SQL安全性
- confirm_operation: 请求用户确认（数据修改操作必须调用）

## 工作流程

1. 理解用户问题或需求
2. 判断需要哪些工具来完成任务
3. 调用工具获取信息或执行操作
4. 基于工具结果回答用户或继续调用工具

## 重要规则

- 数据修改操作（mutation）必须先调用 preview_operation 预览，再调用 confirm_operation 请求确认
- 用户确认后才能调用 execute_operation 并设置 confirmed=true
- 用中文回答，简洁准确
- 如果不确定用户意图，先问清楚再操作"""
```

---

## 六、与现有组件的关系

### 6.1 复用现有服务

| 现有组件 | 新架构中的角色 |
|----------|----------------|
| `DatabaseManager` | 工具层直接调用 |
| `RetrievalPipeline` | `search_schema` 工具调用 |
| `OperationExecutor` | `execute_operation` 工具调用 |
| `KnowledgeLoader` | `get_knowledge` 工具调用 |
| `SQLValidator` | `check_sql_safety` 工具调用 |
| `LLMClient` | 增加 `chat_with_tools` 方法 |

### 6.2 废弃的组件

| 现有 Agent | 处理方式 |
|------------|----------|
| `IntentAgent` | 废弃，意图识别由 ReACT 循环处理 |
| `RetrievalAgent` | 废弃，能力封装到 `search_schema` 工具 |
| `SecurityAgent` | 废弃，能力封装到 `check_sql_safety` 工具 |
| `PreviewAgent` | 废弃，能力封装到 `preview_operation` 工具 |
| `ReviewAgent` | 废弃，能力封装到 `confirm_operation` 工具 |
| `ExecutionAgent` | 废弃，能力封装到 `execute_operation` 工具 |
| `KnowledgeAgent` | 废弃，由 ReACT 循环直接处理 |

### 6.3 目录结构变化

```
src/
├── agents/                    # 简化
│   ├── __init__.py
│   ├── react_orchestrator.py  # 新增：ReACT 编排器
│   └── tool_service.py        # 新增：统一工具服务
│
├── services/                  # 保持不变
│   ├── db_manager.py
│   ├── retrieval_pipeline.py
│   ├── operation_executor.py
│   └── ...
│
└── llm_client.py              # 增强：添加工具调用支持
```

---

## 七、CLI 改造

### 7.1 main.py 改造

```python
# 原来的复杂路由逻辑简化为：

if user_input.lower() == 'chat':
    # 进入对话模式
    chat_history = []
    while True:
        chat_input = input("\n[对话] > ")

        # 统一使用 ReACT Orchestrator
        for chunk in react_orchestrator.process(chat_input, chat_history):
            if chunk["type"] == "confirm_required":
                print(f"\n[确认] {chunk['message']}")
                confirm = input("确认？(y/n) > ")
                # 继续执行
                for result in react_orchestrator.continue_with_confirmation(
                    chunk["state"], confirmed=(confirm == "y")
                ):
                    print(result["content"])

            elif chunk["type"] == "content":
                print(f"\n[助手] {chunk['content']}")
                chat_history.append({"role": "assistant", "content": chunk["content"]})

        chat_history.append({"role": "user", "content": chat_input})
```

---

## 八、实施计划

### 8.1 分支创建

```bash
git checkout -b feature/unified-react-architecture
```

### 8.2 阶段划分

| 阶段 | 任务 | 预计时间 |
|------|------|----------|
| **P0: 基础设施** | LLMClient 添加工具调用支持 | 0.5天 |
| **P1: 工具层** | 实现 UnifiedToolService | 1天 |
| **P2: 编排器** | 实现 UnifiedReACTOrchestrator | 1天 |
| **P3: CLI改造** | 改造 main.py 使用新架构 | 0.5天 |
| **P4: 测试** | 单元测试 + 集成测试 | 1天 |
| **P5: 文档** | 更新 CLAUDE.md 和 README | 0.5天 |

### 8.3 验收标准

- [ ] 用户输入"你可以帮我做什么"，系统能正常返回有意义的回答
- [ ] 用户询问数据库问题，系统能调用工具获取信息
- [ ] 用户执行业务操作，系统能正确预览、确认、执行
- [ ] 多轮对话正常工作
- [ ] 单元测试覆盖率 ≥ 70%

---

## 九、风险与对策

### 9.1 风险列表

| 风险 | 概率 | 影响 | 对策 |
|------|------|------|------|
| Qwen 工具调用不稳定 | 中 | 高 | 添加重试机制和降级方案 |
| ReACT 循环次数过多 | 中 | 中 | 设置合理的 max_iterations |
| 模型无法正确判断何时确认 | 低 | 高 | 在提示词中明确规则 |
| 迁移过程中破坏现有功能 | 中 | 高 | 独立分支，充分测试 |

### 9.2 回滚策略

保留原有 Agent 代码，通过开关控制：

```python
USE_REACT_ARCHITECTURE = os.getenv("USE_REACT", "false").lower() == "true"
```

---

## 十、待讨论问题

1. **工具调用次数限制**：max_iterations 设为多少合适？（建议 10）

2. **确认机制细节**：
   - 是否所有 mutation 都需要确认？
   - 批量操作如何确认？

3. **错误处理**：
   - 工具执行失败后，模型应该怎么处理？
   - 是否需要重试机制？

4. **性能考量**：
   - ReACT 循环可能比现有流程慢，是否可接受？
   - 是否需要流式输出中间过程？

5. **多模态扩展**：
   - 未来是否支持图片输入（表结构截图）？
   - 如何与工具调用结合？

---

*本设计文档由 Claude Code 生成，待用户审核讨论*