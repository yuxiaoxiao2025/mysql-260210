# ReACT 架构改造设计方案

> 设计日期: 2026-03-12
> 状态: 草案，待用户审核

---

## 一、问题背景

### 1.1 当前问题

用户输入"你可以帮我做什么"后，系统返回 `[助手] None`。

**根因分析**：
1. `KnowledgeAgent` 调用 `llm_client.chat_stream()` 返回 generator
2. 但 generator 可能没有产生任何 content chunk（API 调用失败或返回空）
3. `context.execution_result` 最终为 `None`

**深层问题**：
- 当前架构是"一次性 LLM 调用"，没有推理-行动循环
- 过度依赖模板和规则，限制了模型能力的发挥
- 没有工具调用机制，模型无法主动获取信息

### 1.2 MiroFish 的启发

MiroFish 的 `ReportAgent` 采用 **ReACT 模式**：

```
思考 (Reasoning) → 行动 (Acting) → 观察 (Observation) → 循环
```

**核心优势**：
- 模型自主决策何时调用工具
- 多轮推理，逐步解决问题
- 更少的硬编码规则，更灵活的响应

---

## 二、设计目标

### 2.1 核心目标

1. **修复 None 问题**：确保对话模式正常工作
2. **引入 ReACT 模式**：让模型具备工具调用能力
3. **简化硬编码规则**：减少模板依赖，让模型自由推理
4. **支持多模态输入**：未来可支持图片输入（表结构截图）

### 2.2 非目标

- 不改造业务操作流程（query/mutation 保持现有 Agent Pipeline）
- 不引入 Zep Cloud 等外部图谱服务
- 不改变现有的 CLI 交互方式

---

## 三、架构设计

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                           CLI / Web 入口                             │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          Orchestrator                                │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  IntentAgent → 路由决策                                       │   │
│  │     ↓                                                        │   │
│  │  chat/qa → ReACTOrchestrator                                 │   │
│  │  query/mutation → 现有 Agent Pipeline（保持不变）             │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    ▼                           ▼
┌───────────────────────────┐   ┌───────────────────────────────────┐
│   现有 Agent Pipeline     │   │        ReACTOrchestrator          │
│   (query/mutation)        │   │  ┌─────────────────────────────┐  │
│   - RetrievalAgent        │   │  │ Thought: 分析用户意图       │  │
│   - SecurityAgent         │   │  │ Action: 选择工具            │  │
│   - PreviewAgent          │   │  │ Observation: 观察结果       │  │
│   - ExecutionAgent        │   │  │ ... 循环直到完成 ...        │  │
│   (保持不变)               │   │  └─────────────────────────────┘  │
└───────────────────────────┘   │              │                    │
                                │              ▼                    │
                                │    ┌─────────────────────┐       │
                                │    │    ChatToolService   │       │
                                │    │  - search_schema     │       │
                                │    │  - execute_sql       │       │
                                │    │  - list_tables       │       │
                                │    │  - describe_table    │       │
                                │    │  - knowledge_qa      │       │
                                │    └─────────────────────┘       │
                                └───────────────────────────────────┘
```

### 3.2 核心组件

#### 3.2.1 ReACTOrchestrator

负责 ReACT 循环的核心编排器。

```python
class ReACTOrchestrator:
    """ReACT 模式编排器

    实现 Thought → Action → Observation 循环，
    让模型自主决定何时调用工具、何时输出答案。
    """

    def __init__(
        self,
        llm_client: LLMClient,
        tool_service: ChatToolService,
        max_iterations: int = 5
    ):
        self.llm_client = llm_client
        self.tool_service = tool_service
        self.max_iterations = max_iterations

    def process(
        self,
        user_input: str,
        chat_history: list[dict]
    ) -> Generator[dict, None, None]:
        """执行 ReACT 循环，流式输出结果"""
        pass
```

#### 3.2.2 ChatToolService

封装对话场景可用的工具集。

```python
class ChatToolService:
    """对话场景工具服务

    提供模型可调用的工具，让模型自主获取信息。
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        retrieval_pipeline: RetrievalPipeline,
        knowledge_loader: KnowledgeLoader
    ):
        self.db = db_manager
        self.retrieval = retrieval_pipeline
        self.knowledge = knowledge_loader

    # 工具定义
    def search_schema(self, query: str) -> str:
        """搜索相关的数据库表和字段"""
        pass

    def list_tables(self) -> str:
        """列出所有数据库表"""
        pass

    def describe_table(self, table_name: str) -> str:
        """获取表的详细结构"""
        pass

    def execute_sql(self, sql: str) -> str:
        """执行只读SQL查询（带安全限制）"""
        pass

    def list_operations(self) -> str:
        """列出可用的业务操作"""
        pass

    def get_operation_help(self, operation_id: str) -> str:
        """获取操作的详细帮助"""
        pass
```

#### 3.2.3 Tool Definition (for LLM)

工具的 JSON Schema 定义，供模型理解工具能力。

```python
TOOLS_DEFINITION = [
    {
        "type": "function",
        "function": {
            "name": "search_schema",
            "description": "搜索数据库中相关的表和字段。当用户询问数据相关问题时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词或问题描述"
                    }
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
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "describe_table",
            "description": "获取指定表的详细结构信息，包括字段名、类型、注释等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "表名"
                    }
                },
                "required": ["table_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_sql",
            "description": "执行只读SQL查询。只能执行SELECT语句。",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "SELECT语句"
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
            "description": "列出系统支持的所有业务操作，如车牌下发、查询等。",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_operation_help",
            "description": "获取特定业务操作的详细说明和使用方法。",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation_id": {
                        "type": "string",
                        "description": "操作ID，如 plate_distribute"
                    }
                },
                "required": ["operation_id"]
            }
        }
    }
]
```

---

## 四、ReACT 循环设计

### 4.1 系统提示词设计

**核心理念**：简化提示词，让模型自由推理，而不是用模板限制。

```python
REACT_SYSTEM_PROMPT = """你是一个智能数据库助手，帮助用户管理停车数据库。

