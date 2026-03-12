# MVP ReACT 验证实施计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 验证 Qwen 工具调用稳定性，实现基本的查询和操作流程

**Architecture:** 简化版 ReACT 架构，无学习记忆功能。模型通过工具调用执行数据库操作

**Tech Stack:** Python 3.11+, Qwen API (OpenAI 兼容), ChromaDB, Pydantic

---

## File Structure

```
src/
├── react/                          # 新增模块
│   ├── __init__.py                 # 模块入口
│   ├── orchestrator.py             # ReACT 编排器
│   ├── tools.py                    # 工具定义
│   └── tool_service.py             # 工具实现
├── llm_client.py                   # 修改：添加工具调用支持
└── main.py                         # 修改：简化 chat 模式

tests/
├── unit/
│   └── react/                      # 新增测试目录
│       ├── test_orchestrator.py
│       └── test_tool_service.py
└── integration/
    └── test_mvp_flow.py            # 端到端测试
```

---

## Chunk 1: 修复 None 问题

### Task 1: 修复 LLMClient.chat_stream()

**Files:**
- Modify: `src/llm_client.py:834-908`

- [ ] **Step 1: 添加前置检查和错误处理**

在 `chat_stream` 方法开头添加前置检查：

```python
def chat_stream(self, messages: list[dict], enable_thinking: bool = False):
    """
    Stream chat response with thinking support

    Args:
        messages: List of message dicts
        enable_thinking: Whether to enable thinking mode

    Yields:
        Dict with type ('thinking', 'content', 'error', 'usage') and content
    """
    # 前置检查
    if not messages:
        logger.error("chat_stream: messages is empty")
        yield {"type": "error", "content": "消息列表为空"}
        return

    if not self.api_key:
        logger.error("chat_stream: API key not configured")
        yield {"type": "error", "content": "API 密钥未配置，请设置 DASHSCOPE_API_KEY 环境变量"}
        return
```

- [ ] **Step 2: 添加内容跟踪和默认回复**

在 `for chunk in response:` 循环前添加 `has_content = False`，循环后检查：

```python
        # 跟踪是否有实际输出
        has_content = False

        for chunk in response:
            choice = self._extract_stream_choice(chunk)
            if choice:
                thinking = getattr(choice, "reasoning_content", None)
                content = getattr(choice, "content", None)
                if thinking:
                    has_content = True
                    yield {"type": "thinking", "content": str(thinking)}
                if content:
                    has_content = True
                    yield {"type": "content", "content": str(content)}
            # ... existing usage code ...

        # 检查是否有输出
        if not has_content:
            logger.warning("chat_stream: No content generated from LLM")
            yield {"type": "content", "content": "抱歉，我暂时无法回答这个问题。请稍后再试。"}
```

- [ ] **Step 3: 添加异常处理**

在 `except Exception as e:` 中返回 error chunk：

```python
    except Exception as e:
        logger.error(f"chat_stream failed: {e}", exc_info=True)
        yield {"type": "error", "content": f"对话服务暂时不可用：{str(e)}"}
```

- [ ] **Step 4: 验证修复**

运行现有测试确认不破坏现有功能：
```bash
pytest tests/ -v -k "llm" --no-header
```

- [ ] **Step 5: Commit**

```bash
git add src/llm_client.py
git commit -m "fix(llm): 添加 chat_stream 错误处理和默认回复"
```

---

### Task 2: 修复 main.py chat 模式

**Files:**
- Modify: `main.py:320-346`

- [ ] **Step 1: 添加 execution_result None 检查**

找到 `# 处理流式输出` 注释，修改条件判断：

```python
                        # 处理流式输出
                        assistant_response = ""

                        # 检查 execution_result 是否有效
                        if context.execution_result is None:
                            assistant_response = "抱歉，处理您的请求时出现问题，请稍后再试。"
                            print(f"\n[助手] {assistant_response}")

                        elif isinstance(context.execution_result, types.GeneratorType):
```

- [ ] **Step 2: 添加 error chunk 处理**

在 `for chunk in context.execution_result:` 循环中添加：

```python
                            elif chunk.get("type") == "error":
                                # 处理错误 chunk
                                error_msg = chunk.get("content", "未知错误")
                                print(f"[错误] {error_msg}")
                                assistant_response = f"[错误] {error_msg}"
                                has_content = True
```

