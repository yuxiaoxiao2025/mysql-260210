# 对话引擎与多智能体架构融合实施计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将DialogueEngine的概念学习能力整合到IntentAgent和Orchestrator中，实现统一的对话和业务操作处理流程，废弃DialogueEngine作为独立组件。

**Architecture:** 采用分阶段迁移策略，先增强IntentAgent和Orchestrator，再统一main.py的chat模式，最后清理废弃代码。每个阶段保持向后兼容，确保现有功能不受影响。

**Tech Stack:** Python 3.10+, Pydantic, Pytest, TDD

---

## 文件结构规划

### 需要修改的文件

**数据模型增强：**
- `src/agents/context.py` - 添加chat_history、pending_clarification、learned_concepts字段
- `src/agents/models.py` - IntentModel添加clarification_question、unrecognized_concepts字段

**IntentAgent增强：**
- `src/agents/impl/intent_agent.py` - 添加概念识别和学习逻辑
- `src/agents/config.py` - 添加IntentAgentConfig的concept_store配置

**Orchestrator增强：**
- `src/agents/orchestrator.py` - 添加chat_history参数、智能路由、澄清循环处理

**Main.py统一：**
- `main.py` - 修改chat模式，使用Orchestrator替代DialogueEngine

### 需要创建的测试文件

- `tests/unit/agents/impl/test_intent_agent_concept_learning.py` - IntentAgent概念学习测试
- `tests/unit/agents/test_orchestrator_routing.py` - Orchestrator路由测试
- `tests/integration/test_dialogue_orchestrator_integration.py` - 完整流程集成测试

### 需要删除的文件（阶段4）

- `src/dialogue/dialogue_engine.py` - DialogueEngine、DialogueState、DialogueResponse

---

## Chunk 1: 数据模型增强

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

## Chunk 2: IntentAgent概念学习增强

### Task 3: IntentAgent添加概念识别依赖

**Files:**
- Modify: `src/agents/impl/intent_agent.py`
- Test: `tests/unit/agents/impl/test_intent_agent_concept_learning.py`

- [ ] **Step 1: 写失败测试 - IntentAgent初始化概念识别器**

```python
# tests/unit/agents/impl/test_intent_agent_concept_learning.py
import pytest
from unittest.mock import MagicMock
from src.agents.impl.intent_agent import IntentAgent
from src.agents.config import IntentAgentConfig
from src.agents.context import AgentContext

def test_intent_agent_init_with_concept_store():
    """测试IntentAgent可以接受concept_store参数"""
    mock_llm = MagicMock()
    mock_knowledge = MagicMock()
    mock_concept_store = MagicMock()
    
    config = IntentAgentConfig(name="intent")
    agent = IntentAgent(
        config=config,
        llm_client=mock_llm,
        knowledge_loader=mock_knowledge,
        concept_store=mock_concept_store
    )
    
    assert agent.concept_store is mock_concept_store
    assert hasattr(agent, 'concept_recognizer')
    assert hasattr(agent, 'question_generator')
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/unit/agents/impl/test_intent_agent_concept_learning.py::test_intent_agent_init_with_concept_store -v`
Expected: FAIL with "IntentAgent.__init__() got an unexpected keyword argument 'concept_store'"

- [ ] **Step 3: 实现IntentAgent初始化增强**

```python
# src/agents/impl/intent_agent.py (修改__init__)
from src.dialogue.concept_recognizer import ConceptRecognizer
from src.dialogue.question_generator import QuestionGenerator
from src.memory.concept_store import ConceptStoreService

class IntentAgent(BaseAgent):
    def __init__(
        self, 
        config: IntentAgentConfig, 
        llm_client=None, 
        knowledge_loader=None,
        concept_store: Optional[ConceptStoreService] = None
    ):
        super().__init__(config)
        self.llm_client = llm_client
        self.concept_store = concept_store
        self.recognizer = IntentRecognizer(llm_client, knowledge_loader)
        
        # 概念学习组件（可选）
        if concept_store:
            self.concept_recognizer = ConceptRecognizer(concept_store)
            self.question_generator = QuestionGenerator()
        else:
            self.concept_recognizer = None
            self.question_generator = None
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/unit/agents/impl/test_intent_agent_concept_learning.py::test_intent_agent_init_with_concept_store -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/agents/impl/intent_agent.py tests/unit/agents/impl/test_intent_agent_concept_learning.py
git commit -m "feat(intent-agent): 添加concept_store依赖和概念识别器初始化"
```