你有以下工具可用：
- search_schema: 搜索数据库表和字段
- list_tables: 列出所有表
- describe_table: 查看表结构
- execute_sql: 执行只读SQL查询
- list_operations: 列出可用业务操作
- get_operation_help: 查看操作详情

思考过程：
1. 理解用户问题
2. 判断是否需要调用工具获取信息
3. 如果需要，调用合适的工具
4. 基于工具结果回答用户

请用中文回答。回答要简洁、准确。"""
```

### 4.2 ReACT 循环流程

```
┌────────────────────────────────────────────────────────────────┐
│                      ReACT 循环                                 │
│                                                                │
│  ┌──────────────┐                                              │
│  │ 用户输入      │                                              │
│  └──────┬───────┘                                              │
│         ▼                                                      │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐ │
│  │ 构建消息     │ ───▶ │ 调用 LLM     │ ───▶ │ 解析响应     │ │
│  │ (含工具定义) │      │ (支持工具调用)│      │              │ │
│  └──────────────┘      └──────────────┘      └──────┬───────┘ │
│                                                       │        │
│         ┌─────────────────────────────────────────────┼────┐   │
│         ▼                                             ▼    │   │
│  ┌──────────────┐                            ┌──────────────┐ │
│  │ 需要工具调用?│ ──Yes──▶                   │ 直接输出答案 │ │
│  └──────┬───────┘                            └──────────────┘ │
│         │ No                                                   │
│         ▼                                                      │
│  ┌──────────────┐                                              │
│  │ 执行工具     │                                              │
│  │ 获取结果     │                                              │
│  └──────┬───────┘                                              │
│         │                                                      │
│         ▼                                                      │
│  ┌──────────────┐                                              │
│  │ 添加到消息   │                                              │
│  │ 继续循环     │───────────────────────────────┐              │
│  └──────────────┘                               │              │
│                                                 │              │
│         ◀───────────────────────────────────────┘              │
│                   (最多 max_iterations 次)                     │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### 4.3 代码示例

```python
def process(
    self,
    user_input: str,
    chat_history: list[dict]
) -> Generator[dict, None, None]:
    """执行 ReACT 循环，流式输出结果"""

    messages = chat_history.copy()
    messages.append({"role": "user", "content": user_input})

    for iteration in range(self.max_iterations):
        # 调用 LLM（支持工具调用）
        response = self.llm_client.chat_with_tools(
            messages=messages,
            tools=TOOLS_DEFINITION,
            system_prompt=REACT_SYSTEM_PROMPT
        )

        # 检查是否需要工具调用
        if response.tool_calls:
            # 执行工具
            for tool_call in response.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)

                # 执行工具
                tool_result = self.tool_service.execute(tool_name, tool_args)

                # 添加工具调用记录到消息
                messages.append({
                    "role": "assistant",
                    "tool_calls": [tool_call]
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result
                })

            # 继续循环，让 LLM 处理工具结果
            continue

        # 没有工具调用，输出最终答案
        if response.content:
            yield {"type": "content", "content": response.content}
        break

    else:
        # 达到最大迭代次数
        yield {"type": "content", "content": "抱歉，我需要更多的迭代来回答您的问题。"}
```

---

## 五、LLMClient 改造

### 5.1 新增方法

```python
class LLMClient:
    # ... 现有代码 ...

    def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        system_prompt: str = None,
        stream: bool = False
    ) -> ChatResponse:
        """支持工具调用的对话

        Args:
            messages: 对话消息列表
            tools: 工具定义列表
            system_prompt: 系统提示词
            stream: 是否流式输出

        Returns:
            ChatResponse: 包含 content 和 tool_calls 的响应
        """
        pass
```

### 5.2 兼容 Qwen API

Qwen 的工具调用格式与 OpenAI 兼容：

```python
def chat_with_tools(self, messages, tools, system_prompt=None, stream=False):
    """支持工具调用的对话"""

    full_messages = []
    if system_prompt:
        full_messages.append({"role": "system", "content": system_prompt})
    full_messages.extend(messages)

    if self.client:
        # OpenAI 兼容模式
        response = self.client.chat.completions.create(
            model="qwen-plus",
            messages=full_messages,
            tools=tools,
            tool_choice="auto",
            stream=stream
        )
    else:
        # DashScope 原生模式
        api_params = {
            'model': 'qwen-plus',
            'messages': full_messages,
            'tools': tools,
            'result_format': 'message'
        }
        response = Generation.call(**api_params)

    return self._parse_tool_response(response)
```

---

## 六、Orchestrator 改造

### 6.1 修改后的 Orchestrator

```python
class Orchestrator:
    """Orchestrator - 协调 Agent 执行流程"""

    def __init__(
        self,
        intent_agent=None,
        retrieval_agent=None,
        knowledge_agent=None,  # 将被 react_orchestrator 替代
        security_agent=None,
        preview_agent=None,
        execution_agent=None,
        review_agent=None,
        llm_client=None,
        knowledge_loader=None,
        react_orchestrator=None  # 新增
    ):
        # ... 现有 Agent 初始化 ...

        # 新增：ReACT 编排器（用于 chat/qa 意图）
        self.react_orchestrator = react_orchestrator or ReACTOrchestrator(
            llm_client=llm_client,
            tool_service=ChatToolService(
                db_manager=db_manager,  # 需要注入
                retrieval_pipeline=RetrievalPipeline(),
                knowledge_loader=knowledge_loader
            )
        )

    def _handle_conversation(self, context: AgentContext) -> AgentContext:
        """处理对话和知识问答 - 使用 ReACT 模式"""

        # 不再调用 KnowledgeAgent，改用 ReACTOrchestrator
        context.execution_result = self.react_orchestrator.process(
            user_input=context.user_input,
            chat_history=context.chat_history
        )
        context.step_history.append("react_conversation")

        return context
```

---

## 七、实施计划

### 7.1 阶段一：修复 None 问题（紧急）

**目标**：让当前对话模式能正常工作

**任务**：
1. 检查 `chat_stream()` API 调用是否成功
2. 添加错误处理和日志
3. 确保返回有效的 generator

**预计时间**：1-2 小时

### 7.2 阶段二：引入 ReACT 架构

**目标**：实现 ReACT 模式和工具调用

**任务**：
1. 新增 `ChatToolService` 服务
2. 新增 `ReACTOrchestrator` 编排器
3. 修改 `LLMClient` 支持工具调用
4. 修改 `Orchestrator` 路由到 ReACT
5. 添加单元测试和集成测试

**预计时间**：1-2 天

### 7.3 阶段三：优化与扩展

**目标**：优化体验，添加更多工具

**任务**：
1. 优化系统提示词
2. 添加更多工具（如知识库搜索）
3. 支持多模态输入（表结构截图）
4. 性能优化和错误处理

**预计时间**：1 天

---

## 八、风险与对策

### 8.1 风险

| 风险 | 影响 | 对策 |
|------|------|------|
| Qwen 工具调用不稳定 | 模型可能无法正确调用工具 | 添加 fallback 到现有流程 |
| ReACT 循环次数过多 | 响应延迟、token 消耗增加 | 设置合理的 max_iterations |
| 工具执行失败 | 影响用户体验 | 添加错误处理和友好提示 |
| 迁移过程中的回归 | 破坏现有功能 | 保留原有代码路径，通过开关控制 |

### 8.2 回滚策略

```python
# 通过配置开关新旧模式
USE_REACT_MODE = os.getenv("USE_REACT_MODE", "false").lower() == "true"

def _handle_conversation(self, context: AgentContext) -> AgentContext:
    if USE_REACT_MODE:
        return self._handle_conversation_react(context)
    else:
        return self._handle_conversation_legacy(context)
```

---

## 九、验收标准

1. **功能验收**：
   - [ ] 用户输入"你可以帮我做什么"，系统能正常返回有意义的回答
   - [ ] 用户询问数据库相关问题，系统能调用工具获取信息
   - [ ] 多轮对话能正常工作，上下文正确传递

2. **性能验收**：
   - [ ] 简单问题响应时间 < 3 秒
   - [ ] 需要工具调用的问题响应时间 < 10 秒
   - [ ] ReACT 循环次数 ≤ 3 次（典型场景）

3. **质量验收**：
   - [ ] 单元测试覆盖率 ≥ 70%
   - [ ] 集成测试通过
   - [ ] 无明显的 prompt 注入风险

---

## 十、参考资料

- MiroFish Wiki: `docs/MiroFish_Wiki.md`
- OpenAI Function Calling: https://platform.openai.com/docs/guides/function-calling
- Qwen Tool Use: https://help.aliyun.com/zh/dashscope/developer-reference/use-qwen-by-calling-api

---

*本设计文档由 Claude Code 生成*