- [ ] **Step 3: 添加字符串类型处理**

在 `else:` 分支中添加字符串类型处理：

```python
                        elif isinstance(context.execution_result, str):
                            # 字符串结果（错误消息）
                            assistant_response = context.execution_result
                            print(f"\n[助手] {assistant_response}")

                        else:
                            # 其他类型结果
                            assistant_response = str(context.execution_result) if context.execution_result else "处理完成"
                            print(f"\n[助手] {assistant_response}")
```

- [ ] **Step 4: 手动测试**

```bash
python main.py
# 输入 chat，然后输入 "你好"
# 预期：返回有意义的回复，不是 None
```

- [ ] **Step 5: Commit**

```bash
git add main.py
git commit -m "fix(main): 添加 chat 模式错误处理，修复 None 问题"
```

---

## Chunk 2: LLMClient 工具调用支持

### Task 3: 添加 chat_with_tools 方法

**Files:**
- Modify: `src/llm_client.py`
- Create: `src/llm_tool_models.py`

- [ ] **Step 1: 创建工具调用响应模型**

创建 `src/llm_tool_models.py`:

```python
"""LLM 工具调用相关模型"""
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ToolCall:
    """工具调用"""
    id: str
    name: str
    arguments: str  # JSON string

    @classmethod
    def from_openai(cls, tool_call) -> "ToolCall":
        return cls(
            id=tool_call.id,
            name=tool_call.function.name,
            arguments=tool_call.function.arguments
        )


@dataclass
class ChatResponse:
    """对话响应"""
    content: Optional[str] = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)
```

- [ ] **Step 2: 添加 chat_with_tools 方法**

在 `LLMClient` 类中添加方法：

```python
    def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        system_prompt: str = None
    ) -> "ChatResponse":
        """支持工具调用的对话

        Args:
            messages: 对话消息列表
            tools: 工具定义列表
            system_prompt: 系统提示词

        Returns:
            ChatResponse: 包含 content 和 tool_calls 的响应
        """
        from src.llm_tool_models import ChatResponse, ToolCall

        if not self.api_key:
            logger.error("chat_with_tools: API key not configured")
            return ChatResponse(content="API 密钥未配置")

        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        try:
            if self.client:
                response = self.client.chat.completions.create(
                    model="qwen-plus",
                    messages=full_messages,
                    tools=tools,
                    tool_choice="auto"
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

        except Exception as e:
            logger.error(f"chat_with_tools failed: {e}", exc_info=True)
            return ChatResponse(content=f"对话服务异常：{str(e)}")

    def _parse_tool_response(self, response) -> "ChatResponse":
        """解析工具调用响应"""
        from src.llm_tool_models import ChatResponse, ToolCall

        # 提取 message
        if hasattr(response, 'choices') and response.choices:
            message = response.choices[0].message
        elif hasattr(response, 'output') and response.output:
            message = response.output.choices[0].message
        else:
            return ChatResponse(content="响应格式异常")

        # 提取 tool_calls
        tool_calls = []
        if hasattr(message, 'tool_calls') and message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append(ToolCall.from_openai(tc))

        return ChatResponse(
            content=message.content,
            tool_calls=tool_calls,
            finish_reason="tool_calls" if tool_calls else "stop"
        )
```

- [ ] **Step 3: 编写单元测试**

创建 `tests/unit/test_llm_tool_models.py`:

```python
"""测试 LLM 工具调用模型"""
import pytest
from src.llm_tool_models import ToolCall, ChatResponse


def test_tool_call_from_openai():
    """测试从 OpenAI 格式创建 ToolCall"""
    class MockFunction:
        name = "test_tool"
        arguments = '{"arg1": "value1"}'

    class MockToolCall:
        id = "call_123"
        function = MockFunction()

    tc = ToolCall.from_openai(MockToolCall())

    assert tc.id == "call_123"
    assert tc.name == "test_tool"
    assert tc.arguments == '{"arg1": "value1"}'


def test_chat_response_has_tool_calls():
    """测试 ChatResponse 工具调用检测"""
    response = ChatResponse(content="test")
    assert not response.has_tool_calls

    tc = ToolCall(id="1", name="tool", arguments="{}")
    response = ChatResponse(content=None, tool_calls=[tc])
    assert response.has_tool_calls
```

