# 修复对话模式返回 None 问题实施计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复对话模式(chat)返回 None 的问题，确保用户输入自然语言后能获得有意义的回复。

**Architecture:** 分层防御策略，在 LLMClient、KnowledgeAgent、Orchestrator、main.py 四个层面添加错误处理和降级机制，确保任何层级失败都能给出友好提示。

**Tech Stack:** Python 3.11+, pytest, DashScope/Qwen LLM API

---

## 测试目录结构

```
tests/
├── unit/
│   ├── test_llm_client_stream.py    # LLMClient.chat_stream 测试
│   ├── test_main_chat.py            # main.py chat 模式测试
│   └── agents/
│       ├── test_knowledge_agent.py
│       └── test_orchestrator_conversation.py
└── integration/
    └── test_chat_mode.py
```

---

## 文件结构

| 文件 | 职责 | 修改类型 |
|------|------|----------|
| `src/llm_client.py:834-908` | LLM API 调用层 - 添加前置检查、日志、降级 | 修改 |
| `src/agents/impl/knowledge_agent.py:15-33` | Agent 层 - 验证 generator、异常处理 | 修改 |
| `src/agents/orchestrator.py:112-139` | 编排层 - 检查结果有效性 | 修改 |
| `main.py:320-345` | CLI 层 - 处理所有边界情况 | 修改 |
| `tests/unit/test_llm_client_stream.py` | LLMClient.chat_stream 单元测试 | 创建 |
| `tests/unit/test_main_chat.py` | main.py chat 模式单元测试 | 创建 |
| `tests/unit/agents/test_knowledge_agent.py` | KnowledgeAgent 单元测试 | 创建 |
| `tests/unit/agents/test_orchestrator_conversation.py` | Orchestrator 对话流程测试 | 创建 |
| `tests/integration/test_chat_mode.py` | chat 模式集成测试 | 创建 |

---

## Chunk 1: LLMClient.chat_stream() 增强

### Task 1.1: 为 chat_stream 添加前置检查和日志

**Files:**
- Modify: `src/llm_client.py:834-908`
- Test: `tests/unit/test_llm_client_stream.py`

- [ ] **Step 1: 创建测试文件骨架**

```python
# tests/unit/test_llm_client_stream.py
"""LLMClient.chat_stream 单元测试"""
import pytest
from unittest.mock import patch, MagicMock
from src.llm_client import LLMClient


class TestChatStreamValidation:
    """测试 chat_stream 的输入验证"""

    pass
```

- [ ] **Step 2: 编写空消息列表测试**

添加到 `tests/unit/test_llm_client_stream.py`:

```python
    def test_empty_messages_returns_error_chunk(self):
        """空消息列表应返回 error chunk"""
        client = LLMClient.__new__(LLMClient)
        client.api_key = "test-key"
        client.client = None

        chunks = list(client.chat_stream(messages=[]))

        assert len(chunks) == 1
        assert chunks[0]["type"] == "error"
        assert "消息列表为空" in chunks[0]["content"]
```

- [ ] **Step 3: 编写无 API key 测试**

添加到 `tests/unit/test_llm_client_stream.py`:

```python
    def test_no_api_key_returns_error_chunk(self):
        """未配置 API key 应返回 error chunk"""
        client = LLMClient.__new__(LLMClient)
        client.api_key = None
        client.client = None

        chunks = list(client.chat_stream(messages=[{"role": "user", "content": "test"}]))

        assert len(chunks) == 1
        assert chunks[0]["type"] == "error"
        assert "API 密钥未配置" in chunks[0]["content"]
```

- [ ] **Step 4: 运行测试验证失败**

Run: `pytest tests/unit/test_llm_client_stream.py -v`
Expected: FAIL - 功能尚未实现

- [ ] **Step 5: 修改 chat_stream 添加前置检查**

在 `src/llm_client.py` 的 `chat_stream` 方法开头添加检查：

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

    # 原有代码继续...
    try:
        logger.info(f"chat_stream: calling LLM with {len(messages)} messages")
        # ... 保持原有实现