### Task 4: IntentAgent实现概念识别逻辑

**Files:**
- Modify: `src/agents/impl/intent_agent.py`
- Test: `tests/unit/agents/impl/test_intent_agent_concept_learning.py`

- [ ] **Step 1: 写失败测试 - 识别未知概念并生成澄清问题**

```python
# tests/unit/agents/impl/test_intent_agent_concept_learning.py (追加)
from src.dialogue.concept_recognizer import RecognizedConcept

def test_intent_agent_recognize_unknown_concept():
    """测试IntentAgent识别未知概念并生成澄清问题"""
    mock_llm = MagicMock()
    mock_knowledge = MagicMock()
    mock_concept_store = MagicMock()
    
    # Mock concept_recognizer返回未知概念
    config = IntentAgentConfig(name="intent")
    agent = IntentAgent(config, mock_llm, mock_knowledge, mock_concept_store)
    
    # Mock recognize方法
    unknown_concept = RecognizedConcept(
        term="ROI",
        matched_concept_id=None,
        needs_clarification=True,
        confidence=0.0
    )
    agent.concept_recognizer.recognize = MagicMock(return_value=[unknown_concept])
    
    # Mock question_generator
    from src.dialogue.question_generator import ClarificationQuestion
    question = ClarificationQuestion(
        concept_term="ROI",
        question="请问ROI具体指什么？",
        options=["投资回报率", "其他含义"]
    )
    agent.question_generator.generate_clarification_question = MagicMock(return_value=question)
    
    # 执行
    context = AgentContext(user_input="查询ROI")
    result = agent.run(context)
    
    # 验证
    assert result.success is True
    assert context.intent.need_clarify is True
    assert context.intent.clarification_question == "请问ROI具体指什么？"
    assert "ROI" in context.intent.unrecognized_concepts
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/unit/agents/impl/test_intent_agent_concept_learning.py::test_intent_agent_recognize_unknown_concept -v`
Expected: FAIL with "context.intent.need_clarify is False"

- [ ] **Step 3: 实现概念识别逻辑**

```python
# src/agents/impl/intent_agent.py (修改_run_impl)
def _run_impl(self, context: AgentContext) -> AgentResult:
    # 1. 如果启用了概念学习，先识别概念
    if self.concept_recognizer:
        concepts = self.concept_recognizer.recognize(context.user_input)
        unrecognized = [c for c in concepts if c.needs_clarification]
        
        # 如果有未识别概念，生成澄清问题
        if unrecognized:
            return self._generate_clarification(context, unrecognized)
    
    # 2. 正常意图识别
    recognized = self.recognizer.recognize(context.user_input)
    
    # 3. 推断意图类型
    intent_type = self._infer_intent_type(recognized.operation_id)
    
    # 4. 判断是否需要澄清
    need_clarify = bool(
        not recognized.is_matched
        or recognized.missing_params
        or recognized.confidence < self.config.confidence_threshold
    )
    
    # 5. 提取未知术语
    reasoning = recognized.reasoning or ""
    unknown_term = self._extract_unknown_term(reasoning)
    if unknown_term:
        need_clarify = True
        reasoning = f"{reasoning}。请问"{unknown_term}"具体指什么？"
    
    # 6. 映射到IntentModel
    context.intent = IntentModel(
        type=intent_type,
        confidence=recognized.confidence,
        params=recognized.params,
        operation_id=recognized.operation_id,
        reasoning=reasoning,
        sql=recognized.fallback_sql,
        need_clarify=need_clarify
    )
    
    return AgentResult(success=True, data=context.intent)

def _generate_clarification(self, context: AgentContext, unrecognized: list) -> AgentResult:
    """生成澄清问题"""
    # 只处理第一个未识别概念
    first_concept = unrecognized[0]
    question = self.question_generator.generate_clarification_question(first_concept)
    
    context.intent = IntentModel(
        type="clarify",
        confidence=0.0,
        need_clarify=True,
        clarification_question=question.question,
        unrecognized_concepts=[c.term for c in unrecognized],
        reasoning=f"发现未识别概念: {first_concept.term}"
    )
    
    return AgentResult(success=True, data=context.intent)
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/unit/agents/impl/test_intent_agent_concept_learning.py::test_intent_agent_recognize_unknown_concept -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/agents/impl/intent_agent.py tests/unit/agents/impl/test_intent_agent_concept_learning.py
git commit -m "feat(intent-agent): 实现概念识别和澄清问题生成逻辑"
```


