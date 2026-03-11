# Multi-Agent Refactoring Design Document

**Date:** 2026-03-11
**Status:** Approved & Finalized (v3)

## 1. Overview

Refactor the existing monolithic/serial procedural logic into a **Multi-Agent Architecture** orchestrated by a central controller. This improves modularity, testability, and extensibility, inspired by the "MiroFish" architecture but adapted for a lightweight CLI tool.

## 2. Architecture

### 2.1 Core Components

*   **Orchestrator (`src/agents/orchestrator.py`)**: The brain of the system. It manages the conversation loop, maintains global context, and dispatches tasks to specialized agents.
*   **Base Agent (`src/agents/base.py`)**: Abstract base class defining the contract (`run(context) -> Result`) for all agents. Includes default error handling.
*   **Specialized Agents (`src/agents/impl/*.py`)**: Wrappers around existing logic modules.
*   **Context Model (`src/agents/context.py`)**: Pydantic model for strongly typed context.

### 2.2 Agent Roles

| Agent Name | Role | Replaces / Wraps | Input | Output |
| :--- | :--- | :--- | :--- | :--- |
| **IntentAgent** | Understand user input, manage dialogue state | `src/intent`, `src/dialogue` | `user_input` | `intent` (IntentModel) |
| **RetrievalAgent** | Enrich context with schema/knowledge | `src/metadata` | `intent` | `schema_context` |
| **SecurityAgent** | Validate safety of operations | `src/sql_safety`, `src/constraint` | `schema_context` | `is_safe`, `security_report` |
| **PreviewAgent** | Generate preview of effects | `src/preview`, `src/exporter` | `intent`, `schema_context` | `preview_data` |
| **ExecutionAgent** | Execute final operation | `src/executor`, `src/db_manager` | `intent`, `preview_data` | `execution_result` |

### 2.3 Data Flow (Orchestrator Logic)

1.  **User Input** -> `Orchestrator`
2.  `Orchestrator` wraps input in `AgentContext`
3.  `Orchestrator` -> **IntentAgent** -> Update `AgentContext.intent`
4.  If `Intent.need_clarify` is True -> Return to User.
5.  `Orchestrator` -> **RetrievalAgent** -> Update `AgentContext.schema_context`
6.  `Orchestrator` -> **SecurityAgent** -> Check `AgentContext`
7.  If `Safety Check` fails -> Notify User (Stop).
8.  `Orchestrator` -> **PreviewAgent** -> Update `AgentContext.preview`
9.  User Confirms Preview?
10. If Yes -> `Orchestrator` -> **ExecutionAgent** -> Result

## 3. Implementation Details

### 3.1 Directory Structure

```
src/
  agents/
    __init__.py
    base.py           # BaseAgent class with error handling
    orchestrator.py   # Orchestrator class
    context.py        # AgentContext Pydantic model
    models.py         # AgentResult data model
    config.py         # Agent configuration models
    impl/
      __init__.py
      intent_agent.py
      retrieval_agent.py
      security_agent.py
      preview_agent.py
      execution_agent.py
```

### 3.2 Interfaces

**Models (`src/agents/models.py`):**
```python
class AgentResult(BaseModel):
    success: bool
    data: Optional[Any] = None  # The primary payload result of the agent
    message: str = ""           # Human-readable status or error message
    next_action: str = "continue"  # Action hint: continue, stop, ask_user
    metadata: Dict[str, Any] = {}  # Additional debug info or metrics
```

**Context Model (`src/agents/context.py`):**
```python
class IntentModel(BaseModel):
    type: Literal["query", "mutation", "unknown"]
    operation_id: Optional[str] = None
    params: Dict[str, Any] = {}
    confidence: float = 0.0
    reasoning: str = ""
    sql: Optional[str] = None
    need_clarify: bool = False  # Direct flag for orchestration logic

class AgentContext(BaseModel):
    user_input: str
    chat_history: List[Dict[str, str]] = []
    # Use strict Pydantic model for Intent
    intent: Optional[IntentModel] = None
    schema_context: Optional[str] = None
    is_safe: bool = False
    preview_data: Optional[Any] = None
    execution_result: Optional[Any] = None
    
    # Audit and Debug fields
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    step_history: List[str] = [] # Track which agents ran
    audit_log: List[str] = []    # Important events for audit
```

**Configuration (`src/agents/config.py`):**
```python
class BaseAgentConfig(BaseModel):
    name: str
    enabled: bool = True

class IntentAgentConfig(BaseAgentConfig):
    model_name: str = "qwen-plus"
    confidence_threshold: float = 0.7

class SecurityAgentConfig(BaseAgentConfig):
    max_affected_rows: int = 50
    forbidden_keywords: List[str] = ["DROP", "TRUNCATE"]
    require_confirmation: bool = True

# ... other specific configs
```

**Base Agent (`src/agents/base.py`):**
```python
class BaseAgent(ABC):
    def __init__(self, config: BaseAgentConfig):
        self.config = config

    def run(self, context: AgentContext) -> AgentResult:
        try:
            return self._run_impl(context)
        except Exception as e:
            return AgentResult(success=False, message=str(e), next_action="stop")

    @abstractmethod
    def _run_impl(self, context: AgentContext) -> AgentResult:
        pass
```

## 4. Test Strategy

*   **Unit Tests (`tests/agents/impl/test_*.py`)**: Test each agent in isolation using mocks.
*   **Flow Tests (`tests/agents/test_orchestrator.py`)**: Verify state transitions and error handling.
*   **Regression Tests**: Ensure existing functional tests pass.

## 5. Migration Strategy (Phased Rollout)

1.  **Scaffold**: Create `src/agents` infrastructure.
2.  **Implement Agents**: Port logic one by one.
3.  **Feature Flag**: In `main.py`, use `--agent-mode` flag to switch between old logic and new `Orchestrator`.
    ```python
    if args.agent_mode:
        orchestrator.process(input)
    else:
        # old logic
    ```
4.  **Verification**: User tests with flag enabled.
    *   **Rollback Plan**: If critical issues occur, remove `--agent-mode` flag or set default to False. Code is isolated in `src/agents`, safe to ignore.
5.  **Cutover**: Make new mode default, remove old code.