- [ ] **Step 4: 运行测试**

```bash
pytest tests/unit/test_llm_tool_models.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/llm_tool_models.py src/llm_client.py tests/unit/test_llm_tool_models.py
git commit -m "feat(llm): 添加工具调用支持 chat_with_tools 方法"
```

---

## Chunk 3: 工具层实现

### Task 4: 创建工具定义

**Files:**
- Create: `src/react/__init__.py`
- Create: `src/react/tools.py`

- [ ] **Step 1: 创建模块入口**

创建 `src/react/__init__.py`:

```python
"""ReACT 模块 - 简化版智能助手"""
from src.react.orchestrator import MVPReACTOrchestrator
from src.react.tool_service import MVPToolService

__all__ = ["MVPReACTOrchestrator", "MVPToolService"]
```

- [ ] **Step 2: 创建工具定义**

创建 `src/react/tools.py`:

```python
"""工具定义 - 供 Qwen 调用的工具集"""

MVP_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_schema",
            "description": "搜索数据库中与查询相关的表和字段。当你需要了解数据结构或查找相关表时使用。",
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

SYSTEM_PROMPT = """你是智能停车数据库助手。

## 工具使用规则

1. **search_schema**: 先搜索了解数据结构
2. **execute_sql**: 执行SQL操作
   - SELECT: 直接执行
   - UPDATE/DELETE/INSERT: 需要用户确认
3. **list_operations**: 查看可用的预定义操作
4. **execute_operation**: 执行预定义操作（更安全）

## 工作流程

1. 理解用户需求
2. 搜索相关表结构（如需要）
3. 执行查询或操作
4. 用简洁的中文返回结果

## 注意

- 不要向用户显示SQL语句
- 用自然语言描述操作内容
- 如果用户说"不对"或要求修正，重新执行"""
```

- [ ] **Step 3: Commit**

```bash
git add src/react/__init__.py src/react/tools.py
git commit -m "feat(react): 添加工具定义 MVP_TOOLS 和系统提示"
```

---

### Task 5: 实现工具服务

**Files:**
- Create: `src/react/tool_service.py`

- [ ] **Step 1: 创建工具服务类骨架**

创建 `src/react/tool_service.py`:

```python
"""MVP 工具服务 - 实现工具的具体逻辑"""
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class MVPToolService:
    """MVP 工具服务

    实现 4 个工具的具体逻辑：
    - search_schema: 搜索表结构
    - execute_sql: 执行SQL
    - list_operations: 列出操作
    - execute_operation: 执行操作
    """

    def __init__(
        self,
        db_manager,
        retrieval_pipeline,
        operation_executor,
        knowledge_loader
    ):
        """初始化工具服务

        Args:
            db_manager: 数据库管理器
            retrieval_pipeline: 检索管道
            operation_executor: 操作执行器
            knowledge_loader: 知识库加载器
        """
        self.db = db_manager
        self.retrieval = retrieval_pipeline
        self.executor = operation_executor
        self.knowledge = knowledge_loader

    def execute(self, tool_name: str, args: dict) -> str:
        """执行工具

        Args:
            tool_name: 工具名称
            args: 工具参数

        Returns:
            str: 执行结果（字符串格式，供模型阅读）
        """
        method = getattr(self, f"_tool_{tool_name}", None)
        if not method:
            return f"错误：未知工具 {tool_name}"

        try:
            return method(**args)
        except Exception as e:
            logger.error(f"Tool {tool_name} failed: {e}", exc_info=True)
            return f"工具执行失败：{str(e)}"
```

- [ ] **Step 2: 实现 search_schema 工具**

```python
    def _tool_search_schema(self, query: str) -> str:
        """搜索表结构

        Args:
            query: 搜索关键词

        Returns:
            str: 相关表的信息
        """
        result = self.retrieval.search(query, top_k=5)

        if not result.matches:
            return "未找到相关的表。请尝试其他关键词。"

        lines = ["找到以下相关表："]
        for match in result.matches:
            table_name = match.table_name
            description = match.description or ""
            lines.append(f"- {table_name}")
            if description:
                lines.append(f"  说明：{description[:100]}")

        return "\n".join(lines)
```