### Task 5: IntentAgent实现概念学习逻辑

**Files:**
- Modify: `src/agents/impl/intent_agent.py`
- Test: `tests/unit/agents/impl/test_intent_agent_concept_learning.py`

- [ ] **Step 1: 写失败测试 - 从澄清回答中学习概念**

```python
# tests/unit/agents/impl/test_intent_agent_concept_learning.py (追加)
def test_intent_agent_learn_from_clarification():
    """测试IntentAgent从澄清回答中学习概念"""
    mock_llm = MagicMock()
    mock_knowledge = MagicMock()
    mock_concept_store = MagicMock()
    
    config = IntentAgentConfig(name="intent")
    agent = IntentAgent(config, mock_llm, mock_knowledge, mock_concept_store)
    
    # 模拟澄清对话历史
    context = AgentContext(
        user_input="投资回报率",
        chat_history=[
            {"role": "assistant", "content": "请问ROI具体指什么？"},
            {"role": "user", "content": "投资回报率"}
        ]
    )
    
    # Mock recognizer返回正常意图
    mock_recognized = MagicMock()
    mock_recognized.operation_id = "plate_query"
    mock_recognized.is_matched = True
    mock_recognized.confidence = 0.9
    mock_recognized.params = {}
    mock_recognized.missing_params = []
    mock_recognized.reasoning = ""
    mock_recognized.fallback_sql = None
    agent.recognizer.recognize = MagicMock(return_value=mock_recognized)
    
    # 执行
    result = agent.run(context)
    
    # 验证概念已学习
    mock_concept_store.add_concept.assert_called_once()
    call_args = mock_concept_store.add_concept.call_args[0][0]
    assert "ROI" in call_args.user_terms
    assert "投资回报率" in call_args.description
    
    # 验证意图识别成功
    assert result.success is True
    assert context.intent.need_clarify is False
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/unit/agents/impl/test_intent_agent_concept_learning.py::test_intent_agent_learn_from_clarification -v`
Expected: FAIL with "mock_concept_store.add_concept not called"

- [ ] **Step 3: 实现概念学习逻辑**

```python
# src/agents/impl/intent_agent.py (在_run_impl开头添加)
def _run_impl(self, context: AgentContext) -> AgentResult:
    # 0. 检查是否是澄清回答
    if self.concept_store and self._is_clarification_response(context):
        self._handle_clarification(context)
        # 继续正常意图识别
    
    # 1. 如果启用了概念学习，先识别概念
    # ... (之前的代码)

def _is_clarification_response(self, context: AgentContext) -> bool:
    """检查是否是澄清回答"""
    if not context.chat_history or len(context.chat_history) < 2:
        return False
    
    # 检查最后一条助手消息是否包含澄清问题
    last_assistant_msg = None
    for msg in reversed(context.chat_history):
        if msg.get("role") == "assistant":
            last_assistant_msg = msg.get("content", "")
            break
    
    if not last_assistant_msg:
        return False
    
    # 简单判断：包含"请问"、"具体指"等关键词
    clarification_keywords = ["请问", "具体指", "是指", "指的是"]
    return any(kw in last_assistant_msg for kw in clarification_keywords)

def _handle_clarification(self, context: AgentContext) -> None:
    """处理澄清回答，学习概念"""
    # 从chat_history中提取概念术语
    last_assistant_msg = ""
    for msg in reversed(context.chat_history):
        if msg.get("role") == "assistant":
            last_assistant_msg = msg.get("content", "")
            break
    
    # 提取概念术语（简单实现：提取引号中的内容）
    import re
    matches = re.findall(r'["""](.*?)["""]', last_assistant_msg)
    if not matches:
        return
    
    concept_term = matches[0]
    user_explanation = context.user_input
    
    # 创建新概念
    from src.memory.concept_store import ConceptMapping
    new_concept = ConceptMapping(
        concept_id=f"learned_{concept_term}",
        user_terms=[concept_term],
        database_mapping={"meaning": user_explanation},
        description=user_explanation,
        learned_from="dialogue"
    )
    
    # 保存到concept_store
    self.concept_store.add_concept(new_concept)
    context.learned_concepts.append(new_concept)
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/unit/agents/impl/test_intent_agent_concept_learning.py::test_intent_agent_learn_from_clarification -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/agents/impl/intent_agent.py tests/unit/agents/impl/test_intent_agent_concept_learning.py
git commit -m "feat(intent-agent): 实现从澄清回答中学习概念的逻辑"
```

