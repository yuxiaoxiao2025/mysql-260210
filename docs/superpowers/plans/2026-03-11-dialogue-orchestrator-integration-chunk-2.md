# Chunk 2: IntentAgent概念学习增强

> **前置依赖：** [Chunk 1: 数据模型增强](./2026-03-11-dialogue-orchestrator-integration-chunk-1.md)
> **后续文件：** [Chunk 3: Orchestrator路由增强](./2026-03-11-dialogue-orchestrator-integration-chunk-3.md)

---

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

**Chunk 2 完成！** 继续执行 [Chunk 3: Orchestrator路由增强](./2026-03-11-dialogue-orchestrator-integration-chunk-3.md)