- [ ] **Step 3: 实现 execute_sql 工具**

```python
    def _tool_execute_sql(self, sql: str, description: str = None) -> str:
        """执行SQL

        Args:
            sql: SQL语句
            description: 操作描述

        Returns:
            str: 执行结果
        """
        sql_upper = sql.strip().upper()

        # SELECT 查询直接执行
        if sql_upper.startswith("SELECT") or sql_upper.startswith("SHOW") or sql_upper.startswith("DESC"):
            try:
                df = self.db.execute_query(sql)
                if df.empty:
                    return "查询结果为空。"

                # 限制显示行数
                display_df = df.head(20)
                result = f"查询返回 {len(df)} 行数据：\n"
                result += display_df.to_string(index=False)

                if len(df) > 20:
                    result += f"\n... 省略 {len(df) - 20} 行"

                return result
            except Exception as e:
                return f"查询失败：{str(e)}"

        # 修改操作需要确认
        return f"__NEED_CONFIRM__\n操作：{description or '执行SQL'}\nSQL：{sql}"
```

- [ ] **Step 4: 实现 list_operations 工具**

```python
    def _tool_list_operations(self) -> str:
        """列出可用操作

        Returns:
            str: 操作列表
        """
        operations = self.knowledge.get_all_operations()

        if not operations:
            return "暂无预定义操作。"

        lines = ["可用的业务操作："]
        for op in operations[:20]:  # 限制显示数量
            lines.append(f"- {op.id}: {op.name}")
            if op.description:
                lines.append(f"  {op.description[:50]}")

        if len(operations) > 20:
            lines.append(f"... 共 {len(operations)} 个操作")

        return "\n".join(lines)
```

- [ ] **Step 5: 实现 execute_operation 工具**

```python
    def _tool_execute_operation(self, operation_id: str, params: dict = None) -> str:
        """执行预定义操作

        Args:
            operation_id: 操作ID
            params: 操作参数

        Returns:
            str: 执行结果
        """
        params = params or {}

        # 先预览
        preview_result = self.executor.execute_operation(
            operation_id,
            params,
            preview_only=True
        )

        if not preview_result.success:
            return f"操作预览失败：{preview_result.error}"

        # 检查是否是修改操作
        op = self.knowledge.get_operation(operation_id)
        if op and op.is_mutation():
            # 返回预览信息，需要确认
            return f"__NEED_CONFIRM__\n操作：{op.name}\n预览：{preview_result.summary or '即将执行'}"

        # 查询操作直接执行
        result = self.executor.execute_operation(
            operation_id,
            params,
            preview_only=False
        )

        if result.success:
            return f"操作成功：{result.summary or '已完成'}"
        else:
            return f"操作失败：{result.error}"
```

- [ ] **Step 6: 添加确认执行方法**

```python
    def confirm_and_execute_sql(self, sql: str) -> str:
        """确认后执行SQL

        Args:
            sql: SQL语句

        Returns:
            str: 执行结果
        """
        try:
            affected = self.db.execute_update(sql)
            return f"执行成功，影响 {affected} 行。"
        except Exception as e:
            return f"执行失败：{str(e)}"

    def confirm_and_execute_operation(self, operation_id: str, params: dict) -> str:
        """确认后执行操作

        Args:
            operation_id: 操作ID
            params: 操作参数

        Returns:
            str: 执行结果
        """
        result = self.executor.execute_operation(
            operation_id,
            params,
            preview_only=False,
            auto_commit=True
        )

        if result.success:
            return f"操作成功：{result.summary or '已完成'}"
        else:
            return f"操作失败：{result.error}"
```

- [ ] **Step 7: 编写单元测试**

创建 `tests/unit/react/test_tool_service.py`:

