# SQL Mutation Preview Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在现有 Python CLI 中实现自然语言增删改（含批量）的事务内预览与二次确认提交/回滚流程，<=30 行 CLI 展示，>30 行生成 HTML 预览。

**Architecture:** 以现有 CLI 为入口，LLM 生成结构化 DML 与预览 SQL；事务内执行 Before/After 查询并生成差异摘要；根据行数选择 CLI 表格或 HTML 预览；最终二次确认后提交或回滚。

**Tech Stack:** Python 3.12、SQLAlchemy、pandas、pytest/unittest（沿用现有测试栈）

---

### Task 1: 扩展 LLM 输出协议（支持 DML + 预览 SQL）

**Files:**
- Modify: `src/llm_client.py`
- Test: `tests/test_llm_client.py`

**Step 1: Write the failing test**

```python
@patch.dict(os.environ, {"DASHSCOPE_API_KEY": "sk-test"})
@patch("dashscope.Generation.call")
def test_generate_sql_dml_contract(self, mock_call):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_choice = MagicMock()
    mock_choice.message.content = (
        '{"intent":"update","sql":"UPDATE users SET status=1 WHERE id=1",'
        '"preview_sql":"SELECT id,status FROM users WHERE id=1",'
        '"key_columns":["id"],"warnings":["requires_where"]}'
    )
    mock_response.output.choices = [mock_choice]
    mock_call.return_value = mock_response

    client = LLMClient()
    result = client.generate_sql("update user", "context")
    assert result["intent"] == "update"
    assert "preview_sql" in result
    assert result["key_columns"] == ["id"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_llm_client.py::TestLLMClient::test_generate_sql_dml_contract -v`
Expected: FAIL（缺少 intent/preview_sql 解析）

**Step 3: Write minimal implementation**

```python
# 在 prompt 说明中加入 intent/preview_sql/key_columns/warnings 输出要求
# 在解析结果后补齐缺省字段（如 key_columns=[] warnings=[]）
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_llm_client.py::TestLLMClient::test_generate_sql_dml_contract -v`
Expected: PASS

**Step 5: Commit（仅在用户明确要求时执行）**

```bash
git add tests/test_llm_client.py src/llm_client.py
git commit -m "feat: extend llm output for dml preview"
```

---

### Task 2: SQL 安全校验与意图判定

**Files:**
- Create: `src/sql_safety.py`
- Test: `tests/test_sql_safety.py`

**Step 1: Write the failing test**

```python
from src.sql_safety import detect_intent, validate_sql

def test_detect_intent_update():
    assert detect_intent("UPDATE t SET a=1 WHERE id=1") == "update"

def test_validate_rejects_drop():
    ok, reason = validate_sql("DROP TABLE t")
    assert ok is False
    assert "drop" in reason.lower()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_sql_safety.py::test_detect_intent_update -v`
Expected: FAIL（模块不存在）

**Step 3: Write minimal implementation**

```python
import re

def detect_intent(sql: str) -> str:
    first = sql.strip().split()[0].lower() if sql.strip() else ""
    if first in {"insert", "update", "delete", "select"}:
        return first
    return "unknown"

def validate_sql(sql: str) -> tuple[bool, str]:
    lowered = sql.lower()
    for kw in ("drop", "alter", "truncate"):
        if re.search(rf"\\b{kw}\\b", lowered):
            return False, f"Disallowed keyword: {kw}"
    return True, "ok"
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_sql_safety.py -v`
Expected: PASS

**Step 5: Commit（仅在用户明确要求时执行）**

```bash
git add src/sql_safety.py tests/test_sql_safety.py
git commit -m "feat: add sql safety guard"
```

---

### Task 3: 事务预览引擎（Before/After + Diff 摘要）

**Files:**
- Create: `src/txn_preview.py`
- Modify: `src/db_manager.py`
- Test: `tests/test_txn_preview.py`

**Step 1: Write the failing test**

```python
import pandas as pd
from src.txn_preview import summarize_diff

def test_summarize_diff_counts():
    before = pd.DataFrame([{"id": 1, "v": 1}, {"id": 2, "v": 2}])
    after = pd.DataFrame([{"id": 1, "v": 2}, {"id": 3, "v": 3}])
    summary = summarize_diff(before, after, key_columns=["id"])
    assert summary["updated"] == 1
    assert summary["deleted"] == 1
    assert summary["inserted"] == 1
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_txn_preview.py::test_summarize_diff_counts -v`
Expected: FAIL（模块不存在）

**Step 3: Write minimal implementation**

```python
def summarize_diff(before_df, after_df, key_columns):
    # 以 key_columns 对齐，输出 inserted/deleted/updated 计数
    ...
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_txn_preview.py -v`
Expected: PASS

**Step 5: Commit（仅在用户明确要求时执行）**

```bash
git add src/txn_preview.py tests/test_txn_preview.py src/db_manager.py
git commit -m "feat: add transaction preview with diff summary"
```

---

### Task 4: CLI/HTML 预览渲染

**Files:**
- Create: `src/preview_renderer.py`
- Test: `tests/test_preview_renderer.py`

**Step 1: Write the failing test**

```python
import pandas as pd
from src.preview_renderer import should_render_html

def test_should_render_html_threshold():
    df = pd.DataFrame([{"id": i} for i in range(31)])
    assert should_render_html(df, df, max_rows=30) is True
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_preview_renderer.py::test_should_render_html_threshold -v`
Expected: FAIL（模块不存在）

**Step 3: Write minimal implementation**

```python
def should_render_html(before_df, after_df, max_rows: int) -> bool:
    return max(len(before_df), len(after_df)) > max_rows
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_preview_renderer.py -v`
Expected: PASS

**Step 5: Commit（仅在用户明确要求时执行）**

```bash
git add src/preview_renderer.py tests/test_preview_renderer.py
git commit -m "feat: add preview renderer switch"
```

---

### Task 5: CLI 主流程集成（两次确认 + 回滚）

**Files:**
- Modify: `main.py`
- Modify: `src/db_manager.py`
- Modify: `src/llm_client.py`
- Modify: `src/schema_loader.py`（如需为 key_columns 提示补充字段信息）
- Test: `tests/test_main_flow.py`

**Step 1: Write the failing test**

```python
def test_cli_rejects_disallowed_sql(monkeypatch):
    # 伪造输入 DROP 并断言流程直接中止
    ...
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_main_flow.py::test_cli_rejects_disallowed_sql -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# 1) 识别 insert/update/delete
# 2) 调用 validate_sql
# 3) 事务内 preview -> 展示 -> 二次确认 -> commit/rollback
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_main_flow.py::test_cli_rejects_disallowed_sql -v`
Expected: PASS

**Step 5: Commit（仅在用户明确要求时执行）**

```bash
git add main.py src/db_manager.py tests/test_main_flow.py
git commit -m "feat: integrate dml preview and confirm flow"
```

---

### Task 6: 全量测试与质量门禁

**Files:**
- None

**Step 1: Run test suite**

Run: `pytest -v`
Expected: PASS

**Step 2: 运行 lint/typecheck（若项目有明确命令）**

Run: 以仓库内 README/文档提供的命令为准（若未定义则跳过并记录）
Expected: PASS

**Step 3: Commit（仅在用户明确要求时执行）**

```bash
git commit -m "chore: ensure tests pass"
```

---

**Plan complete and saved to `docs/plans/2026-02-10-sql-mutation-preview.md`. Two execution options:**

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
