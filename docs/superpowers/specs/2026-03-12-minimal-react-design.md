# 极简 ReACT 架构设计方案

> 设计日期: 2026-03-12
> 状态: 草案，待讨论
> 分支建议: `feature/minimal-react-architecture`

---

## 一、核心洞察

### 1.1 现有架构的问题

| 问题 | 现状 | 本质 |
|------|------|------|
| 启动问一堆问题 | "before_order这个表是干什么的" | 模型应该自己知道 |
| 概念映射系统 | 17个概念，人工维护 | Qwen 已经懂这些 |
| 6个Agent Pipeline | Intent→Retrieval→Security→Preview→Review→Execution | 过度设计 |
| 返回None | 对话模式完全不可用 | 错误处理缺失 |

### 1.2 核心原则

**Qwen 已经知道什么是数据库、什么是表、什么是SQL。**

我们不需要：
- ❌ 概念映射系统（教模型已经知道的东西）
- ❌ 启动向导（问一堆问题）
- ❌ 6个Agent（过度设计）
- ❌ 复杂的系统提示（限制模型）

我们只需要：
- ✅ 让模型能访问数据库
- ✅ 让模型能访问检索系统
- ✅ 让模型自己推理和执行

---

## 二、目标

### 2.1 项目核心目的

> 通过自然语言，操作数据库：
> - 查询：这辆车在XX园区停了多久？
> - 导出：导出车牌表
> - 下发：把XX车辆下发到全部园区/某个园区
> - CRUD：新增、更新、删除记录

### 2.2 设计目标

1. **极简**：删除所有不必要的组件
2. **工具化**：让模型能调用工具
3. **自主决策**：让模型自己决定调用什么工具
4. **快速响应**：减少中间环节

---

## 三、极简架构

### 3.1 架构图

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
│  │   Thought: 分析用户意图，决定调用什么工具                       │ │
│  │      ↓                                                        │ │
│  │   Action: 调用工具                                             │ │
│  │      ↓                                                        │ │
│  │   Observation: 获取工具结果                                    │ │
│  │      ↓                                                        │ │
│  │   ... 循环直到完成 ...                                        │ │
│  │      ↓                                                        │ │
│  │   Output: 返回结果给用户                                       │ │
│  │                                                               │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                  │                                  │
│                                  ▼                                  │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │                      工具层 (4个工具)                          │ │
│  │                                                               │ │
│  │  search_schema(query)    → 搜索相关表和字段                   │ │
│  │  execute_sql(sql)        → 执行SQL（只读或需确认）             │ │
│  │  execute_operation(...)  → 执行业务操作                       │ │
│  │  list_operations()       → 列出可用操作                       │ │
│  │                                                               │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                  │                                  │
│                                  ▼                                  │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │                      服务层 (已存在)                           │ │
│  │                                                               │ │
│  │  RetrievalPipeline  │  OperationExecutor  │  DatabaseManager  │ │
│  │  (向量索引+重排序)   │  (业务操作执行)     │  (数据库连接)      │ │
│  │                                                               │ │
│  └───────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 与现有架构对比

| 维度 | 现有架构 | 极简架构 |
|------|----------|----------|
| **Agent数量** | 6个（Intent, Retrieval, Security, Preview, Review, Execution） | 0个 |
| **编排器** | Orchestrator（复杂路由） | ReACTOrchestrator（简单循环） |
| **工具数量** | 无 | 4个 |
| **概念映射** | 17个概念，ConceptStore | 删除 |
| **启动向导** | StartupWizard 问一堆问题 | 删除 |
| **系统提示** | 复杂模板 | 简单描述 |
| **意图识别** | IntentAgent + IntentRecognizer | 模型自己判断 |

---

## 四、工具设计

### 4.1 只需要4个工具

