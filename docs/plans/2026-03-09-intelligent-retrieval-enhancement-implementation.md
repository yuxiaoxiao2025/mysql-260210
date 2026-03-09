# Intelligent Retrieval Enhancement Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enhance the retrieval system with context awareness, table constraints, and CLI preview/feedback loop.

**Architecture:** 
Introduce a Context Enhancer to maintain dialogue state and rewrite queries. Add Table Constraints to prevent hallucinated tables. Implement a CLI Preview for rich interaction and a Feedback Loop to learn from user corrections.

**Tech Stack:** 
Python 3.10+, SQLAlchemy, ChromaDB, Rich (new dependency), DashScope.

---

### Task 1: Dependencies and Module Structure

**Files:**
- Modify: `requirements.txt`
- Create: `src/context/__init__.py`
- Create: `src/constraint/__init__.py`
- Create: `src/cli/__init__.py`
- Create: `src/feedback/__init__.py`

**Step 1: Add rich to requirements**

Add `rich` to `requirements.txt`.

**Step 2: Create module directories**

Create the directories and empty `__init__.py` files for new modules.

**Step 3: Commit**

```bash
git add requirements.txt src/context src/constraint src/cli src/feedback
git commit -m "feat: add rich dependency and module structure"
```

---

### Task 2: Context Enhancer (Slot Tracker & Query Rewriter)

**Files:**
- Create: `src/context/slot_tracker.py`
- Create: `src/context/query_rewriter.py`
- Test: `tests/context/test_context_enhancer.py`

**Step 1: Write failing test for SlotTracker**

```python
# tests/context/test_context_enhancer.py
from src.context.slot_tracker import SlotTracker

def test_slot_tracker_extracts_plate():
    tracker = SlotTracker()
    slots = tracker.extract("查沪BAB1565的记录")
    assert slots.get("plate") == "沪BAB1565"
```

**Step 2: Implement SlotTracker**

Implement `SlotTracker` with regex or simple logic to extract plates (e.g., `沪[A-Z0-9]{6,7}`).

**Step 3: Write failing test for QueryRewriter**

```python
# tests/context/test_context_enhancer.py
from src.context.query_rewriter import QueryRewriter

def test_rewrite_query_with_context():
    rewriter = QueryRewriter()
    context = {"plate": "沪BAB1565"}
    new_query = rewriter.rewrite("这辆车3月出入过哪些园区", context)
    assert "沪BAB1565" in new_query
```

**Step 4: Implement QueryRewriter**

Implement `QueryRewriter` to replace pronouns ("这辆车", "它") with values from context.

**Step 5: Run tests**

Run `pytest tests/context/test_context_enhancer.py`

**Step 6: Commit**

```bash
git add src/context/slot_tracker.py src/context/query_rewriter.py tests/context/test_context_enhancer.py
git commit -m "feat: implement context enhancer (slot tracker and query rewriter)"
```

---

### Task 3: Table Constraint Validator

**Files:**
- Create: `src/constraint/table_validator.py`
- Test: `tests/constraint/test_table_validator.py`

**Step 1: Write failing test**

```python
# tests/constraint/test_table_validator.py
from src.constraint.table_validator import TableValidator

def test_validate_sql_tables():
    validator = TableValidator(allowed_tables=["users", "orders"])
    is_valid, error = validator.validate("SELECT * FROM users JOIN products ON users.id = products.user_id")
    assert is_valid is False
    assert "products" in error
```

**Step 2: Implement TableValidator**

Use `sqlglot` (already in requirements) to parse SQL and check table names against allowed list.

**Step 3: Run tests**

Run `pytest tests/constraint/test_table_validator.py`

**Step 4: Commit**

```bash
git add src/constraint/table_validator.py tests/constraint/test_table_validator.py
git commit -m "feat: implement table constraint validator"
```

---

### Task 4: CLI Preview with Rich

**Files:**
- Create: `src/cli/preview.py`
- Create: `src/cli/interaction.py`
- Test: `tests/cli/test_preview.py`

**Step 1: Write failing test (Mocked)**

```python
# tests/cli/test_preview.py
from src.cli.preview import CLIPreview
import pandas as pd

def test_preview_table_generation():
    df = pd.DataFrame({"id": [1, 2], "name": ["A", "B"]})
    preview = CLIPreview()
    table = preview.generate_table(df)
    assert table.columns[0].header == "id"
```

**Step 2: Implement CLIPreview**

Use `rich.table.Table` and `rich.console.Console` to display DataFrames.

**Step 3: Implement Interaction**

Implement `Interaction.ask_feedback()` to prompt user for "y/n/correction".

**Step 4: Run tests**

Run `pytest tests/cli/test_preview.py`

**Step 5: Commit**

```bash
git add src/cli/preview.py src/cli/interaction.py tests/cli/test_preview.py
git commit -m "feat: implement CLI preview and interaction"
```

---

### Task 5: Feedback Parser & Logger

**Files:**
- Create: `src/feedback/intent_parser.py`
- Create: `src/feedback/query_logger.py`
- Test: `tests/feedback/test_feedback.py`

**Step 1: Write failing test**

```python
# tests/feedback/test_feedback.py
from src.feedback.intent_parser import FeedbackParser

def test_parse_correction():
    parser = FeedbackParser()
    intent = parser.parse("不对，我要的是出场记录")
    assert intent.type == "correction"
    assert intent.content == "我要的是出场记录"
```

**Step 2: Implement FeedbackParser**

Simple logic to detect "y", "n", "more", or other text (correction).

**Step 3: Implement QueryLogger**

Log query, result, feedback to a file/DB for future learning.

**Step 4: Run tests**

Run `pytest tests/feedback/test_feedback.py`

**Step 5: Commit**

```bash
git add src/feedback/intent_parser.py src/feedback/query_logger.py tests/feedback/test_feedback.py
git commit -m "feat: implement feedback parser and logger"
```

---

### Task 6: Integrate with LLM Client

**Files:**
- Modify: `src/llm_client.py`
- Test: `tests/test_llm_integration.py`

**Step 1: Modify LLMClient to use ContextEnhancer**

Inject `ContextEnhancer` (SlotTracker + QueryRewriter) into `generate_sql`.
Update `generate_sql` to accept `context` and rewrite query.

**Step 2: Modify LLMClient to use TableValidator**

After generating SQL, run `TableValidator`. If invalid, retry or fail with helpful message.

**Step 3: Modify LLMClient to use Retrieval Pipeline results for Table Constraint**

Pass retrieved tables to `TableValidator` as allowed tables.

**Step 4: Verify integration with tests**

Ensure existing tests pass and add new integration test.

**Step 5: Commit**

```bash
git add src/llm_client.py
git commit -m "refactor: integrate context enhancer and table validator into LLMClient"
```

---

### Task 7: Integrate with Main Loop

**Files:**
- Modify: `main.py`

**Step 1: Initialize new modules in main**

Instantiate `ContextEnhancer`, `CLIPreview`, `FeedbackParser`.

**Step 2: Update main loop**

Refactor the loop to:
1. Get input.
2. Enhance context/rewrite query.
3. Generate SQL (with constraints).
4. Execute query.
5. Show Preview (using CLIPreview).
6. Ask Feedback.
7. Handle Feedback (Retry/Export).

**Step 3: Verify manually**

Run `python main.py` and test the flow.

**Step 4: Commit**

```bash
git add main.py
git commit -m "refactor: integrate all components into main loop"
```
