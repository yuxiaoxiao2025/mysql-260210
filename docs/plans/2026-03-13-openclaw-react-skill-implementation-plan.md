# Openclaw-like Unified ReACT + Skills 安装 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将当前系统改造成“更像 openclaw”的统一 ReACT 工具驱动助手：不跑偏业务、不展示 SQL、可查看现有索引/EXPLAIN，并支持按 `npx skills find/add` 自动寻找与安装 skill 后继续完成任务。

**Architecture:** 使用单一 `ReACT Orchestrator` 处理 chat/qa/query/mutation；所有能力以工具形式暴露给模型。新增 “skills 发现/安装”工具与最小插件启用机制；写操作仍需 preview + confirm。

**Tech Stack:** Python 3、DashScope(OpenAI 兼容)、FastAPI(已有)、SQLAlchemy、pandas、Node.js `npx skills`（可选依赖/可降级）。

---

### Task 1: 去掉停车业务硬编码（system prompt & general chat）

**Files:**
- Modify: `E:/trae-pc/mysql260227/src/react/tools.py`
- Modify: `E:/trae-pc/mysql260227/src/llm_client.py`
- Test: `E:/trae-pc/mysql260227/test_react_integration.py`（或新增 pytest）

**Step 1: 写一个失败的测试（能力说明不跑偏）**

```python
def test_capability_answer_not_parking_domain():
    # 目标：当用户问“你可以干什么”，回复不应包含“停车/智能停车”
    # （实现方式可通过工具服务模拟/或对 SYSTEM_PROMPT 做断言）
    assert True is False
```

**Step 2: 运行测试确认失败**

Run: `pytest -q`
Expected: FAIL

**Step 3: 修改 `src/react/tools.py` 的 `SYSTEM_PROMPT`**

- 替换“你是智能停车数据库助手”→“你是通用 MySQL 助手”
- 规则改为“尽量不展示 SQL，只返回结论/结果摘要”
- 删除/弱化“写 SQL 前必须先 search_schema”的硬规则（让模型自行决定）

**Step 4: 修改 `src/llm_client.py` 的 `chat()` system message**

- 把 `You are a helpful parking management assistant` 改为通用 MySQL/数据助手，避免 chat 模式跑偏。

**Step 5: 运行测试通过**

Run: `pytest -q`
Expected: PASS

**Step 6: 提交**

```bash
git add src/react/tools.py src/llm_client.py test_react_integration.py
git commit -m "feat: 移除停车业务硬编码，统一为通用MySQL助手"
```

---

### Task 2: 扩展 ReACT 工具集合（结构/索引/EXPLAIN/只读SQL白名单）

**Files:**
- Modify: `E:/trae-pc/mysql260227/src/react/tools.py`
- Modify: `E:/trae-pc/mysql260227/src/react/tool_service.py`
- Modify: `E:/trae-pc/mysql260227/src/db_manager.py`
- Test: `E:/trae-pc/mysql260227/tests/unit/test_react_tools.py`（Create）

**Step 1: 写失败的单测（list_indexes / explain_sql / run_readonly_sql）**

```python
def test_run_readonly_sql_rejects_mutations():
    svc = MVPToolService(db_manager=FakeDB(), retrieval_pipeline=FakeRetrieval(), operation_executor=None, knowledge_loader=FakeKnowledge())
    out = svc.execute("run_readonly_sql", {"sql": "DELETE FROM t", "purpose": "测试"})
    assert "拒绝" in out or "不允许" in out

def test_list_indexes_calls_metadata():
    # 目标：工具返回索引摘要，不返回SQL
    assert True is False
```

**Step 2: 跑测试确认失败**

Run: `pytest tests/unit/test_react_tools.py -q`
Expected: FAIL

**Step 3: 扩展 `src/react/tools.py` 的 `MVP_TOOLS`**

新增函数定义（至少）：
- `list_tables`
- `describe_table`
- `list_indexes`
- `explain_sql`
- `run_readonly_sql`
- `find_skills`
- `install_skill`

（保留现有：`search_schema`, `execute_sql`, `list_operations`, `execute_operation`；后续可逐步统一命名/替换）

**Step 4: 在 `src/react/tool_service.py` 实现对应 `_tool_*`**

- `_tool_list_tables()`：调用 `DatabaseManager.get_all_tables()`（必要时限制返回数量）
- `_tool_describe_table(table_name)`：调用 `DatabaseManager.get_table_schema(...)` 或跨库版本
- `_tool_list_indexes(table_name, db_name=None)`：
  - 优先走 `information_schema.statistics`（跨库更稳）
  - 输出：索引名、列顺序、唯一性、类型（只摘要，不输出 SQL）
- `_tool_explain_sql(sql)`：
  - 只允许对只读 SQL 做 EXPLAIN
  - 输出：是否全表扫描、possible_keys/key、rows 等摘要
- `_tool_run_readonly_sql(sql, purpose=None)`：
  - 白名单语句：`SELECT/SHOW/DESC/DESCRIBE/EXPLAIN/WITH`
  - 黑名单：任何 DML/DDL（INSERT/UPDATE/DELETE/ALTER/...）
  - 返回 DataFrame 的摘要（行数+head），不输出 SQL

**Step 5: `DatabaseManager` 补齐索引元数据方法（如需要）**