```python
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_schema",
            "description": "搜索数据库中与查询相关的表和字段。当你需要了解数据结构时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_sql",
            "description": "执行SQL语句。SELECT语句直接执行，UPDATE/INSERT/DELETE需要先确认。",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {"type": "string", "description": "SQL语句"},
                    "confirmed": {"type": "boolean", "description": "是否已确认（修改操作必须）"}
                },
                "required": ["sql"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_operation",
            "description": "执行预定义的业务操作，如车牌下发、导出等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation_id": {"type": "string", "description": "操作ID"},
                    "params": {"type": "object", "description": "操作参数"}
                },
                "required": ["operation_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_operations",
            "description": "列出所有可用的业务操作。",
            "parameters": {"type": "object", "properties": {}}
        }
    }
]
```

### 4.2 工具实现

```python
class ToolService:
    """极简工具服务"""

    def __init__(self, db, retrieval_pipeline, operation_executor, knowledge_loader):
        self.db = db
        self.retrieval = retrieval_pipeline
        self.executor = operation_executor
        self.knowledge = knowledge_loader

    def execute(self, tool_name: str, args: dict) -> str:
        """执行工具"""
        return getattr(self, f"tool_{tool_name}", self.tool_unknown)(**args)

    def tool_search_schema(self, query: str) -> str:
        """搜索表结构"""
        result = self.retrieval.search(query, top_k=5)
        if not result.matches:
            return "未找到相关的表。"

        lines = ["找到以下相关表："]
        for match in result.matches:
            lines.append(f"- {match.table_name}")
            if match.description:
                lines.append(f"  说明：{match.description}")
        return "\n".join(lines)

    def tool_execute_sql(self, sql: str, confirmed: bool = False) -> str:
        """执行SQL"""
        sql_upper = sql.strip().upper()

        # SELECT 直接执行
        if sql_upper.startswith("SELECT"):
            df = self.db.execute_query(sql)
            if df.empty:
                return "查询结果为空。"
            return f"查询返回 {len(df)} 行：\n" + df.head(10).to_string()

        # 修改操作需要确认
        if not confirmed:
            return f"__NEED_CONFIRM__: 确认执行以下SQL？\n{sql}"

        # 执行修改
        try:
            affected = self.db.execute_update(sql)
            return f"执行成功，影响 {affected} 行。"
        except Exception as e:
            return f"执行失败：{e}"

    def tool_execute_operation(self, operation_id: str, params: dict = None) -> str:
        """执行业务操作"""
        params = params or {}
        result = self.executor.execute_operation(operation_id, params)
        if result.success:
            return f"操作成功：{result.summary}"
        return f"操作失败：{result.error}"

    def tool_list_operations(self) -> str:
        """列出操作"""
        ops = self.knowledge.get_all_operations()
        lines = ["可用的业务操作："]
        for op in ops:
            lines.append(f"- {op.id}: {op.name}")
        return "\n".join(lines)

    def tool_unknown(self, **kwargs) -> str:
        return "未知工具"
```

---

## 五、ReACT Orchestrator 设计

### 5.1 核心类

```python
class ReACTOrchestrator:
    """极简 ReACT 编排器"""

    def __init__(self, llm_client, tool_service, max_iterations=5):
        self.llm = llm_client
        self.tools = tool_service
        self.max_iterations = max_iterations

    def process(self, user_input: str, chat_history: list = None) -> str:
        """处理用户输入"""
        messages = chat_history or []
        messages.append({"role": "user", "content": user_input})

        for _ in range(self.max_iterations):
            # 调用模型（支持工具调用）
            response = self.llm.chat_with_tools(
                messages=messages,
                tools=TOOLS,
                system_prompt=SYSTEM_PROMPT
            )

            # 检查是否需要工具调用
            if response.tool_calls:
                for tool_call in response.tool_calls:
                    # 执行工具
                    result = self.tools.execute(
                        tool_call.function.name,
                        json.loads(tool_call.function.arguments)
                    )

                    # 处理确认请求
                    if result.startswith("__NEED_CONFIRM__"):
                        return result.replace("__NEED_CONFIRM__:", "").strip()

                    # 记录到消息历史
                    messages.append({"role": "assistant", "tool_calls": [tool_call]})
                    messages.append({"role": "tool", "content": result})

                # 继续循环
                continue

            # 没有工具调用，返回最终答案
            return response.content

        return "抱歉，我需要更多时间来处理您的请求。"

    def confirm_and_continue(self, chat_history: list, confirmed: bool) -> str:
        """用户确认后继续"""
        if confirmed:
            chat_history.append({"role": "user", "content": "确认执行"})
        else:
            return "操作已取消。"
        # 继续处理...
```

