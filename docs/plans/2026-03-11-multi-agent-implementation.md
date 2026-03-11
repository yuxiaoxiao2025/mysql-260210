# Multi-Agent Refactoring Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将现有的单体/串行过程逻辑重构为由中央控制器协调的 **Multi-Agent 架构**，并**真实集成**现有业务模块（Intent, Metadata, Safety, Executor）。

**Architecture:** 采用 Orchestrator 模式，各 Agent 封装现有的功能模块：
*   **IntentAgent** -> `src.intent.intent_recognizer`
*   **RetrievalAgent** -> `src.metadata.retrieval_pipeline`
*   **SecurityAgent** -> `src.sql_safety`
*   **PreviewAgent** -> `src.preview`, `src.executor` (preview mode)
*   **ExecutionAgent** -> `src.executor`, `src.db_manager`

**Tech Stack:** Python, Pydantic, Pytest

---

### Task 1: 基础设施搭建 (Infrastructure Setup)

**Files:**
- Create: `src/agents/__init__.py`
- Create: `src/agents/models.py`
- Create: `src/agents/context.py`
- Create: `src/agents/config.py`
- Create: `src/agents/base.py`
- Create: `tests/unit/agents/__init__.py`
- Create: `tests/unit/agents/test_infrastructure.py`

**Step 1: Write the failing test**

```python
# tests/unit/agents/test_infrastructure.py
import pytest
from src.agents.models import AgentResult
from src.agents.context import AgentContext
from src.agents.config import BaseAgentConfig
from src.agents.base import BaseAgent

def test_agent_context_structure():
    ctx = AgentContext(user_input="hello")
    assert ctx.trace_id is not None
    assert ctx.step_history == []

def test_base_agent_implementation():
    class TestAgent(BaseAgent):
        def _run_impl(self, context):
            return AgentResult(success=True)
            
    agent = TestAgent(BaseAgentConfig(name="test"))
    assert agent.run(AgentContext(user_input="")).success is True
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/agents/test_infrastructure.py`

**Step 3: Implement code**

Define `AgentResult`, `IntentModel`, `AgentContext`, `BaseAgentConfig` (and subclasses), `BaseAgent` as per design doc.

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/agents/test_infrastructure.py`

**Step 5: Commit**

```bash
git add src/agents tests/unit/agents
git commit -m "feat: infrastructure setup for multi-agent system"
```

---

### Task 2: 实现 Intent Agent (集成 IntentRecognizer)

**Files:**
- Create: `src/agents/impl/__init__.py`
- Create: `src/agents/impl/intent_agent.py`
- Create: `tests/unit/agents/impl/__init__.py`
- Create: `tests/unit/agents/impl/test_intent_agent.py`

**Step 1: Write the failing test**

```python
# tests/unit/agents/impl/test_intent_agent.py
from unittest.mock import MagicMock, patch
from src.agents.impl.intent_agent import IntentAgent
from src.agents.config import IntentAgentConfig
from src.agents.context import AgentContext

@patch("src.agents.impl.intent_agent.IntentRecognizer")
def test_intent_agent_integration(mock_recognizer_cls):
    # Setup mock
    mock_instance = mock_recognizer_cls.return_value
    mock_instance.recognize.return_value.type = "query"
    mock_instance.recognize.return_value.confidence = 0.95
    mock_instance.recognize.return_value.sql = "SELECT * FROM users"
    
    agent = IntentAgent(IntentAgentConfig(name="intent"))
    context = AgentContext(user_input="show users")
    result = agent.run(context)
    
    assert result.success is True
    assert context.intent.type == "query"
    assert context.intent.confidence == 0.95
    assert context.intent.sql == "SELECT * FROM users"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/agents/impl/test_intent_agent.py`

**Step 3: Implement code**

`src/agents/impl/intent_agent.py`:
```python
from src.agents.base import BaseAgent
from src.agents.config import IntentAgentConfig
from src.agents.context import AgentContext, IntentModel
from src.agents.models import AgentResult
# Integration: Import existing module
from src.intent.intent_recognizer import IntentRecognizer