```python
"""测试工具服务"""
import pytest
from unittest.mock import Mock, MagicMock
from src.react.tool_service import MVPToolService


@pytest.fixture
def tool_service():
    """创建工具服务实例"""
    db = Mock()
    retrieval = Mock()
    executor = Mock()
    knowledge = Mock()

    return MVPToolService(db, retrieval, executor, knowledge)


def test_search_schema_no_results(tool_service):
    """测试搜索无结果"""
    tool_service.retrieval.search.return_value = Mock(matches=[])

    result = tool_service._tool_search_schema("不存在")

    assert "未找到" in result


def test_execute_sql_select(tool_service):
    """测试SELECT查询"""
    import pandas as pd
    tool_service.db.execute_query.return_value = pd.DataFrame({
        "name": ["张三", "李四"],
        "age": [25, 30]
    })

    result = tool_service._tool_execute_sql("SELECT * FROM users")

    assert "2 行数据" in result


def test_execute_sql_update_needs_confirm(tool_service):
    """测试UPDATE需要确认"""
    result = tool_service._tool_execute_sql("UPDATE users SET age=20", "更新年龄")

    assert "__NEED_CONFIRM__" in result


def test_execute_unknown_tool(tool_service):
    """测试未知工具"""
    result = tool_service.execute("unknown_tool", {})

    assert "未知工具" in result
```

- [ ] **Step 8: 运行测试**

```bash
pytest tests/unit/react/test_tool_service.py -v
```

- [ ] **Step 9: Commit**

```bash
git add src/react/tool_service.py tests/unit/react/test_tool_service.py
git commit -m "feat(react): 实现 MVPToolService 四个工具"
```

---

## Chunk 4: Orchestrator 实现

### Task 6: 实现 MVP ReACT Orchestrator

**Files:**
- Create: `src/react/orchestrator.py`

- [ ] **Step 1: 创建 Orchestrator 类骨架**

创建 `src/react/orchestrator.py`:

```python
"""MVP ReACT 编排器 - 无学习功能的简化版"""
import json
import logging
from typing import Generator, Optional
from dataclasses import dataclass, field

from src.llm_client import LLMClient
from src.react.tool_service import MVPToolService
from src.react.tools import MVP_TOOLS, SYSTEM_PROMPT

logger = logging.getLogger(__name__)


@dataclass
class ConversationState:
    """对话状态"""
    messages: list = field(default_factory=list)
    pending_confirmation: bool = False
    confirmation_type: str = ""  # "sql" or "operation"
    confirmation_data: dict = field(default_factory=dict)


class MVPReACTOrchestrator:
    """MVP ReACT 编排器

    实现简化的 ReACT 循环：
    1. 模型推理 → 调用工具
    2. 执行 → 返回结果
    3. 用户修正 → 重新执行

    无学习记忆功能。
    """

    def __init__(
        self,
        llm_client: LLMClient,
        tool_service: MVPToolService,
        max_iterations: int = 5
    ):
        """初始化编排器

        Args:
            llm_client: LLM 客户端
            tool_service: 工具服务
            max_iterations: 最大迭代次数
        """
        self.llm = llm_client
        self.tools = tool_service
        self.max_iterations = max_iterations
        self.state = ConversationState()
```

- [ ] **Step 2: 实现 process 方法**

```python
    def process(self, user_input: str) -> str:
        """处理用户输入

        Args:
            user_input: 用户输入

        Returns:
            str: 助手回复
        """
        # 添加用户消息
        self.state.messages.append({"role": "user", "content": user_input})

        # ReACT 循环
        for iteration in range(self.max_iterations):
            # 调用模型
            response = self.llm.chat_with_tools(
                messages=self.state.messages,
                tools=MVP_TOOLS,
                system_prompt=SYSTEM_PROMPT
            )

            # 检查是否有工具调用
            if response.has_tool_calls:
                # 执行工具
                tool_results = self._execute_tools(response.tool_calls)

                # 检查是否需要确认
                if self.state.pending_confirmation:
                    return self._format_confirmation_request()

                # 添加工具结果到消息
                self._add_tool_results(response.tool_calls, tool_results)

                # 继续循环
                continue

            # 没有工具调用，返回最终答案
            self.state.messages.append({"role": "assistant", "content": response.content or ""})
            return response.content or "抱歉，我没有理解您的问题。"

        return "抱歉，我需要更多时间来处理您的请求。"
```

- [ ] **Step 3: 实现工具执行方法**