### 5.2 系统提示（极简）

```python
SYSTEM_PROMPT = """你是智能停车数据库助手。

你可以调用以下工具：
- search_schema: 搜索数据库表结构
- execute_sql: 执行SQL语句
- execute_operation: 执行业务操作
- list_operations: 查看可用操作

工作方式：
1. 理解用户需求
2. 调用合适的工具获取信息或执行操作
3. 返回结果

注意事项：
- 执行数据修改操作前，先询问用户确认
- 用中文回答，简洁准确"""
```

**就这么简单！** 不需要复杂的模板和规则。

---

## 六、删除的组件

### 6.1 完全删除

| 组件 | 文件 | 原因 |
|------|------|------|
| 概念映射系统 | `src/memory/concept_store.py` | 模型已经懂这些 |
| 概念识别器 | `src/dialogue/concept_recognize.py` | 不需要 |
| 启动向导 | `src/dialogue/startup_wizard.py` | 不需要问一堆问题 |
| 问题生成器 | `src/dialogue/question_generator.py` | 不需要 |
| 对话引擎 | `src/dialogue/dialogue_engine.py` | 已废弃 |
| IntentAgent | `src/agents/impl/intent_agent.py` | 模型自己判断意图 |
| RetrievalAgent | `src/agents/impl/retrieval_agent.py` | 封装到工具 |
| SecurityAgent | `src/agents/impl/security_agent.py` | 封装到工具 |
| PreviewAgent | `src/agents/impl/preview_agent.py` | 封装到工具 |
| ReviewAgent | `src/agents/impl/review_agent.py` | 封装到工具 |
| ExecutionAgent | `src/agents/impl/execution_agent.py` | 封装到工具 |
| KnowledgeAgent | `src/agents/impl/knowledge_agent.py` | 不需要 |
| 旧 Orchestrator | `src/agents/orchestrator.py` | 替换 |

### 6.2 保留的组件

| 组件 | 文件 | 作用 |
|------|------|------|
| RetrievalPipeline | `src/metadata/retrieval_pipeline.py` | 向量搜索+重排序 |
| DatabaseManager | `src/db_manager.py` | 数据库操作 |
| OperationExecutor | `src/executor/operation_executor.py` | 业务操作执行 |
| KnowledgeLoader | `src/knowledge/knowledge_loader.py` | 操作模板加载 |
| LLMClient | `src/llm_client.py` | 增加 `chat_with_tools` |

---

## 七、目录结构变化

### 7.1 现有结构

```
src/
├── agents/                    # 6个Agent + Orchestrator（删除）
│   ├── impl/
│   │   ├── intent_agent.py
│   │   ├── retrieval_agent.py
│   │   ├── security_agent.py
│   │   ├── preview_agent.py
│   │   ├── review_agent.py
│   │   ├── execution_agent.py
│   │   └── knowledge_agent.py
│   ├── orchestrator.py
│   └── ...
├── dialogue/                  # 对话系统（删除）
│   ├── concept_recognize.py
│   ├── startup_wizard.py
│   ├── question_generator.py
│   └── dialogue_engine.py
├── memory/                    # 记忆系统（删除概念存储）
│   ├── concept_store.py
│   └── ...
└── ...
```

### 7.2 新结构

```
src/
├── react/                     # 新增：ReACT 核心
│   ├── __init__.py
│   ├── orchestrator.py        # ReACT 编排器
│   ├── tools.py               # 工具定义
│   └── tool_service.py        # 工具实现
├── metadata/                  # 保留
│   ├── retrieval_pipeline.py  # 向量搜索+重排序
│   └── ...
├── executor/                  # 保留
│   └── operation_executor.py  # 业务操作执行
├── knowledge/                 # 保留
│   └── knowledge_loader.py    # 操作模板加载
├── llm_client.py              # 增强：添加工具调用支持
└── db_manager.py              # 保留
```