---

## Chunk 3: Orchestrator路由增强

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

## Chunk 4: Main.py统一chat模式

### Task 9: Main.py修改chat模式使用Orchestrator

**Files:**
- Modify: `main.py`
- Test: 手工测试

- [ ] **Step 1: 备份当前chat模式实现**

```bash
# 创建备份分支
git checkout -b backup-dialogue-engine
git checkout main
```

- [ ] **Step 2: 修改main.py的chat模式**

```python
# main.py (找到chat模式的代码，大约在259-297行)
# 替换为以下实现：

# 新增：chat 命令 - 进入对话模式（使用Orchestrator）
if user_input.lower() == 'chat':
    print("\n" + "=" * 60)
    print("进入对话模式")
    print("你好，我是你的停车数据库助手，有什么可以帮你？")
    print("输入 'exit' 或 'quit' 退出对话模式")
    print("=" * 60)

    chat_history = []

    while True:
        try:
            chat_input = input("\n[对话] > ").strip()
            if not chat_input:
                continue

            if chat_input.lower() in ['exit', 'quit', '退出']:
                print("退出对话模式")
                break

            # 使用Orchestrator处理输入
            context = orchestrator.process(chat_input, chat_history)

            # 处理澄清
            if context.pending_clarification:
                print(f"\n[助手] {context.intent.clarification_question}")
                chat_history.append({
                    "role": "assistant",
                    "content": context.intent.clarification_question
                })
                chat_history.append({
                    "role": "user",
                    "content": chat_input
                })
                continue

            # 处理确认（ReviewAgent）
            if context.step_history and "review" in context.step_history:
                from src.agents.models import AgentResult
                if isinstance(context.execution_result, AgentResult):
                    if context.execution_result.next_action == "ask_user":
                        print(f"\n[助手] {context.execution_result.message}")
                        confirm = input("确认执行？(y/n) > ").strip().lower()
                        if confirm == 'y':
                            context = orchestrator.process(
                                chat_input,
                                chat_history,
                                user_confirmation=True
                            )
                        else:
                            print("[助手] 已取消操作")
                            continue

            # 处理流式输出
            import types
            if isinstance(context.execution_result, types.GeneratorType):
                print("\n[助手] ", end="", flush=True)
                for chunk in context.execution_result:
                    if chunk.get("type") == "thinking":
                        # 可选：显示思考过程
                        pass
                    elif chunk.get("type") == "content":
                        print(chunk.get("content", ""), end="", flush=True)
                print()  # 换行
            else:
                # 非流式结果（业务操作）
                if context.execution_result:
                    print(f"\n[助手] 操作已完成")
                else:
                    print(f"\n[助手] 处理完成")

            # 更新对话历史
            chat_history.append({"role": "user", "content": chat_input})

        except KeyboardInterrupt:
            print("\n退出对话模式")
            break
        except Exception as e:
            logger.error(f"对话模式错误: {e}", exc_info=True)
            print(f"[ERR] 对话出错: {e}")

    print("=" * 60)
    continue
```

- [ ] **Step 3: 确保Orchestrator在main.py中正确初始化**

