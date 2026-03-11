# Chunk 3: Orchestrator路由增强

> **前置依赖：** [Chunk 2: IntentAgent概念学习增强](./2026-03-11-dialogue-orchestrator-integration-chunk-2.md)
> **后续文件：** [Chunk 4: Main.py统一chat模式](./2026-03-11-dialogue-orchestrator-integration-chunk-4.md)

---

### Task 6: Orchestrator添加chat_history参数支持

**Files:**
- Modify: `src/agents/orchestrator.py`
- Test: `tests/unit/agents/test_orchestrator_routing.py`

- [ ] **Step 1: 写失败测试 - Orchestrator接受chat_history**

```python
# tests/unit/agents/test_orchestrator_routing.py
import pytest
from unittest.mock import MagicMock
from src.agents.orchestrator import Orchestrator
from src.agents.context import AgentContext

def test_orchestrator_process_with_chat_history():
    """测试Orchestrator接受chat_history参数"""
    # Mock agents
    mock_intent = MagicMock()
    mock_intent.run.return_value.success = True

    orch = Orchestrator(intent_agent=mock_intent)

    chat_history = [
        {"role": "user", "content": "之前的问题"},
        {"role": "assistant", "content": "之前的回答"}
    ]

    context = orch.process("新问题", chat_history=chat_history)

    # 验证chat_history被传递到context
    assert len(context.chat_history) == 2
    assert context.chat_history[0]["role"] == "user"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/unit/agents/test_orchestrator_routing.py::test_orchestrator_process_with_chat_history -v`
Expected: FAIL with "process() got an unexpected keyword argument 'chat_history'"

- [ ] **Step 3: 实现Orchestrator.process支持chat_history**

```python
# src/agents/orchestrator.py (修改process方法签名)
def process(
    self,
    user_input: str,
    chat_history: List[Dict] = None,
    user_confirmation: bool | None = None
) -> AgentContext:
    """处理用户输入

    Args:
        user_input: 用户输入文本
        chat_history: 对话历史（可选）
        user_confirmation: 用户确认标志（可选，用于ReviewAgent）

    Returns:
        AgentContext: 包含执行结果的上下文
    """
    context = AgentContext(
        user_input=user_input,
        chat_history=chat_history or []
    )

    # ... (之前的代码)
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/unit/agents/test_orchestrator_routing.py::test_orchestrator_process_with_chat_history -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/agents/orchestrator.py tests/unit/agents/test_orchestrator_routing.py
git commit -m "feat(orchestrator): 添加chat_history参数支持"
```


### Task 7: Orchestrator实现智能路由逻辑

**Files:**
- Modify: `src/agents/orchestrator.py`
- Test: `tests/unit/agents/test_orchestrator_routing.py`

- [ ] **Step 1: 写失败测试 - 对话路由到KnowledgeAgent**

```python
# tests/unit/agents/test_orchestrator_routing.py (追加)
import types

def test_orchestrator_route_chat_to_knowledge_agent():
    """测试Orchestrator将chat意图路由到KnowledgeAgent"""
    # Mock agents
    mock_intent = MagicMock()
    mock_retrieval = MagicMock()
    mock_knowledge = MagicMock()

    # Mock intent返回chat类型
    from src.agents.context import IntentModel
    from src.agents.models import AgentResult

    mock_intent.run.return_value = AgentResult(
        success=True,
        data=IntentModel(type="chat", confidence=0.95, need_clarify=False)
    )

    # Mock knowledge返回generator
    def mock_generator():
        yield {"type": "content", "content": "你好"}

    mock_knowledge.run.return_value = AgentResult(
        success=True,
        data=mock_generator()
    )

    orch = Orchestrator(
        intent_agent=mock_intent,
        retrieval_agent=mock_retrieval,
        knowledge_agent=mock_knowledge
    )

    context = orch.process("你好")

    # 验证路由
    assert "knowledge" in context.step_history
    assert isinstance(context.execution_result, types.GeneratorType)

    # 验证没有调用业务流程的agents
    # (security, preview, review, execution不应该被调用)

def test_orchestrator_route_query_to_business_flow():
    """测试Orchestrator将query意图路由到业务流程"""
    # Mock agents
    mock_intent = MagicMock()
    mock_retrieval = MagicMock()
    mock_security = MagicMock()
    mock_review = MagicMock()
    mock_execution = MagicMock()

    # Mock intent返回query类型
    from src.agents.context import IntentModel
    from src.agents.models import AgentResult

    mock_intent.run.return_value = AgentResult(
        success=True,
        data=IntentModel(
            type="query",
            confidence=0.95,
            need_clarify=False,
            operation_id="plate_query"
        )
    )

    mock_security.run.return_value = AgentResult(success=True)
    mock_review.run.return_value = AgentResult(success=True, next_action="continue")
    mock_execution.run.return_value = AgentResult(success=True)

    orch = Orchestrator(
        intent_agent=mock_intent,
        retrieval_agent=mock_retrieval,
        security_agent=mock_security,
        review_agent=mock_review,
        execution_agent=mock_execution
    )

    context = orch.process("查询车牌")

    # 验证完整业务流程
    assert "intent" in context.step_history
    assert "retrieval" in context.step_history
    assert "security" in context.step_history
    assert "execution" in context.step_history
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/unit/agents/test_orchestrator_routing.py::test_orchestrator_route_chat_to_knowledge_agent -v`
Expected: FAIL with "'knowledge' not in context.step_history"