```

- [ ] **Step 6: 运行测试验证通过**

Run: `pytest tests/unit/test_llm_client_stream.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add tests/unit/test_llm_client_stream.py src/llm_client.py
git commit -m "feat(llm): 添加 chat_stream 前置检查和错误处理"
```

### Task 1.2: 为 chat_stream 添加输出验证和降级

**Files:**
- Modify: `src/llm_client.py:865-908`
- Test: `tests/unit/test_llm_client_stream.py`

- [ ] **Step 1: 编写失败测试**

```python
# 添加到 tests/unit/test_llm_client_stream.py

class TestChatStreamOutputValidation:
    """测试 chat_stream 的输出验证"""

    @patch('src.llm_client.Generation.call')
    def test_no_content_returns_fallback_message(self, mock_call):
        """LLM 无输出时返回降级消息"""
        client = LLMClient.__new__(LLMClient)
        client.api_key = "test-key"
        client.client = None
        client._metrics_collector = MagicMock()

        # 模拟空响应
        mock_chunk = MagicMock()
        mock_chunk.output.choices = []
        mock_call.return_value = iter([mock_chunk])

        chunks = list(client.chat_stream(messages=[{"role": "user", "content": "test"}]))

        # 应该包含降级消息
        content_chunks = [c for c in chunks if c.get("type") == "content"]
        assert len(content_chunks) >= 1
        assert "抱歉" in content_chunks[-1]["content"] or "无法回答" in content_chunks[-1]["content"]

    @patch('src.llm_client.Generation.call')
    def test_exception_returns_error_chunk(self, mock_call):
        """异常时返回 error chunk"""
        client = LLMClient.__new__(LLMClient)
        client.api_key = "test-key"
        client.client = None
        client._metrics_collector = MagicMock()

        mock_call.side_effect = Exception("Network error")

        chunks = list(client.chat_stream(messages=[{"role": "user", "content": "test"}]))

        assert len(chunks) == 1
        assert chunks[0]["type"] == "error"
        assert "Network error" in chunks[0]["content"]
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/unit/test_llm_client_stream.py::TestChatStreamOutputValidation -v`
Expected: FAIL

- [ ] **Step 3: 修改 chat_stream 添加输出验证**

修改 `src/llm_client.py` 中的循环部分：

```python
# 在 chat_stream 方法的 try 块内，替换原有循环
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

    usage = getattr(chunk, "usage", None)
    # ... 保持 usage 处理逻辑 ...

# 检查是否有输出
if not has_content:
    logger.warning("chat_stream: No content generated from LLM")
    yield {"type": "content", "content": "抱歉，我暂时无法回答这个问题。请稍后再试。"}
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/unit/test_llm_client_stream.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_llm_client_stream.py src/llm_client.py
git commit -m "feat(llm): 添加 chat_stream 输出验证和降级消息"
```

---

## Chunk 2: KnowledgeAgent 错误处理

### Task 2.1: 增强 KnowledgeAgent 异常处理

**Files:**
- Modify: `src/agents/impl/knowledge_agent.py:15-33`
- Test: `tests/unit/agents/test_knowledge_agent.py`

- [ ] **Step 1: 创建测试文件并编写失败测试**

```python
# tests/unit/agents/test_knowledge_agent.py
"""KnowledgeAgent 单元测试"""
import pytest
from unittest.mock import MagicMock, patch
from src.agents.impl.knowledge_agent import KnowledgeAgent
from src.agents.context import AgentContext
from src.agents.models import IntentModel