检查main.py中orchestrator的初始化，确保包含concept_store：

```python
# main.py (在orchestrator初始化部分)
from src.agents.orchestrator import Orchestrator

# 初始化Orchestrator（确保传入concept_store）
orchestrator = Orchestrator(
    llm_client=llm_client,
    knowledge_loader=knowledge_loader
)

# 为IntentAgent注入concept_store
orchestrator.intent_agent.concept_store = concept_store
orchestrator.intent_agent.concept_recognizer = ConceptRecognizer(concept_store)
orchestrator.intent_agent.question_generator = QuestionGenerator()
```

- [ ] **Step 4: 手工测试chat模式**

Run: `python main.py`

测试场景1：普通对话
```
[MySQL/AI] > chat
[对话] > 你可以正常和我对话吗
期望：流式输出友好回复
```

测试场景2：知识问答
```
[对话] > 数据库有哪些表？
期望：基于schema流式回答
```

测试场景3：概念学习
```
[对话] > 查询ROI
期望：询问"ROI具体指什么？"
[对话] > 投资回报率
期望：学习概念并继续
```

- [ ] **Step 5: 提交**

```bash
git add main.py
git commit -m "feat(main): 统一chat模式使用Orchestrator，支持对话、澄清和业务操作"
```


---

## Chunk 5: 集成测试和清理

### Task 10: 添加完整流程集成测试

**Files:**
- Create: `tests/integration/test_dialogue_orchestrator_integration.py`

- [ ] **Step 1: 写集成测试 - 完整对话流程**