```python
    def _execute_tools(self, tool_calls: list) -> list[str]:
        """执行工具调用

        Args:
            tool_calls: 工具调用列表

        Returns:
            list[str]: 工具结果列表
        """
        results = []

        for tc in tool_calls:
            args = json.loads(tc.arguments) if tc.arguments else {}
            result = self.tools.execute(tc.name, args)

            # 检查是否需要确认
            if result.startswith("__NEED_CONFIRM__"):
                self.state.pending_confirmation = True
                self.state.confirmation_type = "sql" if tc.name == "execute_sql" else "operation"
                self.state.confirmation_data = {
                    "tool_name": tc.name,
                    "args": args,
                    "preview": result.replace("__NEED_CONFIRM__\n", "")
                }

            results.append(result)

        return results

    def _format_confirmation_request(self) -> str:
        """格式化确认请求"""
        preview = self.state.confirmation_data.get("preview", "")
        return f"{preview}\n\n确认执行？(输入 'y' 确认，或描述您的修改意见)"
```

- [ ] **Step 4: 实现确认处理方法**

```python
    def confirm(self, confirmed: bool, modification: str = None) -> str:
        """处理用户确认

        Args:
            confirmed: 是否确认
            modification: 修改意见（可选）

        Returns:
            str: 执行结果
        """
        if not confirmed:
            self.state.pending_confirmation = False
            self.state.confirmation_data = {}
            return "操作已取消。"

        # 执行确认的操作
        tool_name = self.state.confirmation_data.get("tool_name")
        args = self.state.confirmation_data.get("args", {})

        if tool_name == "execute_sql":
            result = self.tools.confirm_and_execute_sql(args.get("sql", ""))
        elif tool_name == "execute_operation":
            result = self.tools.confirm_and_execute_operation(
                args.get("operation_id"),
                args.get("params", {})
            )
        else:
            result = "未知操作类型"

        # 重置状态
        self.state.pending_confirmation = False
        self.state.confirmation_data = {}

        return result
```

- [ ] **Step 5: 实现辅助方法**

```python
    def _add_tool_results(self, tool_calls: list, results: list[str]):
        """添加工具结果到消息"""
        # 添加助手消息（包含工具调用）
        self.state.messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": tc.arguments
                    }
                }
                for tc in tool_calls
            ]
        })

        # 添加工具结果
        for tc, result in zip(tool_calls, results):
            self.state.messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result
            })

    def reset(self):
        """重置对话状态"""
        self.state = ConversationState()
```

- [ ] **Step 6: 编写单元测试**

创建 `tests/unit/react/test_orchestrator.py`:

```python
"""测试 MVP Orchestrator"""
import pytest
from unittest.mock import Mock, MagicMock
from src.react.orchestrator import MVPReACTOrchestrator, ConversationState
from src.llm_tool_models import ChatResponse, ToolCall


@pytest.fixture
def orchestrator():
    """创建编排器实例"""
    llm = Mock()
    tools = Mock()
    return MVPReACTOrchestrator(llm, tools)


def test_process_without_tools(orchestrator):
    """测试无工具调用的处理"""
    orchestrator.llm.chat_with_tools.return_value = ChatResponse(
        content="你好，我是助手",
        tool_calls=[]
    )

    result = orchestrator.process("你好")

    assert result == "你好，我是助手"


def test_process_with_tools(orchestrator):
    """测试有工具调用的处理"""
    # 第一次返回工具调用
    tc = ToolCall(id="1", name="search_schema", arguments='{"query": "车牌"}')
    orchestrator.llm.chat_with_tools.side_effect = [
        ChatResponse(content=None, tool_calls=[tc]),
        ChatResponse(content="找到车牌表", tool_calls=[])
    ]
    orchestrator.tools.execute.return_value = "找到 cloud_fixed_plate 表"

    result = orchestrator.process("查找车牌表")

    assert "车牌表" in result


def test_confirmation_flow(orchestrator):
    """测试确认流程"""
    tc = ToolCall(id="1", name="execute_sql", arguments='{"sql": "UPDATE ..."}')
    orchestrator.llm.chat_with_tools.return_value = ChatResponse(
        content=None,
        tool_calls=[tc]
    )
    orchestrator.tools.execute.return_value = "__NEED_CONFIRM__\n操作：更新数据"

    result = orchestrator.process("更新数据")

    assert "确认执行" in result
    assert orchestrator.state.pending_confirmation

    # 用户确认
    confirm_result = orchestrator.confirm(True)
    assert orchestrator.tools.confirm_and_execute_sql.called
```