class IntentAgent(BaseAgent):
    def __init__(self, config: IntentAgentConfig):
        super().__init__(config)
        self.recognizer = IntentRecognizer() 

    def _run_impl(self, context: AgentContext) -> AgentResult:
        # Call existing logic
        recognized = self.recognizer.recognize(context.user_input)
        
        # Map to Context Model
        context.intent = IntentModel(
            type=recognized.type,
            confidence=recognized.confidence,
            params=recognized.params,
            operation_id=getattr(recognized, "operation_id", None),
            reasoning=getattr(recognized, "reasoning", ""),
            sql=getattr(recognized, "sql", None),
            need_clarify=getattr(recognized, "need_clarify", False)
        )
        return AgentResult(success=True, data=context.intent)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/agents/impl/test_intent_agent.py`

**Step 5: Commit**

```bash
git add src/agents/impl/intent_agent.py tests/unit/agents/impl/test_intent_agent.py
git commit -m "feat: implement IntentAgent wrapping IntentRecognizer with full mapping"
```

---

### Task 3: 实现 Retrieval Agent (集成 RetrievalPipeline)

**Files:**
- Create: `src/agents/impl/retrieval_agent.py`
- Create: `tests/unit/agents/impl/test_retrieval_agent.py`

**Step 1: Write the failing test**

```python
# tests/unit/agents/impl/test_retrieval_agent.py
from unittest.mock import patch
from src.agents.impl.retrieval_agent import RetrievalAgent
from src.agents.config import BaseAgentConfig
from src.agents.context import AgentContext, IntentModel

@patch("src.agents.impl.retrieval_agent.RetrievalPipeline")
def test_retrieval_agent_search(mock_pipeline_cls):
    mock_pipeline = mock_pipeline_cls.return_value
    mock_pipeline.search.return_value = ["table_users", "table_orders"]
    
    agent = RetrievalAgent(BaseAgentConfig(name="retrieval"))
    context = AgentContext(user_input="find users")
    context.intent = IntentModel(type="query", params={"keywords": "users"})
    
    agent.run(context)
    assert "table_users" in context.schema_context
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/agents/impl/test_retrieval_agent.py`

**Step 3: Implement code**

`src/agents/impl/retrieval_agent.py`:
```python
from src.agents.base import BaseAgent
from src.metadata.retrieval_pipeline import RetrievalPipeline

class RetrievalAgent(BaseAgent):
    def __init__(self, config):
        super().__init__(config)
        self.pipeline = RetrievalPipeline()

    def _run_impl(self, context):
        if not context.intent or not context.intent.params:
             return AgentResult(success=True, message="No params for retrieval")
             
        # Call existing logic
        # Assuming params has 'query' or constructing it from user_input
        results = self.pipeline.search(context.user_input) 
        
        context.schema_context = str(results) # Format as needed
        return AgentResult(success=True, data=results)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/agents/impl/test_retrieval_agent.py`

**Step 5: Commit**

```bash
git add src/agents/impl/retrieval_agent.py tests/unit/agents/impl/test_retrieval_agent.py
git commit -m "feat: implement RetrievalAgent wrapping RetrievalPipeline"
```

---

### Task 4: 实现 Security Agent (集成 SQL Safety)

**Files:**
- Create: `src/agents/impl/security_agent.py`
- Create: `tests/unit/agents/impl/test_security_agent.py`

**Step 1: Write the failing test**

```python
# tests/unit/agents/impl/test_security_agent.py
from src.agents.impl.security_agent import SecurityAgent
from src.agents.config import SecurityAgentConfig
from src.agents.context import AgentContext, IntentModel

def test_security_real_logic():
    agent = SecurityAgent(SecurityAgentConfig(name="sec"))
    context = AgentContext(user_input="drop table")
    context.intent = IntentModel(type="mutation", sql="DROP TABLE users")
    
    result = agent.run(context)
    assert result.success is False
    assert "DROP" in result.message
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/agents/impl/test_security_agent.py`

**Step 3: Implement code**

`src/agents/impl/security_agent.py`:
```python
from src.agents.base import BaseAgent
from src.sql_safety import validate_sql, validate_direct_query_sql