```python
# tests/integration/test_dialogue_orchestrator_integration.py
import pytest
import types
from unittest.mock import patch, MagicMock
from src.agents.orchestrator import Orchestrator
from src.llm_client import LLMClient
from src.knowledge.knowledge_loader import KnowledgeLoader
from src.memory.concept_store import ConceptStoreService

@pytest.fixture
def orchestrator_with_mocks():
    """创建带mock的Orchestrator用于集成测试"""
    mock_llm = MagicMock(spec=LLMClient)
    mock_knowledge = MagicMock(spec=KnowledgeLoader)
    mock_concept_store = MagicMock(spec=ConceptStoreService)
    
    orch = Orchestrator(
        llm_client=mock_llm,
        knowledge_loader=mock_knowledge
    )
    
    # 注入concept_store
    orch.intent_agent.concept_store = mock_concept_store
    
    return orch, mock_llm, mock_knowledge, mock_concept_store

def test_full_conversation_flow(orchestrator_with_mocks):
    """测试完整对话流程：普通对话 -> 知识问答 -> 业务操作"""
    orch, mock_llm, mock_knowledge, mock_concept_store = orchestrator_with_mocks
    
    # 场景1：普通对话
    # Mock IntentRecognizer识别为chat
    with patch.object(orch.intent_agent.recognizer, 'recognize') as mock_recognize:
        mock_result = MagicMock()
        mock_result.operation_id = "general_chat"
        mock_result.is_matched = True
        mock_result.confidence = 0.95
        mock_result.params = {}
        mock_result.missing_params = []
        mock_result.reasoning = ""
        mock_result.fallback_sql = None
        mock_recognize.return_value = mock_result
        
        # Mock KnowledgeAgent返回generator
        def mock_generator():
            yield {"type": "content", "content": "你好！"}
        
        with patch.object(orch.knowledge_agent, '_run_impl') as mock_knowledge_run:
            from src.agents.models import AgentResult
            mock_knowledge_run.return_value = AgentResult(
                success=True,
                data=mock_generator()
            )
            
            context = orch.process("你好")
            
            assert "knowledge" in context.step_history
            assert isinstance(context.execution_result, types.GeneratorType)
            
            # 消费generator
            chunks = list(context.execution_result)
            assert len(chunks) > 0

def test_concept_learning_flow(orchestrator_with_mocks):
    """测试概念学习流程：未知概念 -> 澄清 -> 学习 -> 继续"""
    orch, mock_llm, mock_knowledge, mock_concept_store = orchestrator_with_mocks
    
    # 第一次：触发澄清
    from src.dialogue.concept_recognizer import RecognizedConcept
    unknown_concept = RecognizedConcept(
        term="ROI",
        matched_concept_id=None,
        needs_clarification=True,
        confidence=0.0
    )
    
    with patch.object(orch.intent_agent.concept_recognizer, 'recognize') as mock_recog:
        mock_recog.return_value = [unknown_concept]
        
        from src.dialogue.question_generator import ClarificationQuestion
        question = ClarificationQuestion(
            concept_term="ROI",
            question="请问ROI具体指什么？",
            options=["投资回报率", "其他"]
        )
        
        with patch.object(orch.intent_agent.question_generator, 'generate_clarification_question') as mock_gen:
            mock_gen.return_value = question
            
            context = orch.process("查询ROI")
            
            assert context.pending_clarification is True
            assert "ROI" in context.intent.unrecognized_concepts
    
    # 第二次：学习并继续
    chat_history = [
        {"role": "assistant", "content": "请问ROI具体指什么？"},
        {"role": "user", "content": "投资回报率"}
    ]
    
    with patch.object(orch.intent_agent.recognizer, 'recognize') as mock_recognize:
        mock_result = MagicMock()
        mock_result.operation_id = "plate_query"
        mock_result.is_matched = True
        mock_result.confidence = 0.9
        mock_result.params = {}
        mock_result.missing_params = []
        mock_result.reasoning = ""
        mock_result.fallback_sql = "SELECT * FROM plates"
        mock_recognize.return_value = mock_result
        
        context = orch.process("投资回报率", chat_history=chat_history)
        
        # 验证概念已学习
        mock_concept_store.add_concept.assert_called()
        
        # 验证继续执行业务流程
        assert context.pending_clarification is False
        assert "execution" in context.step_history

def test_business_operation_flow(orchestrator_with_mocks):
    """测试业务操作流程：query -> retrieval -> security -> execution"""
    orch, mock_llm, mock_knowledge, mock_concept_store = orchestrator_with_mocks
    
    with patch.object(orch.intent_agent.recognizer, 'recognize') as mock_recognize:
        mock_result = MagicMock()
        mock_result.operation_id = "plate_query"
        mock_result.is_matched = True
        mock_result.confidence = 0.95
        mock_result.params = {"plate": "沪A12345"}
        mock_result.missing_params = []
        mock_result.reasoning = ""
        mock_result.fallback_sql = "SELECT * FROM plates WHERE plate='沪A12345'"
        mock_recognize.return_value = mock_result
        
        context = orch.process("查询车牌沪A12345")
        
        # 验证完整业务流程
        assert "intent" in context.step_history
        assert "retrieval" in context.step_history
        assert "security" in context.step_history
        assert "execution" in context.step_history
```

- [ ] **Step 2: 运行集成测试**

Run: `pytest tests/integration/test_dialogue_orchestrator_integration.py -v`
Expected: PASS (3 tests)

- [ ] **Step 3: 提交**

```bash
git add tests/integration/test_dialogue_orchestrator_integration.py
git commit -m "test(integration): 添加对话引擎与Orchestrator集成的完整流程测试"
```


### Task 11: 回归测试确保无破坏性变更

**Files:**
- Test: 运行所有现有测试

- [ ] **Step 1: 运行所有单元测试**

Run: `pytest tests/unit -v`
Expected: 所有测试通过（或已知失败的测试保持失败状态）

- [ ] **Step 2: 运行所有集成测试**

Run: `pytest tests/integration -v`
Expected: 所有测试通过

- [ ] **Step 3: 检查测试覆盖率**

Run: `pytest --cov=src/agents --cov-report=term-missing tests/`
Expected: agents模块覆盖率 > 80%

- [ ] **Step 4: 如果有失败测试，修复并重新运行**

如果有测试失败：
1. 分析失败原因
2. 修复代码或更新测试
3. 重新运行测试确保通过
4. 提交修复

```bash
git add <修复的文件>
git commit -m "fix: 修复回归测试中发现的问题"
```

- [ ] **Step 5: 提交回归测试通过的记录**

```bash
# 创建测试报告
pytest tests/ --html=test-report.html --self-contained-html

git add test-report.html
git commit -m "test: 回归测试通过，确认无破坏性变更"
```

