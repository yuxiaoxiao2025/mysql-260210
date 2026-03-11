# Unified Multi-Agent System v2.0 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 构建一个统一的、职责分离的 Multi-Agent 系统，集成 Qwen3 的深度思考与流式输出能力，并引入 ReviewAgent 增强安全性，最终废弃旧的 DialogueEngine。

**Architecture:** Hub-and-Spoke (Orchestrator 中心化调度)，IntentAgent 负责路由与概念学习，KnowledgeAgent 负责流式问答，ReviewAgent 负责执行前确认，ExecutionAgent 负责操作执行。

**Tech Stack:** Python, Qwen3 (Thinking/Streaming), Pydantic

---

### Phase 1: 基础设施增强 (Streaming & Thinking)

**Files:**
- Modify: `src/llm_client.py`
- Modify: `src/agents/models.py`
- Create: `tests/unit/test_llm_client_streaming.py`

**Step 1: Write the failing test for LLMClient streaming**

```python
# tests/unit/test_llm_client_streaming.py
import pytest
from unittest.mock import MagicMock, patch
from src.llm_client import LLMClient

def test_chat_stream_with_thinking():
    client = LLMClient()
    # Mock OpenAI client
    with patch.object(client, 'client') as mock_openai:
        mock_stream = MagicMock()
        # Mock chunks: thinking -> content
        chunk1 = MagicMock()
        chunk1.choices = [MagicMock(delta=MagicMock(reasoning_content="Thinking...", content=None))]
        chunk2 = MagicMock()
        chunk2.choices = [MagicMock(delta=MagicMock(reasoning_content=None, content="Hello"))]
        
        mock_stream.__iter__.return_value = [chunk1, chunk2]
        mock_openai.chat.completions.create.return_value = mock_stream
        
        # Test generator
        generator = client.chat_stream(
            messages=[{"role": "user", "content": "hi"}],
            enable_thinking=True
        )
        
        results = list(generator)
        assert len(results) == 2
        assert results[0]["type"] == "thinking"
        assert results[0]["content"] == "Thinking..."
        assert results[1]["type"] == "content"
        assert results[1]["content"] == "Hello"
        
        # Verify stream_options was passed
        mock_openai.chat.completions.create.assert_called_with(
            model="qwen-plus",
            messages=[{"role": "user", "content": "hi"}],
            stream=True,
            extra_body={"enable_thinking": True},
            stream_options={"include_usage": True}
        )
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_llm_client_streaming.py`

**Step 3: Implement LLMClient streaming support**

In `src/llm_client.py`:
- Add `chat_stream` method handling `enable_thinking`.
- **Crucial:** Set `stream_options={"include_usage": True}` to capture token usage.
- Normalize output to `{"type": "thinking"|"content", "content": str}`.
- Handle DashScope specific `reasoning_content` fields in `delta`.
- Capture `usage` from the final chunk and record metrics.

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_llm_client_streaming.py`

**Step 5: Commit**

```bash
git add src/llm_client.py tests/unit/test_llm_client_streaming.py
git commit -m "feat: add streaming and thinking support to LLMClient"
```

---

### Phase 2: KnowledgeAgent 实现

**Files:**
- Create: `src/agents/impl/knowledge_agent.py`
- Modify: `src/agents/orchestrator.py`
- Create: `tests/unit/agents/impl/test_knowledge_agent.py`

**Step 1: Write the failing test for KnowledgeAgent**

```python
# tests/unit/agents/impl/test_knowledge_agent.py
import pytest
from unittest.mock import MagicMock, patch
from src.agents.impl.knowledge_agent import KnowledgeAgent
from src.agents.context import AgentContext, IntentModel
from src.agents.config import BaseAgentConfig

def test_knowledge_agent_run():
    # Mock LLMClient
    mock_llm = MagicMock()
    mock_llm.chat_stream.return_value = [
        {"type": "thinking", "content": "Thinking..."},
        {"type": "content", "content": "Answer"}
    ]
    
    agent = KnowledgeAgent(BaseAgentConfig(name="knowledge"), llm_client=mock_llm)
    context = AgentContext(user_input="ask something")
    context.intent = IntentModel(type="qa", confidence=1.0)
    context.schema_context = "Table: users"
    
    result = agent.run(context)
    
    assert result.success is True
    # Verify stream generator is returned
    assert hasattr(result.data, "__iter__")
    chunks = list(result.data)
    assert len(chunks) == 2
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/agents/impl/test_knowledge_agent.py`

**Step 3: Implement KnowledgeAgent**

In `src/agents/impl/knowledge_agent.py`:
- Inherit from `BaseAgent`.
- In `_run_impl`, construct system prompt using `context.schema_context`.
- Call `llm_client.chat_stream`.
- Return generator in `AgentResult.data`.

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/agents/impl/test_knowledge_agent.py`

**Step 5: Integrate into Orchestrator**

In `src/agents/orchestrator.py`:
- Add `knowledge_agent` to `__init__`.
- In `process`:
    - Detect `intent.type` in `["qa", "chat"]`.
    - If true, call `retrieval_agent` then `knowledge_agent`.
    - Return `context` with `result.data` (the generator) in `execution_result`.