- [ ] **Step 7: 运行测试**

```bash
pytest tests/unit/react/test_orchestrator.py -v
```

- [ ] **Step 8: Commit**

```bash
git add src/react/orchestrator.py tests/unit/react/test_orchestrator.py
git commit -m "feat(react): 实现 MVPReACTOrchestrator 编排器"
```

---

## Chunk 5: main.py 改造

### Task 7: 改造 main.py 使用新架构

**Files:**
- Modify: `main.py`

- [ ] **Step 1: 添加新架构初始化代码**

在 main.py 中找到 Orchestrator 初始化代码后，添加新架构初始化：

```python
        # 初始化 MVP ReACT 架构
        print("正在初始化 ReACT 架构...")
        try:
            from src.react.orchestrator import MVPReACTOrchestrator
            from src.react.tool_service import MVPToolService

            mvp_tool_service = MVPToolService(
                db_manager=db,
                retrieval_pipeline=RetrievalPipeline(),
                operation_executor=operation_executor,
                knowledge_loader=knowledge_loader
            )
            mvp_orchestrator = MVPReACTOrchestrator(
                llm_client=llm,
                tool_service=mvp_tool_service
            )
            logger.info("ReACT 架构初始化成功")
            print("[OK] ReACT 架构初始化成功！")
        except Exception as e:
            logger.error(f"ReACT 架构初始化失败: {e}")
            print(f"[WARN] ReACT 架构初始化失败: {e}")
            mvp_orchestrator = None
```

- [ ] **Step 2: 添加 react 命令**

在命令处理部分添加新命令：

```python
            # 新增：react 命令 - 使用新架构对话
            if user_input.lower() == 'react':
                if not mvp_orchestrator:
                    print("[ERR] ReACT 架构未初始化")
                    continue

                print("\n" + "=" * 60)
                print("进入 ReACT 对话模式（新架构）")
                print("你好，我是你的智能数据库助手。")
                print("输入 'exit' 或 'quit' 退出")
                print("=" * 60)

                while True:
                    try:
                        react_input = input("\n[ReACT] > ").strip()
                        if not react_input:
                            continue

                        if react_input.lower() in ['exit', 'quit', '退出']:
                            break

                        # 检查是否是确认响应
                        if mvp_orchestrator.state.pending_confirmation:
                            if react_input.lower() == 'y':
                                result = mvp_orchestrator.confirm(True)
                                print(f"\n[助手] {result}")
                            elif react_input.lower() == 'n':
                                result = mvp_orchestrator.confirm(False)
                                print(f"\n[助手] {result}")
                            else:
                                # 用户修改意见，重置状态重新处理
                                mvp_orchestrator.state.pending_confirmation = False
                                result = mvp_orchestrator.process(f"用户修改：{react_input}")
                                print(f"\n[助手] {result}")
                            continue

                        # 正常处理
                        result = mvp_orchestrator.process(react_input)
                        print(f"\n[助手] {result}")

                    except KeyboardInterrupt:
                        break
                    except Exception as e:
                        logger.error(f"ReACT 模式错误: {e}", exc_info=True)
                        print(f"[ERR] 出错: {e}")

                mvp_orchestrator.reset()
                print("退出 ReACT 模式")
                print("=" * 60)
                continue
```

- [ ] **Step 3: 更新欢迎信息**

修改 `print_welcome` 函数，添加 react 命令说明：

```python
    print("  react             - 进入 ReACT 对话模式（新架构，推荐）")
```

- [ ] **Step 4: 手动测试**

```bash
python main.py
# 输入 react 进入新模式
# 测试用例：
# 1. "查询车牌 沪A12345"
# 2. "列出所有园区"
# 3. "搜索车牌相关的表"
```

- [ ] **Step 5: Commit**

```bash
git add main.py
git commit -m "feat(main): 添加 react 命令使用新 ReACT 架构"
```

---

## Chunk 6: 集成测试

### Task 8: 编写端到端测试