- [ ] **Step 3: 实现智能路由逻辑**

```python
# src/agents/orchestrator.py (修改process方法)
def process(
    self,
    user_input: str,
    chat_history: List[Dict] = None,
    user_confirmation: bool | None = None
) -> AgentContext:
    context = AgentContext(
        user_input=user_input,
        chat_history=chat_history or []
    )

    # 1. 意图识别
    res = self.intent_agent.run(context)
    if not res.success:
        context.step_history.append("intent_failed")
        return context

    context.step_history.append("intent")

    # 2. 检查是否需要澄清
    if context.intent and context.intent.need_clarify:
        context.pending_clarification = True
        return context

    # 3. 根据意图类型路由
    if context.intent and context.intent.type in ["chat", "qa"]:
        return self._handle_conversation(context)
    elif context.intent and context.intent.type in ["query", "mutation"]:
        return self._handle_business_operation(context, user_confirmation)
    else:
        return context

def _handle_conversation(self, context: AgentContext) -> AgentContext:
    """处理对话和知识问答"""
    # 检索相关schema（可选）
    retrieval_res = self.retrieval_agent.run(context)
    if retrieval_res.success:
        context.step_history.append("retrieval")

    # 流式问答
    knowledge_res = self.knowledge_agent.run(context)
    if not knowledge_res.success:
        context.step_history.append("knowledge_failed")
        return context

    context.execution_result = knowledge_res.data  # generator
    context.step_history.append("knowledge")

    return context

def _handle_business_operation(
    self,
    context: AgentContext,
    user_confirmation: bool | None = None
) -> AgentContext:
    """处理业务操作"""
    # 2. Retrieval
    retrieval_res = self.retrieval_agent.run(context)
    if retrieval_res.success:
        context.step_history.append("retrieval")

    # 3. Security
    if not self.security_agent.run(context).success:
        context.step_history.append("security_failed")
        return context
    context.step_history.append("security")

    # 4. Preview (if mutation)
    if context.intent and context.intent.type == "mutation":
        preview_res = self.preview_agent.run(context)
        if preview_res.success:
            context.step_history.append("preview")

    # 5. Review (if provided)
    if self.review_agent and user_confirmation is not True:
        review_res = self.review_agent.run(context)
        if review_res.next_action == "ask_user":
            context.execution_result = review_res
            context.step_history.append("review")
            return context
        if not review_res.success:
            context.step_history.append("review_failed")
            return context
        context.step_history.append("review")
    elif user_confirmation is True:
        context.step_history.append("review_confirmed")

    # 6. Execution
    self.execution_agent.run(context)
    context.step_history.append("execution")

    return context
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/unit/agents/test_orchestrator_routing.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: 提交**

```bash
git add src/agents/orchestrator.py tests/unit/agents/test_orchestrator_routing.py
git commit -m "feat(orchestrator): 实现智能路由逻辑，支持对话和业务操作分流"
```


### Task 8: Orchestrator处理澄清循环

**Files:**
- Modify: `src/agents/orchestrator.py`
- Test: `tests/unit/agents/test_orchestrator_routing.py`

- [ ] **Step 1: 写失败测试 - 澄清循环处理**

```python
# tests/unit/agents/test_orchestrator_routing.py (追加)
def test_orchestrator_handle_clarification_loop():
    """测试Orchestrator处理澄清循环"""
    # Mock agents
    mock_intent = MagicMock()

    from src.agents.context import IntentModel
    from src.agents.models import AgentResult

    # 第一次调用：需要澄清
    mock_intent.run.return_value = AgentResult(
        success=True,
        data=IntentModel(
            type="clarify",
            confidence=0.0,
            need_clarify=True,
            clarification_question="请问ROI具体指什么？",
            unrecognized_concepts=["ROI"]
        )
    )

    orch = Orchestrator(intent_agent=mock_intent)

    # 第一次处理
    context = orch.process("查询ROI")

    # 验证返回澄清状态
    assert context.pending_clarification is True
    assert context.intent.clarification_question == "请问ROI具体指什么？"
    assert "ROI" in context.intent.unrecognized_concepts

    # 验证没有继续执行后续流程
    assert "retrieval" not in context.step_history
    assert "execution" not in context.step_history
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/unit/agents/test_orchestrator_routing.py::test_orchestrator_handle_clarification_loop -v`
Expected: FAIL (可能已经通过，因为之前实现了部分逻辑)

- [ ] **Step 3: 确认澄清循环逻辑已实现**

检查`src/agents/orchestrator.py`中的process方法，确保包含：

```python
# 2. 检查是否需要澄清
if context.intent and context.intent.need_clarify:
    context.pending_clarification = True
    return context  # 立即返回，不继续执行
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/unit/agents/test_orchestrator_routing.py::test_orchestrator_handle_clarification_loop -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add tests/unit/agents/test_orchestrator_routing.py
git commit -m "test(orchestrator): 添加澄清循环处理测试"
```

---

**Chunk 3 完成！** 继续执行 [Chunk 4: Main.py统一chat模式](./2026-03-11-dialogue-orchestrator-integration-chunk-4.md)