### Task 12: 删除DialogueEngine废弃代码

**Files:**
- Delete: `src/dialogue/dialogue_engine.py`中的DialogueEngine、DialogueState、DialogueResponse类
- Modify: `src/dialogue/__init__.py`

- [ ] **Step 1: 检查DialogueEngine的引用**

Run: `grep -r "DialogueEngine" src/ tests/ main.py`
Expected: 只在main.py的注释或已删除的代码中出现

- [ ] **Step 2: 删除DialogueEngine相关类**

```python
# src/dialogue/dialogue_engine.py
# 删除以下类：
# - DialogueState
# - DialogueResponse  
# - DialogueEngine

# 保留文件，但清空内容，添加废弃说明：
"""
dialogue_engine.py - DEPRECATED

This module has been deprecated. The functionality has been integrated into:
- IntentAgent: Concept recognition and learning
- Orchestrator: Dialogue flow management

For migration guide, see: docs/superpowers/specs/2026-03-11-dialogue-orchestrator-integration-design.md
"""
```

- [ ] **Step 3: 更新dialogue模块的__init__.py**

```python
# src/dialogue/__init__.py
# 移除DialogueEngine相关的导出

from src.dialogue.concept_recognizer import ConceptRecognizer, RecognizedConcept
from src.dialogue.question_generator import QuestionGenerator, ClarificationQuestion

# DialogueEngine已废弃，请使用Orchestrator
# from src.dialogue.dialogue_engine import DialogueEngine  # DEPRECATED

__all__ = [
    "ConceptRecognizer",
    "RecognizedConcept",
    "QuestionGenerator",
    "ClarificationQuestion",
]
```

- [ ] **Step 4: 运行测试确保删除不影响功能**

Run: `pytest tests/ -v`
Expected: 所有测试通过

- [ ] **Step 5: 提交**

```bash
git add src/dialogue/dialogue_engine.py src/dialogue/__init__.py
git commit -m "refactor: 废弃DialogueEngine，功能已整合到IntentAgent和Orchestrator"
```

### Task 13: 更新文档

**Files:**
- Create: `docs/migration/dialogue-engine-to-orchestrator.md`
- Modify: `README.md`

- [ ] **Step 1: 创建迁移指南**

```markdown
# docs/migration/dialogue-engine-to-orchestrator.md

# DialogueEngine迁移指南

## 概述

DialogueEngine已被废弃，其功能已整合到多智能体架构中：
- **概念学习** → IntentAgent
- **对话流程管理** → Orchestrator
- **流式输出** → KnowledgeAgent

## 迁移步骤

### 旧代码（使用DialogueEngine）

```python
from src.dialogue.dialogue_engine import DialogueEngine

dialogue_engine = DialogueEngine(
    concept_store=concept_store,
    context_memory=context_memory
)

response = dialogue_engine.process_input(user_input)
print(response.message)
```

### 新代码（使用Orchestrator）

```python
from src.agents.orchestrator import Orchestrator

orchestrator = Orchestrator(
    llm_client=llm_client,
    knowledge_loader=knowledge_loader
)

# 注入concept_store到IntentAgent
orchestrator.intent_agent.concept_store = concept_store

# 处理输入
context = orchestrator.process(user_input, chat_history)

# 处理澄清
if context.pending_clarification:
    print(context.intent.clarification_question)
    # 等待用户回答...

# 处理流式输出
if isinstance(context.execution_result, types.GeneratorType):
    for chunk in context.execution_result:
        if chunk["type"] == "content":
            print(chunk["content"], end="", flush=True)