- 新增 `get_table_indexes(db_name, table_name)`（封装 information_schema.statistics）
- 确保入参做 identifier 校验（复用 `_VALID_IDENTIFIER`）

**Step 6: 运行测试通过**

Run: `pytest tests/unit/test_react_tools.py -q`
Expected: PASS

**Step 7: 提交**

```bash
git add src/react/tools.py src/react/tool_service.py src/db_manager.py tests/unit/test_react_tools.py
git commit -m "feat: ReACT补齐结构/索引/EXPLAIN与只读SQL工具"
```

---

### Task 3: 集成 `npx skills` 的 find/install（可降级）

**Files:**
- Modify: `E:/trae-pc/mysql260227/src/react/tool_service.py`
- Create: `E:/trae-pc/mysql260227/src/skills/skills_cli.py`
- Create: `E:/trae-pc/mysql260227/tests/unit/test_skills_cli.py`

**Step 1: 写失败单测（无 npx 时降级）**

```python
def test_find_skills_graceful_when_npx_missing(monkeypatch):
    # 目标：当 npx 不存在/执行失败时，返回可读的降级信息而不是抛异常
    assert True is False
```

**Step 2: 跑测试确认失败**

Run: `pytest tests/unit/test_skills_cli.py -q`
Expected: FAIL

**Step 3: 实现 `src/skills/skills_cli.py`**

- `find_skills(query: str) -> dict`：
  - 调用 `npx skills find <query>`
  - 解析输出（至少提取：install 命令行、skills.sh 链接、标题/说明）
  - 失败则返回降级：提示需要 Node/npm，并返回用户可手动执行的命令
- `install_skill(spec: str, global_install: bool = True) -> dict`：
  - 调用 `npx skills add <spec> -g -y`（global_install=True）
  - 失败则降级返回命令与错误摘要

**Step 4: 在 `MVPToolService` 中接入工具**

- `_tool_find_skills(query)`
- `_tool_install_skill(spec, global_install=True)`

**Step 5: 测试通过**

Run: `pytest tests/unit/test_skills_cli.py -q`
Expected: PASS

**Step 6: 提交**

```bash
git add src/skills/skills_cli.py src/react/tool_service.py tests/unit/test_skills_cli.py
git commit -m "feat: 集成npx skills的查找与安装（可降级）"
```

---

### Task 4: ReACT 策略与“能力说明”动态化（不展示SQL）

**Files:**
- Modify: `E:/trae-pc/mysql260227/src/react/orchestrator.py`
- Modify: `E:/trae-pc/mysql260227/src/react/tools.py`
- Modify: `E:/trae-pc/mysql260227/src/react/tool_service.py`
- Test: `E:/trae-pc/mysql260227/tests/integration/test_react_capabilities.py`（Create）

**Step 1: 写失败集成测试**

```python
def test_what_can_you_do_lists_tools_not_domain():
    # 目标：问“你可以干什么”时，回答应基于 tools/skills/operations 构建
    assert True is False
```

**Step 2: 跑测试确认失败**

Run: `pytest tests/integration/test_react_capabilities.py -q`
Expected: FAIL

**Step 3: 在 system prompt 中加入软规则**

- “默认不展示 SQL”
- “当缺能力时，可尝试 find_skills/install_skill 后再继续”
- “尽量先用元数据工具（describe_table/list_indexes/explain_sql）再判断性能/索引问题”

**Step 4: 在 `MVPToolService` 新增一个内部能力汇总方法**

例如 `_tool_list_capabilities()`（是否暴露为 tool 取决于提示词效果）：
- 汇总：工具名+一句话、operations 数量、已启用 skills
- 供模型回答“你可以干什么”时使用

**Step 5: 测试通过**

Run: `pytest tests/integration/test_react_capabilities.py -q`
Expected: PASS

**Step 6: 提交**

```bash
git add src/react/orchestrator.py src/react/tools.py src/react/tool_service.py tests/integration/test_react_capabilities.py
git commit -m "feat: ReACT能力说明动态化并加入自动skills策略"
```

---

### Task 5: 端到端验证（CLI + 回滚开关）

**Files:**
- Modify: `E:/trae-pc/mysql260227/main.py`（或实际 CLI 入口文件，按仓库结构确认）
- Modify: `E:/trae-pc/mysql260227/CLAUDE.md`（如需补充运行/验证）
- Test: `pytest` 全量

**Step 1: 加入开关**

- `USE_UNIFIED_REACT=true/false`（默认 false，逐步灰度）

**Step 2: 手工验证脚本**

Run: `python main.py`
Try:
- “你可以干什么”
- “你可以查看数据库里是否有索引？”
- “对某个表列出索引”（如：`list_indexes` 需要表名时，模型应追问并调用工具）

**Step 3: 全量测试**

Run: `pytest`
Expected: PASS

**Step 4: 提交**

```bash
git add main.py CLAUDE.md
git commit -m "chore: 增加统一ReACT开关与验证说明"
```

---

## 执行交接

计划已写入 `docs/plans/2026-03-13-openclaw-react-skill-implementation-plan.md`。

两种执行方式：

1. **Subagent-Driven（本会话）**：我按任务逐个实现、每步跑测试、边做边回报进展（推荐）。
2. **Parallel Session（新会话）**：在独立环境按计划批量执行并设置检查点。

请选择 1 或 2。