**Files:**
- Create: `tests/integration/test_mvp_flow.py`

- [ ] **Step 1: 创建集成测试**

创建 `tests/integration/test_mvp_flow.py`:

```python
"""MVP 流程端到端测试"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd

from src.react.orchestrator import MVPReACTOrchestrator
from src.react.tool_service import MVPToolService
from src.llm_tool_models import ChatResponse, ToolCall


class TestMVPFlow:
    """MVP 流程测试"""

    @pytest.fixture
    def setup_components(self):
        """设置测试组件"""
        llm = Mock()
        db = Mock()
        retrieval = Mock()
        executor = Mock()
        knowledge = Mock()

        tool_service = MVPToolService(db, retrieval, executor, knowledge)
        orchestrator = MVPReACTOrchestrator(llm, tool_service)

        return {
            "llm": llm,
            "db": db,
            "retrieval": retrieval,
            "executor": executor,
            "knowledge": knowledge,
            "tool_service": tool_service,
            "orchestrator": orchestrator
        }

    def test_query_plate_info(self, setup_components):
        """测试用例1：查询车牌信息"""
        orch = setup_components["orchestrator"]
        setup_components["llm"].chat_with_tools.return_value = ChatResponse(
            content="车牌 沪A12345，状态=已下发，绑定园区=国际商务中心",
            tool_calls=[]
        )

        result = orch.process("查询车牌 沪A12345")

        assert result != "None"
        assert "沪A12345" in result or "车牌" in result

    def test_list_parks(self, setup_components):
        """测试用例5：列出所有园区"""
        orch = setup_components["orchestrator"]
        setup_components["llm"].chat_with_tools.return_value = ChatResponse(
            content="共有 33 个园区：国际商务中心、万达广场...",
            tool_calls=[]
        )

        result = orch.process("列出所有园区")

        assert "园区" in result

    def test_update_needs_confirmation(self, setup_components):
        """测试修改操作需要确认"""
        orch = setup_components["orchestrator"]

        tc = ToolCall(id="1", name="execute_sql", arguments='{"sql": "UPDATE ..."}')
        setup_components["llm"].chat_with_tools.return_value = ChatResponse(
            content=None,
            tool_calls=[tc]
        )
        setup_components["db"].execute_query.return_value = pd.DataFrame()

        result = orch.process("下发车牌")

        assert "确认" in result or "确认执行" in result
        assert orch.state.pending_confirmation

    def test_user_correction(self, setup_components):
        """测试用例9：用户修正"""
        orch = setup_components["orchestrator"]

        # 第一次返回错误结果
        setup_components["llm"].chat_with_tools.side_effect = [
            ChatResponse(content="查询结果：车牌不存在", tool_calls=[]),
            ChatResponse(content="修正后：找到车牌 沪A12345", tool_calls=[])
        ]

        result1 = orch.process("查询车牌")
        result2 = orch.process("不对，车牌是 沪A12345")

        assert "沪A12345" in result2

    def test_user_cancel(self, setup_components):
        """测试用例10：用户取消操作"""
        orch = setup_components["orchestrator"]

        tc = ToolCall(id="1", name="execute_sql", arguments='{"sql": "UPDATE ..."}')
        setup_components["llm"].chat_with_tools.return_value = ChatResponse(
            content=None,
            tool_calls=[tc]
        )

        orch.process("下发车牌")
        result = orch.confirm(False)

        assert "取消" in result
```

- [ ] **Step 2: 运行集成测试**

```bash
pytest tests/integration/test_mvp_flow.py -v
```

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_mvp_flow.py
git commit -m "test: 添加 MVP 流程端到端测试"
```

---

## 验收清单

完成所有任务后，验证以下内容：

- [ ] `python main.py` 启动无错误
- [ ] 输入 `react` 进入新对话模式
- [ ] 测试用例1-5（查询类）全部成功
- [ ] 测试用例6-8（操作类）需要确认
- [ ] 测试用例9（修正）正常工作
- [ ] 测试用例10（取消）正常工作
- [ ] 无 None 返回
- [ ] 所有测试通过：`pytest tests/ -v`

---

*本计划由 Claude Code 生成，遵循 TDD、DRY、YAGNI 原则*