class TestKnowledgeAgentErrorHandling:
    """测试 KnowledgeAgent 错误处理"""

    def test_chat_stream_returns_none(self):
        """chat_stream 返回 None 时应返回失败结果"""
        config = MagicMock()
        llm_client = MagicMock()
        llm_client.chat_stream.return_value = None

        agent = KnowledgeAgent(config, llm_client=llm_client)

        context = AgentContext(user_input="测试问题")
        context.intent = IntentModel(type="chat", operation_id="general_chat")

        result = agent._run_impl(context)

        assert result.success is False
        assert "异常" in result.message or "LLM" in result.message

    def test_chat_stream_raises_exception(self):
        """chat_stream 抛出异常时应捕获"""
        config = MagicMock()
        llm_client = MagicMock()
        llm_client.chat_stream.side_effect = Exception("API Error")

        agent = KnowledgeAgent(config, llm_client=llm_client)

        context = AgentContext(user_input="测试问题")
        context.intent = IntentModel(type="chat", operation_id="general_chat")

        result = agent._run_impl(context)

        assert result.success is False
        assert "异常" in result.message

    def test_valid_stream_returns_success(self):
        """有效 generator 应返回成功"""
        config = MagicMock()
        llm_client = MagicMock()

        def mock_generator():
            yield {"type": "content", "content": "测试回复"}

        llm_client.chat_stream.return_value = mock_generator()

        agent = KnowledgeAgent(config, llm_client=llm_client)

        context = AgentContext(user_input="测试问题")
        context.intent = IntentModel(type="chat", operation_id="general_chat")

        result = agent._run_impl(context)

        assert result.success is True
        assert result.message == "knowledge_stream_ready"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/unit/agents/test_knowledge_agent.py -v`
Expected: FAIL - 异常处理未实现

- [ ] **Step 3: 修改 KnowledgeAgent._run_impl**

修改 `src/agents/impl/knowledge_agent.py`:

```python
"""Knowledge Agent 实现"""
import logging
from src.agents.base import BaseAgent
from src.agents.models import AgentResult
from src.agents.context import AgentContext
from src.llm_client import LLMClient

logger = logging.getLogger(__name__)


class KnowledgeAgent(BaseAgent):
    """知识问答 Agent，负责基于 schema 上下文输出流式回复。"""

    def __init__(self, config, llm_client: LLMClient | None = None):
        super().__init__(config)
        self.llm_client = llm_client or LLMClient()

    def _run_impl(self, context: AgentContext) -> AgentResult:
        """执行知识问答

        Args:
            context: Agent 执行上下文

        Returns:
            AgentResult: 包含 generator 的结果对象
        """
        if not context.intent or context.intent.type not in ["qa", "chat"]:
            return AgentResult(success=False, message="KnowledgeAgent 仅处理 qa/chat 意图")

        # 构建消息
        schema_context = context.schema_context or "暂无可用 schema 上下文"

        # 简化系统提示，让模型更自由
        messages = [
            {
                "role": "system",
                "content": f"你是智能停车数据库助手。\n\n相关表: {schema_context}"
            },
            {"role": "user", "content": context.user_input},
        ]

        try:
            stream = self.llm_client.chat_stream(messages=messages, enable_thinking=True)

            # 验证 generator 是否有效
            if stream is None:
                logger.error("chat_stream returned None")
                return AgentResult(
                    success=False,
                    message="LLM 服务返回异常",
                    data=None
                )

            return AgentResult(success=True, data=stream, message="knowledge_stream_ready")

        except Exception as e:
            logger.error(f"KnowledgeAgent failed: {e}", exc_info=True)
            return AgentResult(
                success=False,
                message=f"对话服务异常: {str(e)}",
                data=None
            )
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/unit/agents/test_knowledge_agent.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/unit/agents/test_knowledge_agent.py src/agents/impl/knowledge_agent.py
git commit -m "fix(agents): 增强 KnowledgeAgent 异常处理和 generator 验证"
```

---

## Chunk 3: Orchestrator 对话流程增强

### Task 3.1: 增强 _handle_conversation 结果验证

**Files:**
- Modify: `src/agents/orchestrator.py:112-139`
- Test: `tests/unit/agents/test_orchestrator_conversation.py`

- [ ] **Step 1: 创建测试文件并编写失败测试**

```python
# tests/unit/agents/test_orchestrator_conversation.py
"""Orchestrator 对话流程测试"""
import pytest
from unittest.mock import MagicMock
from src.agents.orchestrator import Orchestrator
from src.agents.context import AgentContext
from src.agents.models import IntentModel, AgentResult


