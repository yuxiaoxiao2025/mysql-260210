## 背景与现象（来自用户日志）

- 进入 `ReACT` 模式后，问“你可以干什么”会输出“智能停车系统”相关能力，明显跑偏。
- 问“能否查看索引”时，助手回答“无法直接查看索引结构”，且无法给出替代路径。
- 用户期望：更像 “openclaw” 一样**跳出固定框架**，让大模型自己想办法完成任务；同时强调数据库本来就有索引，不想做“建议建索引”这类无用功，而是要能**查看/利用现有索引**。
- 用户偏好：**不展示 SQL**，只返回结果。
- 新增诉求：当现有能力不足时，能按 `vercel-labs/skills` 的 `find-skills` 方式**自动寻找并安装 skill**，再继续工作。

## 目标（验收标准）

- 用户输入“你可以干什么”：回答应与**当前已注册工具与已启用 skills/operations**一致，不再输出停车业务硬编码内容。
- 用户询问索引（如“某表有哪些索引/这个查询走不走索引”）：系统能通过工具读取元数据并给出结论或下一步（如 EXPLAIN）。
- ReACT 循环对所有请求统一处理：chat/qa/query/mutation **一套编排**，模型自主决定调用哪些工具。
- 安全边界清晰：写操作必须 preview + confirm；只读类查询允许更自由（含 SHOW / EXPLAIN / information_schema）。
- 当缺能力时：模型能 `find_skills → install_skill/enable_skill → 重试`，行为与 `npx skills` 工作流一致（或在受限环境下给出可执行命令）。

## 方案选型（2-3 个方案）

### 方案 1：最小修补（不推荐）

- 仅修改 `ReACT` 的 system prompt，去掉“智能停车”字样；不改工具集合。
- 优点：改动小。
- 缺点：仍无法查看索引/EXPLAIN；“更像 openclaw”的能力上限不足。

### 方案 2：增强工具 + 保留现有双架构（次选）

- 保留 `agents/` Pipeline 与 `react/` 两套体系；
- 给 ReACT 增加索引/元数据工具、find_skills/install_skill；
- 优点：风险较低。
- 缺点：架构继续分裂，后续维护成本高；能力重复实现。

### 方案 3：统一 ReACT + 可插拔 Skill（推荐）

- 所有输入统一进入 ReACT 循环；将“schema 检索、安全校验、预览、执行、知识/operation”等能力全部工具化；
- 让模型自主决定使用哪些工具；减少硬编码流程；
- 内置 skill 发现与安装工具（对齐 `vercel-labs/skills` 的 `find-skills` 流程）。
- 优点：架构统一、能力上限最高、最贴近“openclaw”体验。
- 缺点：改动面较大，需要测试兜底与开关回滚。

## 推荐设计（方案 3）的关键点

### 1) 统一 ReACT 编排器（单入口）

- 入口：CLI/Web 的所有请求都走 `UnifiedReACTOrchestrator`（或现有 `MVPReACTOrchestrator` 的升级版）。
- 循环：模型输出 tool calls → 执行工具 → 把 observation 回灌 → 直到输出最终答案。
- 交互中断：当写操作需要确认时，中断循环并返回确认请求；用户确认后恢复继续。

### 2) 去业务硬编码：系统提示词与“能力说明”改造

问题根因：
- 当前 `src/react/tools.py` 的 `SYSTEM_PROMPT` 写死“智能停车数据库助手”，导致模型在任何场景都按停车业务回答。

设计：
- 将 system prompt 改为“通用 MySQL 助手 + 工具驱动”。
- “你可以干什么”的回答由以下信息动态生成：
  - 已注册工具列表（工具名 + 简述）
  - 已启用业务 operations（若存在）
  - 已启用 skills（若存在）

约束（按用户偏好）：
- 默认不展示 SQL，只展示结论与结果摘要。

### 3) 工具层（Tools）设计：让模型“自己想办法”

工具分层（建议最小闭环）：

- **数据库元信息/结构**
  - `list_tables()`
  - `describe_table(table_name)`
  - `search_schema(query)`（可复用现有检索管线）
  - `list_indexes(table_name)`（SHOW INDEX / information_schema.statistics）
  - `get_index_detail(table_name, index_name)`（可选）

- **只读数据访问（更自由，但有白名单）**
  - `run_readonly_sql(sql, purpose)`：允许 `SELECT` / `SHOW` / `DESCRIBE` / `EXPLAIN` / `WITH` 等只读语句
  - 内部做严格校验：拒绝 `INSERT/UPDATE/DELETE/REPLACE/ALTER/DROP/CREATE/TRUNCATE` 等

- **性能解释（可选但强烈建议）**
  - `explain_sql(sql)`：封装 `EXPLAIN` 或 `EXPLAIN FORMAT=JSON`（仅当可用）
  - 输出结构化摘要：可能用到的索引、扫描行数、是否全表扫描等

- **业务操作（已有则保留）**
  - `list_operations()`
  - `get_operation_help(operation_id)`
  - `preview_operation(operation_id, params)`
  - `execute_operation(operation_id, params, confirmed)`

- **安全与确认**
  - `check_sql_safety(sql)`（用于只读 SQL 兜底校验或策略解释）
  - `confirm_operation(message)`（触发“需要用户确认”的中断）

### 4) “像 openclaw 一样自动找 skill 并安装”

对齐参考：
- `vercel-labs/skills` 的 `find-skills` 工作流（`npx skills find` / `npx skills add`）。

新增工具：
- `find_skills(query)`
  - 实现：调用 `npx skills find <query>`，解析输出为结构化结果（skill 名称、描述、安装命令、skills.sh 链接）
- `install_skill(owner_repo_at_skill, global=true)`
  - 实现：调用 `npx skills add <owner/repo@skill> -g -y`
  - 受限环境降级：若无法联网/无 Node，则返回“可执行命令 + 手动步骤”，模型继续用现有能力完成任务或提示限制
- `enable_skill(skill_id)` / `list_enabled_skills()`（如需要）

ReACT 策略（软规则，不硬编码流程）：
- 当模型判断“缺少工具/未知工具/无法完成”时：
  1) 调用 `find_skills`（关键词由模型自主生成）
  2) 选择最匹配 skill
  3) `install_skill`（可配置：只读类自动安装；写操作类需确认）
  4) `enable_skill` 并重试原任务

### 5) 回滚与开关

- 环境变量开关（示例）：`USE_UNIFIED_REACT=true/false`
- 保留现有 `agents/` pipeline 作为回滚路径，便于快速恢复可用性。

## 测试与验证用例（最少集）

- **能力说明不跑偏**
  - 输入：你可以干什么
  - 期望：输出基于实际工具/skills/operations 的能力清单；不出现“智能停车”类硬编码。

- **索引可见**
  - 输入：你可以查看数据库里是否有索引？
  - 期望：先解释“可以，通过元数据查询”；随后（在有连接时）可对指定表 `list_indexes` 并摘要输出。

- **自动找 skill**
  - 输入：帮我做一个 xxx（当前无工具支持）
  - 期望：触发 `find_skills`，给出候选并执行 `install_skill`（或降级提示），然后继续完成任务。

## 非目标（明确不做）

- 不做“建议新增索引/自动建索引”的优化建议闭环（除非用户明确要求）。
- 不默认展示 SQL。