**Step 6: Commit**

```bash
git add src/agents/impl/knowledge_agent.py src/agents/orchestrator.py tests/unit/agents/impl/test_knowledge_agent.py
git commit -m "feat: implement KnowledgeAgent with streaming support"
```

---

### Phase 3: ReviewAgent 实现

**Files:**
- Create: `src/agents/impl/review_agent.py`
- Modify: `src/agents/config.py`
- Modify: `src/agents/orchestrator.py`
- Create: `tests/unit/agents/impl/test_review_agent.py`

**Step 1: Write the failing test for ReviewAgent**

```python
# tests/unit/agents/impl/test_review_agent.py
from src.agents.impl.review_agent import ReviewAgent
from src.agents.context import AgentContext, IntentModel
from src.agents.config import BaseAgentConfig

def test_review_agent_needs_confirmation():
    agent = ReviewAgent(BaseAgentConfig(name="review"))
    context = AgentContext(user_input="delete users")
    context.intent = IntentModel(type="mutation", sql="DELETE FROM users")
    context.is_safe = True
    
    result = agent.run(context)
    
    # ReviewAgent should mark as needing user confirmation
    assert result.success is True
    assert result.next_action == "ask_user"
    assert "DELETE" in result.message
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/agents/impl/test_review_agent.py`

**Step 3: Implement ReviewAgent**

In `src/agents/impl/review_agent.py`:
- Analyze `context.intent` and `context.preview_data`.
- If mutation or critical operation:
    - Return `AgentResult` with `next_action="ask_user"` and confirmation message.
- If query (and config allows auto-run):
    - Return `success=True`.

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/agents/impl/test_review_agent.py`

**Step 5: Integrate into Orchestrator**

In `src/agents/orchestrator.py`:
- Add `review_agent` before `execution_agent`.
- If `review_agent` returns `next_action="ask_user"`, stop and return context to `main.py` to handle input.

**Step 6: Commit**

```bash
git add src/agents/impl/review_agent.py src/agents/orchestrator.py tests/unit/agents/impl/test_review_agent.py
git commit -m "feat: implement ReviewAgent for pre-execution confirmation"
```

---

### Phase 4: IntentAgent 增强 (Concept Learning)

**Files:**
- Modify: `src/agents/impl/intent_agent.py`
- Modify: `src/agents/context.py`
- Create: `tests/unit/agents/impl/test_intent_agent_learning.py`

**Step 1: Write the failing test for Concept Learning**

```python
# tests/unit/agents/impl/test_intent_agent_learning.py
import pytest
from unittest.mock import MagicMock
from src.agents.impl.intent_agent import IntentAgent
from src.agents.context import AgentContext
from src.agents.config import IntentAgentConfig

def test_intent_agent_clarification():
    mock_recognizer = MagicMock()
    # Simulate unrecognized concept
    mock_recognizer.recognize.return_value.is_matched = False
    mock_recognizer.recognize.return_value.reasoning = "Unknown concept: 'ROI'"
    
    # Inject dependencies
    agent = IntentAgent(IntentAgentConfig(name="intent"), llm_client=MagicMock(), knowledge_loader=MagicMock())
    agent.recognizer = mock_recognizer
    
    context = AgentContext(user_input="Calculate ROI")
    result = agent.run(context)
    
    assert context.intent.need_clarify is True
    assert "ROI" in context.intent.reasoning
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/agents/impl/test_intent_agent_learning.py`

**Step 3: Implement Concept Learning Logic**

In `src/agents/impl/intent_agent.py`:
- Integrate `ConceptStore` (inject via init).
- When `recognizer` fails or returns low confidence:
    - Check for unknown terms.
    - Set `need_clarify=True`.
    - Generate clarification question (using LLM or template).
- Handle user feedback (if `context.chat_history` has clarification context):
    - Learn new concept -> Update `ConceptStore`.
    - Retry recognition.

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/agents/impl/test_intent_agent_learning.py`

**Step 5: Commit**

```bash
git add src/agents/impl/intent_agent.py tests/unit/agents/impl/test_intent_agent_learning.py
git commit -m "feat: enhance IntentAgent with concept learning and clarification flow"
```

---

### Phase 5: Main Loop 集成

**Files:**
- Modify: `main.py`

**Step 1: Update main.py to use streaming Orchestrator**

- Remove `DialogueEngine` loop.
- Use `orchestrator.process()` as the main entry point.
- Handle generator output from `KnowledgeAgent` (print chunks in real-time).
- Handle `ReviewAgent`'s `ask_user` request (prompt user and call orchestrator again with confirmation).

**Step 2: Verify manually**

Run: `python main.py --agent-mode`
- Test: "你现在知识库有哪些内容" (Expect streaming output)
- Test: "删除所有用户" (Expect review confirmation)

**Step 3: Commit**

```bash
git add main.py
git commit -m "refactor: switch main loop to unified streaming orchestrator"
```