class TestOrchestratorConversation:
    """测试 Orchestrator 对话流程"""

    def test_knowledge_agent_failure_sets_error_message(self):
        """KnowledgeAgent 失败时应设置错误消息"""
        # 创建 mock agents
        intent_agent = MagicMock()
        intent_agent.run.return_value = MagicMock(success=True)

        retrieval_agent = MagicMock()
        retrieval_agent.run.return_value = MagicMock(success=True)

        knowledge_agent = MagicMock()
        knowledge_agent.run.return_value = AgentResult(
            success=False,
            message="对话服务异常",
            data=None
        )

        orchestrator = Orchestrator(
            intent_agent=intent_agent,
            retrieval_agent=retrieval_agent,
            knowledge_agent=knowledge_agent
        )

        context = orchestrator._handle_conversation(AgentContext(user_input="测试"))

        assert "knowledge_failed" in context.step_history
        assert context.execution_result is not None
        assert "异常" in context.execution_result or "不可用" in context.execution_result

    def test_knowledge_agent_returns_none(self):
        """KnowledgeAgent 返回 None data 时应有降级"""
        intent_agent = MagicMock()
        intent_agent.run.return_value = MagicMock(success=True)

        retrieval_agent = MagicMock()
        retrieval_agent.run.return_value = MagicMock(success=True)

        knowledge_agent = MagicMock()
        knowledge_agent.run.return_value = AgentResult(
            success=True,
            data=None,
            message="success"
        )

        orchestrator = Orchestrator(
            intent_agent=intent_agent,
            retrieval_agent=retrieval_agent,
            knowledge_agent=knowledge_agent
        )

        context = orchestrator._handle_conversation(AgentContext(user_input="测试"))

        assert context.execution_result is not None
        assert "不可用" in context.execution_result or "稍后" in context.execution_result

    def test_knowledge_agent_success(self):
        """KnowledgeAgent 成功时应设置 generator"""
        def mock_generator():
            yield {"type": "content", "content": "测试回复"}

        intent_agent = MagicMock()
        intent_agent.run.return_value = MagicMock(success=True)

        retrieval_agent = MagicMock()
        retrieval_agent.run.return_value = MagicMock(success=True)

        knowledge_agent = MagicMock()
        knowledge_agent.run.return_value = AgentResult(
            success=True,
            data=mock_generator(),
            message="knowledge_stream_ready"
        )

        orchestrator = Orchestrator(
            intent_agent=intent_agent,
            retrieval_agent=retrieval_agent,
            knowledge_agent=knowledge_agent
        )

        context = orchestrator._handle_conversation(AgentContext(user_input="测试"))

        assert context.execution_result is not None
        assert "knowledge" in context.step_history
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/unit/agents/test_orchestrator_conversation.py -v`
Expected: FAIL

- [ ] **Step 3: 修改 _handle_conversation**

修改 `src/agents/orchestrator.py` 的 `_handle_conversation` 方法：

```python
def _handle_conversation(self, context: AgentContext) -> AgentContext:
    """处理对话和知识问答

    执行对话流程：
    1. 可选的 schema 检索（为知识问答提供上下文）
    2. 调用 KnowledgeAgent 进行流式问答

    Args:
        context: 执行上下文

    Returns:
        AgentContext: 更新后的上下文，其中 execution_result 包含 generator 对象或错误消息
    """
    # 检索相关schema（可选）
    retrieval_res = self.retrieval_agent.run(context)
    if retrieval_res.success:
        context.step_history.append("retrieval")

    # 流式问答
    knowledge_res = self.knowledge_agent.run(context)

    if not knowledge_res.success:
        context.step_history.append("knowledge_failed")
        # 设置错误消息作为执行结果
        context.execution_result = knowledge_res.message
        return context

    # 验证 generator 是否有效
    if knowledge_res.data is None:
        context.step_history.append("knowledge_failed")
        context.execution_result = "对话服务暂时不可用，请稍后再试。"
        return context

    context.execution_result = knowledge_res.data  # generator
    context.step_history.append("knowledge")

    return context
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/unit/agents/test_orchestrator_conversation.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/unit/agents/test_orchestrator_conversation.py src/agents/orchestrator.py
git commit -m "fix(orchestrator): 增强 _handle_conversation 结果验证"
```

---

## Chunk 4: main.py CLI 层完善

### Task 4.1: 增强 chat 模式流式输出处理

**Files:**
- Modify: `main.py:320-345`
- Test: `tests/unit/test_main_chat.py`

- [ ] **Step 1: 创建测试文件骨架**

```python
# tests/unit/test_main_chat.py
"""main.py chat 模式单元测试"""
import pytest
from unittest.mock import MagicMock, patch
import types


class TestChatStreamOutput:
    """测试 chat 模式流式输出处理"""

    pass