---

## 八、main.py 改造

### 8.1 现有代码（复杂）

```python
# 初始化一堆组件
concept_store = ConceptStoreService()
context_memory = ContextMemoryService()
wizard = StartupWizard(concept_store, db_manager=db)
# ... 启动向导问一堆问题 ...
orchestrator = Orchestrator(llm_client=llm, knowledge_loader=knowledge_loader, ...)
orchestrator.intent_agent.concept_store = concept_store
orchestrator.intent_agent.concept_recognizer = ConceptRecognizer(concept_store)
# ... 复杂的 chat 模式处理 ...
```

### 8.2 新代码（极简）

```python
# 初始化核心组件
tool_service = ToolService(db, RetrievalPipeline(), operation_executor, knowledge_loader)
react = ReACTOrchestrator(llm, tool_service)

# chat 模式
if user_input.lower() == 'chat':
    chat_history = []
    while True:
        chat_input = input("\n[对话] > ")
        if chat_input.lower() in ['exit', 'quit']:
            break

        result = react.process(chat_input, chat_history)

        # 处理确认请求
        if result.startswith("确认执行"):
            print(f"\n[助手] {result}")
            confirm = input("确认？(y/n) > ")
            if confirm == 'y':
                result = react.confirm_and_continue(chat_history, True)

        print(f"\n[助手] {result}")
        chat_history.append({"role": "user", "content": chat_input})
        chat_history.append({"role": "assistant", "content": result})
```

---

## 九、实施计划

### 9.1 分支创建

```bash
git checkout -b feature/minimal-react-architecture
```

### 9.2 阶段划分

| 阶段 | 任务 | 预计时间 |
|------|------|----------|
| **P0: 修复 None** | 按 `2026-03-12-fix-none-issue.md` 修复 | 1小时 |
| **P1: 新增 ReACT** | 创建 `src/react/` 模块 | 2小时 |
| **P2: 工具实现** | 实现 4 个工具 | 2小时 |
| **P3: LLMClient 改造** | 添加 `chat_with_tools` | 1小时 |
| **P4: main.py 改造** | 使用新架构 | 1小时 |
| **P5: 删除旧代码** | 删除不需要的组件 | 0.5小时 |
| **P6: 测试** | 端到端测试 | 1小时 |
| **总计** | | **~8.5小时** |

### 9.3 验收标准

- [ ] 启动不再问一堆问题
- [ ] 输入"查询车牌 沪A12345"，能正常返回结果
- [ ] 输入"下发车牌 沪A12345 到 国际商务中心"，能正常执行
- [ ] 输入"知识库有多大"，能正常回答
- [ ] 无用组件已删除

---

## 十、风险与对策

| 风险 | 对策 |
|------|------|
| Qwen 工具调用不稳定 | 添加重试机制，fallback 到简单回复 |
| 模型不调用工具 | 在系统提示中强调工具使用 |
| 删除代码影响现有功能 | 分支开发，充分测试后合并 |

---

## 十一、与 MiroFish 的对比

| 维度 | MiroFish | 本项目 |
|------|----------|--------|
| **目的** | 多智能体模拟预测 | 数据库操作助手 |
| **ReACT** | ReportAgent | ReACTOrchestrator |
| **工具** | InsightForge, PanoramaSearch 等 | search_schema, execute_sql 等 |
| **知识图谱** | Zep Cloud | 不需要（数据库本身就是结构化数据） |
| **多智能体** | OASIS | 不需要 |
| **复杂度** | 高 | 极简 |

**借鉴点**：
- ReACT 思考模式 ✅
- 工具调用机制 ✅
- 简洁系统提示 ✅

**不需要借鉴**：
- Zep Cloud 知识图谱 ❌
- OASIS 多智能体 ❌
- ReportAgent 报告生成 ❌

---

*本设计文档由 Claude Code 生成，待用户审核讨论*