```

## 功能对照表

| DialogueEngine | 新架构 | 说明 |
|----------------|--------|------|
| `process_input()` | `Orchestrator.process()` | 统一入口 |
| `DialogueState.CLARIFYING` | `context.pending_clarification` | 澄清状态 |
| `DialogueResponse.message` | `context.intent.clarification_question` | 澄清问题 |
| `DialogueResponse.options` | `context.intent.unrecognized_concepts` | 未识别概念 |
| `_learn_concept()` | `IntentAgent._handle_clarification()` | 概念学习 |
| `reset()` | 创建新的chat_history | 重置对话 |

## 优势

1. **职责清晰**：每个Agent专注单一职责
2. **易于测试**：可独立测试每个Agent
3. **易于扩展**：可单独升级某个Agent的模型或逻辑
4. **统一流程**：对话和业务操作使用同一套架构

## 常见问题

**Q: 如何保持对话历史？**
A: 使用`chat_history`参数传递给`Orchestrator.process()`

**Q: 如何处理多轮澄清？**
A: 检查`context.pending_clarification`，如果为True则继续澄清循环

**Q: 如何获取流式输出？**
A: `context.execution_result`是generator，直接迭代即可

## 相关文档

- [设计文档](../superpowers/specs/2026-03-11-dialogue-orchestrator-integration-design.md)
- [实施计划](../superpowers/plans/2026-03-11-dialogue-orchestrator-integration.md)
```

- [ ] **Step 2: 更新README.md**

在README.md中添加架构说明：

```markdown
## 架构

本项目采用多智能体架构，通过Orchestrator协调各个专业Agent：

- **IntentAgent**: 意图识别、概念学习
- **RetrievalAgent**: Schema检索
- **KnowledgeAgent**: 知识问答（流式）
- **SecurityAgent**: SQL安全检查
- **PreviewAgent**: 变更预览
- **ReviewAgent**: 执行前确认
- **ExecutionAgent**: 操作执行

详见：[架构设计文档](docs/superpowers/specs/2026-03-11-dialogue-orchestrator-integration-design.md)
```

- [ ] **Step 3: 提交**

```bash
git add docs/migration/dialogue-engine-to-orchestrator.md README.md
git commit -m "docs: 添加DialogueEngine迁移指南和架构说明"
```

---

## 验收标准

### 功能验收

- [ ] 用户输入"你可以正常和我对话吗"，系统流式输出友好回复
- [ ] 用户输入"数据库有哪些表"，系统基于schema回答
- [ ] 用户输入未知概念（如"ROI"），系统询问并学习
- [ ] 用户输入业务操作，系统正常执行
- [ ] 用户输入变更操作，系统要求确认

### 性能验收

- [ ] 流式输出首token延迟 < 2秒
- [ ] 概念学习后，相同概念识别成功率 > 95%
- [ ] 意图路由准确率 > 90%

### 代码质量验收

- [ ] 单元测试覆盖率 > 80%
- [ ] 集成测试覆盖核心流程
- [ ] 无明显代码重复
- [ ] 所有Agent职责清晰，接口统一
- [ ] 所有测试通过
- [ ] 无回归问题

---

## 风险和缓解

| 风险 | 影响 | 缓解措施 | 状态 |
|------|------|----------|------|
| 概念学习逻辑迁移出错 | 用户无法学习新概念 | 充分的单元测试，保留原ConceptStore逻辑 | ✅ 已缓解 |
| 流式输出中断 | 用户体验差 | 添加异常处理和超时保护 | ⚠️ 需在Task 9中实现 |
| 路由逻辑错误 | 业务操作被误判为对话 | 添加置信度阈值和fallback机制 | ✅ 已缓解 |
| 对话历史过长 | 内存占用高 | 限制chat_history长度（如最近20轮） | ⚠️ 后续优化 |
| DialogueEngine删除后回归问题 | 现有功能受影响 | 分阶段迁移，充分测试后再删除 | ✅ 已缓解 |

---

## 总结

本实施计划通过5个Chunk、13个Task，分阶段将DialogueEngine的核心能力整合到多智能体架构中：

1. **Chunk 1**: 数据模型增强（Task 1-2）
2. **Chunk 2**: IntentAgent概念学习增强（Task 3-5）
3. **Chunk 3**: Orchestrator路由增强（Task 6-8）
4. **Chunk 4**: Main.py统一chat模式（Task 9）
5. **Chunk 5**: 集成测试和清理（Task 10-13）

每个阶段都保持向后兼容，确保现有功能不受影响。通过TDD方法，先写测试再实现，保证代码质量。最终实现统一的、职责清晰的多智能体架构。