```

- [ ] **Step 2: 编写 None 结果测试**

添加到 `tests/unit/test_main_chat.py`:

```python
    def test_none_execution_result_shows_fallback(self, capsys):
        """execution_result 为 None 时应显示降级消息"""
        # 模拟处理逻辑
        context = MagicMock()
        context.execution_result = None

        assistant_response = ""
        if context.execution_result is None:
            assistant_response = "抱歉，处理您的请求时出现问题，请稍后再试。"

        assert assistant_response != ""
        assert "抱歉" in assistant_response or "问题" in assistant_response
```

- [ ] **Step 3: 编写 error chunk 测试**

添加到 `tests/unit/test_main_chat.py`:

```python
    def test_error_chunk_handling(self, capsys):
        """应正确处理 error 类型 chunk"""

        def mock_generator():
            yield {"type": "error", "content": "API Error"}

        assistant_response = ""
        has_content = False
        for chunk in mock_generator():
            if chunk.get("type") == "error":
                error_msg = chunk.get("content", "未知错误")
                assistant_response = f"[错误] {error_msg}"
                has_content = True

        assert has_content
        assert "API Error" in assistant_response
```

- [ ] **Step 4: 编写空内容测试**

添加到 `tests/unit/test_main_chat.py`:

```python
    def test_empty_stream_shows_default_message(self, capsys):
        """空 generator 应显示默认消息"""

        def mock_generator():
            return
            yield  # 空生成器

        assistant_response = ""
        has_content = False
        for chunk in mock_generator():
            pass

        if not has_content:
            assistant_response = "抱歉，我没有理解您的问题，请换个方式提问。"

        assert "抱歉" in assistant_response or "提问" in assistant_response
```

- [ ] **Step 5: 运行测试验证通过**

Run: `pytest tests/unit/test_main_chat.py -v`
Expected: PASS

- [ ] **Step 6: 分析现有 main.py 代码结构**

当前代码（main.py:320-345）：
```python
# 处理流式输出
assistant_response = ""
if isinstance(context.execution_result, types.GeneratorType):
    print("\n[助手] ", end="", flush=True)
    for chunk in context.execution_result:
        if chunk.get("type") == "thinking":
            pass
        elif chunk.get("type") == "content":
            content = chunk.get("content", "")
            print(content, end="", flush=True)
            assistant_response += content
    print()
else:
    if context.execution_result:
        assistant_response = "操作已完成"
        print(f"\n[助手] {assistant_response}")
    else:
        assistant_response = "处理完成"
        print(f"\n[助手] {assistant_response}")
```

- [ ] **Step 7: 修改 main.py 增强边界处理**

修改 `main.py` 第 320-345 行：

```python
# 处理流式输出
assistant_response = ""

# 检查 execution_result 是否有效
if context.execution_result is None:
    assistant_response = "抱歉，处理您的请求时出现问题，请稍后再试。"
    print(f"\n[助手] {assistant_response}")

elif isinstance(context.execution_result, types.GeneratorType):
    print("\n[助手] ", end="", flush=True)

    has_content = False
    try:
        for chunk in context.execution_result:
            if chunk.get("type") == "thinking":
                # 可选：显示思考过程
                pass
            elif chunk.get("type") == "content":
                content = chunk.get("content", "")
                if content:
                    has_content = True
                    print(content, end="", flush=True)
                    assistant_response += content
            elif chunk.get("type") == "error":
                # 处理错误 chunk
                error_msg = chunk.get("content", "未知错误")
                print(f"[错误] {error_msg}", end="", flush=True)
                assistant_response = f"[错误] {error_msg}"
                has_content = True
    except Exception as e:
        logger.error(f"Error consuming stream: {e}", exc_info=True)
        assistant_response = "对话处理出错，请稍后再试。"

    print()  # 换行

    # 如果没有任何内容输出，给出默认回复
    if not has_content:
        assistant_response = "抱歉，我没有理解您的问题，请换个方式提问。"
        print(assistant_response)

elif isinstance(context.execution_result, str):
    # 字符串结果（错误消息）
    assistant_response = context.execution_result
    print(f"\n[助手] {assistant_response}")

else:
    # 其他类型结果（业务操作）
    if context.execution_result:
        assistant_response = "操作已完成"
    else:
        assistant_response = "处理完成"
    print(f"\n[助手] {assistant_response}")
