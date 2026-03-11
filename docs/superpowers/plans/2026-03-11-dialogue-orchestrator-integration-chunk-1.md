# Chunk 1: 数据模型增强

> **前置依赖：** 无
> **后续文件：** [Chunk 2: IntentAgent概念学习增强](./2026-03-11-dialogue-orchestrator-integration-chunk-2.md)

---

### Task 1: 增强AgentContext支持对话历史

**Files:**
- Modify: `src/agents/context.py`
- Test: `tests/unit/agents/test_context.py`

- [ ] **Step 1: 写失败测试 - AgentContext对话历史**

```python
# tests/unit/agents/test_context.py
import pytest
from src.agents.context import AgentContext
from src.memory.concept_store import ConceptMapping

def test_agent_context_chat_history():
    """测试AgentContext支持chat_history"""
    context = AgentContext(
        user_input="你好",
        chat_history=[
            {"role": "user", "content": "之前的问题"},
            {"role": "assistant", "content": "之前的回答"}
        ]
    )
    assert len(context.chat_history) == 2
    assert context.chat_history[0]["role"] == "user"

def test_agent_context_pending_clarification():
    """测试AgentContext支持pending_clarification标志"""
    context = AgentContext(user_input="查询ROI")
    assert context.pending_clarification is False

    context.pending_clarification = True
    assert context.pending_clarification is True

def test_agent_context_learned_concepts():
    """测试AgentContext支持learned_concepts列表"""
    context = AgentContext(user_input="测试")
    assert context.learned_concepts == []

    concept = ConceptMapping(
        concept_id="test_concept",
        user_terms=["ROI"],
        database_mapping={"meaning": "投资回报率"},
        description="投资回报率"
    )
    context.learned_concepts.append(concept)
    assert len(context.learned_concepts) == 1
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/unit/agents/test_context.py::test_agent_context_chat_history -v`
Expected: FAIL with "AgentContext has no attribute 'chat_history'"

- [ ] **Step 3: 实现AgentContext增强**

```python
# src/agents/context.py
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
import uuid
from src.memory.concept_store import ConceptMapping

class AgentContext(BaseModel):
    user_input: str
    chat_history: List[Dict[str, str]] = Field(default_factory=list)

    # Agent间传递的数据
    intent: Optional[Any] = None  # IntentModel
    schema_context: Optional[str] = None
    is_safe: bool = False
    preview_data: Optional[Any] = None
    execution_result: Optional[Any] = None

    # 概念学习状态
    learned_concepts: List[ConceptMapping] = Field(default_factory=list)
    pending_clarification: bool = False

    # 审计和调试
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    step_history: List[str] = Field(default_factory=list)
    audit_log: List[str] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/unit/agents/test_context.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: 提交**

```bash
git add src/agents/context.py tests/unit/agents/test_context.py
git commit -m "feat(agents): 增强AgentContext支持对话历史和概念学习状态"
```


### Task 2: 增强IntentModel支持澄清问题

**Files:**
- Modify: `src/agents/context.py`
- Test: `tests/unit/agents/test_context.py`

- [ ] **Step 1: 写失败测试 - IntentModel澄清字段**

```python
# tests/unit/agents/test_context.py (追加)
from src.agents.context import IntentModel

def test_intent_model_clarification_fields():
    """测试IntentModel支持澄清相关字段"""
    intent = IntentModel(
        type="query",
        confidence=0.5,
        need_clarify=True,
        clarification_question="请问ROI具体指什么？",
        unrecognized_concepts=["ROI"]
    )

    assert intent.need_clarify is True
    assert intent.clarification_question == "请问ROI具体指什么？"
    assert "ROI" in intent.unrecognized_concepts
    assert len(intent.unrecognized_concepts) == 1
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/unit/agents/test_context.py::test_intent_model_clarification_fields -v`
Expected: FAIL with "IntentModel has no attribute 'clarification_question'"

- [ ] **Step 3: 实现IntentModel增强**

```python
# src/agents/context.py (修改IntentModel)
from typing import Literal

class IntentModel(BaseModel):
    type: Literal["query", "mutation", "chat", "qa", "clarify"]
    confidence: float
    operation_id: Optional[str] = None
    params: Dict[str, Any] = Field(default_factory=dict)
    sql: Optional[str] = None
    reasoning: str = ""

    # 概念学习相关
    need_clarify: bool = False
    clarification_question: Optional[str] = None
    unrecognized_concepts: List[str] = Field(default_factory=list)
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/unit/agents/test_context.py::test_intent_model_clarification_fields -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/agents/context.py tests/unit/agents/test_context.py
git commit -m "feat(agents): 增强IntentModel支持澄清问题和未识别概念"
```

---

**Chunk 1 完成！** 继续执行 [Chunk 2: IntentAgent概念学习增强](./2026-03-11-dialogue-orchestrator-integration-chunk-2.md)