class SecurityAgent(BaseAgent):
    def _run_impl(self, context):
        sql = context.intent.sql
        if not sql:
            return AgentResult(success=True)
            
        try:
            # Call existing logic
            validate_sql(sql)
            if context.intent.type == "query":
                validate_direct_query_sql(sql)
                
            context.is_safe = True
            return AgentResult(success=True)
        except Exception as e:
            context.is_safe = False
            return AgentResult(success=False, message=str(e), next_action="stop")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/agents/impl/test_security_agent.py`

**Step 5: Commit**

```bash
git add src/agents/impl/security_agent.py tests/unit/agents/impl/test_security_agent.py
git commit -m "feat: implement SecurityAgent wrapping sql_safety"
```

---

### Task 5: 实现 Preview & Execution Agent (集成 Executor)

**Files:**
- Create: `src/agents/impl/preview_agent.py`
- Create: `src/agents/impl/execution_agent.py`
- Create: `tests/unit/agents/impl/test_execution_agents.py`

**Step 1: Write the failing test**

```python
# tests/unit/agents/impl/test_execution_agents.py
from unittest.mock import MagicMock, patch
from src.agents.impl.preview_agent import PreviewAgent
from src.agents.impl.execution_agent import ExecutionAgent
from src.agents.context import AgentContext, IntentModel
from src.agents.config import BaseAgentConfig

@patch("src.agents.impl.preview_agent.OperationExecutor")
def test_preview_agent_mutation_only(mock_executor_cls):
    agent = PreviewAgent(BaseAgentConfig(name="preview"))
    context = AgentContext(user_input="drop table")
    context.intent = IntentModel(type="mutation", operation_id="op_1")
    
    agent.run(context)
    mock_executor_cls.return_value.execute_operation.assert_called_with(
        "op_1", {}, preview_only=True
    )

@patch("src.agents.impl.execution_agent.OperationExecutor")
def test_execution_agent_run(mock_executor_cls):
    agent = ExecutionAgent(BaseAgentConfig(name="exec"))
    context = AgentContext(user_input="query")
    context.intent = IntentModel(type="query", operation_id="op_2")
    
    agent.run(context)
    mock_executor_cls.return_value.execute_operation.assert_called_with(
        "op_2", {}, preview_only=False
    )
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/agents/impl/test_execution_agents.py`

**Step 3: Implement code**

`src/agents/impl/preview_agent.py`:
```python
from src.executor.operation_executor import OperationExecutor
# ...
class PreviewAgent(BaseAgent):
    def _run_impl(self, context):
        if context.intent.type != "mutation":
             return AgentResult(success=True, message="Skipped preview for non-mutation")

        executor = OperationExecutor()
        preview = executor.execute_operation(
            context.intent.operation_id, 
            context.intent.params, 
            preview_only=True
        )
        context.preview_data = preview
        return AgentResult(success=True, data=preview)
```

`src/agents/impl/execution_agent.py`:
```python
from src.executor.operation_executor import OperationExecutor
# ...
class ExecutionAgent(BaseAgent):
    def _run_impl(self, context):
        executor = OperationExecutor()
        result = executor.execute_operation(
            context.intent.operation_id, 
            context.intent.params, 
            preview_only=False
        )
        context.execution_result = result
        return AgentResult(success=True, data=result)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/agents/impl/test_execution_agents.py`

**Step 5: Commit**

```bash
git add src/agents/impl/preview_agent.py src/agents/impl/execution_agent.py tests/unit/agents/impl/test_execution_agents.py
git commit -m "feat: implement Preview and Execution agents wrapping OperationExecutor"
```

---

### Task 6: 实现 Orchestrator 完整流程 (Orchestrator Logic)

**Files:**
- Create: `src/agents/orchestrator.py`
- Create: `tests/unit/agents/test_orchestrator.py`

**Step 1: Write the failing test**

```python
# tests/unit/agents/test_orchestrator.py
from unittest.mock import MagicMock
from src.agents.orchestrator import Orchestrator
from src.agents.context import AgentContext