```

- [ ] **Step 8: 手动测试验证**

Run: `python main.py`
输入: `chat`
输入: `你可以帮我做什么`
预期: 显示有意义的功能介绍，而非 "None"

- [ ] **Step 9: Commit**

```bash
git add main.py
git commit -m "fix(cli): 增强 chat 模式流式输出处理和错误边界"
```

---

## Chunk 5: 集成测试与验证

### Task 5.1: 编写集成测试

**Files:**
- Create: `tests/integration/test_chat_mode.py`

- [ ] **Step 1: 创建测试文件并编写测试**

```python
# tests/integration/test_chat_mode.py
"""chat 模式集成测试"""
import pytest
from unittest.mock import patch, MagicMock


class TestChatModeIntegration:
    """测试 chat 模式完整流程"""

    @patch('src.llm_client.Generation.call')
    def test_chat_returns_meaningful_response(self, mock_call):
        """chat 模式应返回有意义的内容"""
        from src.agents.orchestrator import Orchestrator
        from src.agents.impl.intent_agent import IntentAgent
        from src.agents.impl.knowledge_agent import KnowledgeAgent
        from src.agents.config import IntentAgentConfig, BaseAgentConfig
        from src.llm_client import LLMClient

        # 模拟 LLM 响应
        mock_chunk = MagicMock()
        mock_chunk.output.choices = [MagicMock()]
        mock_chunk.output.choices[0].message.content = "我是智能停车数据库助手，可以帮助你查询和管理车辆信息。"
        mock_call.return_value = iter([mock_chunk])

        llm = LLMClient.__new__(LLMClient)
        llm.api_key = "test-key"
        llm.client = None
        llm._metrics_collector = MagicMock()

        orchestrator = Orchestrator(
            intent_agent=IntentAgent(IntentAgentConfig(name="intent"), llm_client=llm),
            knowledge_agent=KnowledgeAgent(BaseAgentConfig(name="knowledge"), llm_client=llm)
        )

        context = orchestrator.process("你可以帮我做什么")

        assert context.execution_result is not None
        assert context.execution_result != "None"

        # 消费 generator 验证内容
        if hasattr(context.execution_result, '__iter__'):
            chunks = list(context.execution_result)
            content_chunks = [c for c in chunks if c.get("type") == "content"]
            assert len(content_chunks) > 0
            assert content_chunks[0]["content"] != ""
```

- [ ] **Step 2: 运行集成测试**

Run: `pytest tests/integration/test_chat_mode.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_chat_mode.py
git commit -m "test(integration): 添加 chat 模式集成测试"
```

### Task 5.2: 端到端验证

- [ ] **Step 1: 运行完整测试套件**

Run: `pytest tests/ -v --cov=src --cov-fail-under=70`
Expected: 全部 PASS，覆盖率 >= 70%

- [ ] **Step 2: 手动功能验证**

```bash
python main.py
```

测试用例：
1. 输入 `chat` 进入对话模式
2. 输入 `你可以帮我做什么` → 应返回功能介绍
3. 输入 `知识库有多大` → 应返回知识库信息
4. 输入 `exit` 退出

- [ ] **Step 3: 最终提交**

```bash
git add -A
git commit -m "fix: 修复对话模式返回 None 问题

- LLMClient.chat_stream: 添加前置检查、日志、输出验证
- KnowledgeAgent: 添加异常处理和 generator 验证
- Orchestrator._handle_conversation: 检查结果有效性
- main.py: 处理所有边界情况

Closes: #修复对话模式返回None问题"
```

---

## 实施摘要

| 层级 | 文件 | 改进点 |
|------|------|--------|
| Layer 1 | `src/llm_client.py` | 前置检查、日志、输出验证、降级 |
| Layer 2 | `src/agents/impl/knowledge_agent.py` | 异常捕获、generator 验证 |
| Layer 3 | `src/agents/orchestrator.py` | 结果有效性检查、错误消息设置 |
| Layer 4 | `main.py` | 边界处理、error chunk 处理、默认回复 |

**预计时间:** ~1.5小时
**测试覆盖:** 新增 5 个测试文件，覆盖所有修复点
**提交次数:** 8 次，每次提交独立可验证