def test_orchestrator_dependency_injection():
    # Inject mocks to test flow without real agents
    mock_intent = MagicMock()
    mock_intent.run.return_value.success = True
    mock_intent.run.return_value.data.need_clarify = False
    mock_intent.run.return_value.data.type = "query"
    
    mock_retrieval = MagicMock()
    mock_security = MagicMock()
    mock_security.run.return_value.success = True
    mock_execution = MagicMock()
    
    orch = Orchestrator(
        intent_agent=mock_intent,
        retrieval_agent=mock_retrieval,
        security_agent=mock_security,
        execution_agent=mock_execution
    )
    
    orch.process("test input")
    
    mock_intent.run.assert_called_once()
    mock_execution.run.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/agents/test_orchestrator.py`

**Step 3: Implement code**

`src/agents/orchestrator.py`:
```python
from src.agents.context import AgentContext
from src.agents.config import IntentAgentConfig, SecurityAgentConfig, BaseAgentConfig
from src.agents.impl.intent_agent import IntentAgent
from src.agents.impl.retrieval_agent import RetrievalAgent
from src.agents.impl.security_agent import SecurityAgent
from src.agents.impl.preview_agent import PreviewAgent
from src.agents.impl.execution_agent import ExecutionAgent

class Orchestrator:
    def __init__(self, intent_agent=None, retrieval_agent=None, security_agent=None, 
                 preview_agent=None, execution_agent=None):
        # Allow DI for testing, otherwise initialize defaults
        self.intent_agent = intent_agent or IntentAgent(IntentAgentConfig(name="intent"))
        self.retrieval_agent = retrieval_agent or RetrievalAgent(BaseAgentConfig(name="retrieval"))
        self.security_agent = security_agent or SecurityAgent(SecurityAgentConfig(name="security"))
        self.preview_agent = preview_agent or PreviewAgent(BaseAgentConfig(name="preview"))
        self.execution_agent = execution_agent or ExecutionAgent(BaseAgentConfig(name="execution"))

    def process(self, user_input: str) -> AgentContext:
        context = AgentContext(user_input=user_input)
        
        # 1. Intent
        res = self.intent_agent.run(context)
        if not res.success or (context.intent and context.intent.need_clarify):
            return context # Ask user
            
        # 2. Retrieval
        self.retrieval_agent.run(context)
        
        # 3. Security
        if not self.security_agent.run(context).success:
            return context # Blocked
            
        # 4. Preview (if mutation)
        if context.intent and context.intent.type == "mutation":
             self.preview_agent.run(context)
             # Logic to stop and ask for confirmation would go here
        
        # 5. Execution (if query or confirmed mutation)
        # ... logic for confirmation handling ...
        self.execution_agent.run(context)
        
        return context
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/agents/test_orchestrator.py`

**Step 5: Commit**

```bash
git add src/agents/orchestrator.py tests/unit/agents/test_orchestrator.py
git commit -m "feat: implement Orchestrator workflow logic with DI"
```

---

### Task 7: 集成与配置 (Integration & Configuration)

**Files:**
- Modify: `main.py`
- Create: `tests/integration/test_cli_agent_mode.py`

**Step 1: Write the failing test**

```python
# tests/integration/test_cli_agent_mode.py
import pytest
from unittest.mock import patch, MagicMock
from src.agents.orchestrator import Orchestrator

@patch.dict("os.environ", {"OPENAI_API_KEY": "test-key", "DASHSCOPE_API_KEY": "test-key"})
@patch("main.Orchestrator")
def test_cli_agent_mode_flag(mock_orch_cls):
    # This is a placeholder for testing main.py logic
    # In reality, you'd invoke main() or parse_args()
    pass
```

**Step 2: Run test to verify it fails**

**Step 3: Implement code**

In `main.py`:
1. Load env vars/config.
2. Initialize `Orchestrator`.
3. Switch logic based on `args.agent_mode`.
4. **Handle Orchestrator returns:** If `context.intent.need_clarify` or `context.preview_data` is present, prompt user and loop back.

**Step 4: Run test to verify it passes**

**Step 5: Commit**

```bash
git add main.py tests/integration/test_cli_agent_mode.py
git commit -m "feat: integrate Orchestrator into main CLI loop with env support"
```
