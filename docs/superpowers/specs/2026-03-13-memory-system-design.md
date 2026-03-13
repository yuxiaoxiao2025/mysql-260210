# 长期记忆系统设计方案（knowledge_facts）

> 日期：2026-03-13  
> 状态：草案（待实现）  
> 场景：MySQL Export Tool v3.0 / Orchestrator / MVP ReACT

---

## 1. 背景与目标

当前系统在对话和 ReACT 排错过程中，经常通过多轮 SQL 查询 + 日志分析，推导出**高价值的业务结论**，例如：

- 某个 P 打头库（如 `p210331212303`）对应的真实园区名称与 `park_id`
- 某些字段或特殊取值的业务语义（如某库中 `park_id=0` 的含义）
- 「云平台表 / 中心主数据 / 分表」之间的稳定映射关系

这些结论目前：

- 只存在于**当前进程的短期记忆**（Orchestrator state / ContextMemory），
- 进程结束后不会自动保存，下次启动需要重新排查；
- 即使已经在一次 debug 中被你和 LLM 反复确认，也不会“记住”。

**目标：**

1. 提供一个**长期记忆存储**，可以持久保存这类结论，并在今后推理/查库时自动使用。
2. 所有长期记忆在写入前**必须经过人工确认**，绝不允许 LLM 自主静默写入。
3. 每条记忆在保存前，都要给出**清晰的证据摘要**，方便你快速判断是否可信。
4. 记忆具备**可管理性**：支持软删除/停用，便于后续修正错误结论。

---

## 2. 整体设计概览

### 2.1 核心思路

- 在 `db_parking_center` 中新增一张长期记忆表 `knowledge_facts`；
- 通过内部工具（面向 ReACT / Orchestrator）提供三类操作：
  - **propose_fact**：生成“记忆提案”，仅缓存，不写库；
  - **confirm_fact**：在你确认后，将提案写入 `knowledge_facts`；
  - （可选）list_facts / update_fact / disable_fact：用于后续维护。
- 运行时，从 `knowledge_facts` 中加载**已确认且启用的事实**，用于：
  - ReACT 构造工具调用 / SQL 时的先验知识；
  - Orchestrator 进行 schema / 场库 / 字段语义推理时的辅助。

### 2.2 设计原则

- **安全优先**：所有写入均需用户确认；默认不保存任何未经确认的“推测”。
- **格式统一**：使用简单且通用的 `fact_key` 命名规则，同时方便人类和 LLM 理解。
- **灵活扩展**：不按业务类别硬编码分表，所有类型的事实都可以进入 `knowledge_facts`，类别通过 key/value 自描述。
- **可回滚**：支持软删除（enabled=false），保留历史以便审计或后续分析。

---

## 3. 数据模型设计

### 3.1 表结构：`db_parking_center.knowledge_facts`

**字段：**

- `id` bigint, PK, auto_increment
- `fact_key` varchar(255), NOT NULL, 唯一键
  - 形式：`<namespace>:<identifier>`
  - 典型示例：
    - `schema:p210331212303`  
    - `park:p210331212303`  
    - `table:p210331212303.tb_outpark_infos202603`  
    - `field:p210331212303.tb_outpark_infos202603.park_id`  
    - `rule:park_id_zero_semantics`
- `fact_value` json / text, NOT NULL
  - 存储**机器可读的完整事实内容**，例如：

    ```json
    {
      "schema": "p210331212303",
      "park_id": 25,
      "park_name": "漕河泾科技产业化大楼",
      "notes": "源自 cloudinterface.config + parkcloud.cloud_park 多轮交叉验证"
    }
    ```

- `evidence` json / text, NOT NULL
  - 存储**证据列表**（SQL、日志、备注等），用于后续展示和审计，例如：

    ```json
    {
      "sql": [
        "SELECT parkNumber, parkName FROM cloudinterface.config WHERE parkNumber='p210331212303';",
        "SELECT id, number, name FROM parkcloud.cloud_park WHERE number='p210331212303';"
      ],
      "logs": [
        "2026-03-13 ... knowledge_loader: cloud_park.number = 'p210331212303' name='漕河泾科技产业化大楼'"
      ],
      "comments": [
        "经人工确认，此映射无误。"
      ]
    }
    ```

- `summary` text, NOT NULL
  - 面向人的**一句话总结**，用于确认提示：
  - 例如：`p210331212303 库对应“漕河泾科技产业化大楼”，park_id=25。`

- `source` varchar(64), NOT NULL
  - 事实来源，如：`"react"`, `"orchestrator"`, `"manual"`。

- `confirmed_by_user` bool, NOT NULL, 默认 false
  - 仅当为 true 时，运行时推理层才会使用该记录。

- `enabled` bool, NOT NULL, 默认 true
  - 软删除开关；false 表示当前不再使用此事实，但保留记录。

- `created_at` datetime, NOT NULL
- `updated_at` datetime, NOT NULL

**索引建议：**

- `UNIQUE (fact_key)`
- `INDEX idx_facts_active (enabled, confirmed_by_user)`

### 3.2 fact_key 命名空间约定

为兼顾“对人友好”和“对 LLM 易于模式匹配”，约定少量前缀：

- `schema:<schema_name>`  
  - 关于某个 schema 的事实（所属业务域、默认场库等）。
- `park:<schema_or_id>`  
  - 关于场库/园区的事实，例如 `park:p210331212303`，或 `park:25`。
- `table:<schema.table>`  
  - 某个表的整体语义，如是否为事实表、分表、实时日志表。
- `field:<schema.table.column>`  
  - 某个字段的业务含义、取值语义、特殊编码说明。
- `rule:<name>`  
  - 复杂规则，如「某些库中 park_id=0 表示未归类，不参与统计」。

> 注意：此处命名空间仅是约定，并不会在代码中通过枚举强约束；  
> LLM 通过 system prompt 被告知这些前缀的常见用法，从而生成适合的 fact_key。

---

## 4. 工具接口设计

本节描述供 ReACT / Orchestrator 内部调用的“记忆管理工具”接口（可以以 Python 函数、内部工具列表或 ReACT 工具的形式实现）。

### 4.1 `propose_fact`（生成记忆提案）

**目的：**  
仅在内存中生成一条“待确认”的长期记忆提案，不直接写数据库。

**入参（逻辑结构）：**

- `fact_key: str`
- `summary: str`
- `fact_value: dict`
- `evidence: dict`
- `source: str`（如 `"react"` 或 `"orchestrator"`）

**行为：**

- 在内存（如 ReACT orchestrator state）中保存一条 pending 记录；
- 生成并返回 `pending_fact_id`（唯一标识本次提案）。

**出参：**

```json
{
  "pending_fact_id": "uuid-or-increment-id",
  "summary": "...",
  "fact_key": "park:p210331212303"
}
```

### 4.2 `confirm_fact`（确认并写入数据库）

**目的：**  
在用户确认后，将 pending 提案写入 `knowledge_facts` 表。

**入参：**

- `pending_fact_id: str`
- `confirmed: bool`
- `user_comment: Optional[str]`

**行为：**

- 若 `confirmed == false`：  
  - 丢弃 pending 记录，**不写数据库**。
- 若 `confirmed == true`：
  - 取出 pending 记录；
  - 若 `user_comment` 存在：
    - LLM 可以根据 `user_comment` 修正 `summary` / `fact_value`（例如更正名称、补充说明）；
  - 写入/更新 `knowledge_facts`：
    - 若 `fact_key` 已存在：更新 `fact_value` / `evidence` / `summary` / `updated_at`；
    - 否则插入新行；
  - 设置：`confirmed_by_user = true`, `enabled = true`。

**出参：**

```json
{
  "success": true,
  "fact_key": "park:p210331212303",
  "message": "fact saved"
}
```

### 4.3 维护接口（可选）

后续可以补充以下接口（不作为首批实现的硬要求）：

- `list_facts(filter)`：按 `fact_key` 前缀、时间区间等列出所有事实；
- `disable_fact(fact_key)`：将 `enabled` 置为 false，软删除；
- `update_fact(fact_key, patches)`：在新信息下更新某条事实的 value / evidence / summary。

---

## 5. 与 ReACT 的集成流程

### 5.1 何时触发记忆提案

在 MVP ReACT 流程中，当模型通过多轮工具调用和对话，推导出**对未来推理有明显帮助的稳定结论**时，应考虑触发记忆提案，例如：

- 确认某 P 库对应的场库名称和 `park_id`；
- 确认某字段编码的业务语义；
- 发现并确认某条数据质量规则（如某库的特殊取值含义）。

在 ReACT 的 system prompt 中加入约束：

> 当你基于多轮查询/日志推理出一条**稳定且可复用的结论**时，  
> 不要直接记住它，而是先调用 `propose_fact` 工具生成记忆提案，  
> 然后向用户展示证据摘要并请求确认，只有用户确认后才可写入长期记忆。

### 5.2 ReACT 对话级流程

1. 用户与 ReACT 多轮交互，触发多次工具调用（如 search_schema / execute_sql）。
2. LLM 得出一个可长期使用的结论，调用 `propose_fact`：
   - 构造 `fact_key` / `summary` / `fact_value` / `evidence` / `source`；
   - 工具返回 `pending_fact_id`。
3. LLM 向用户呈现**确认提示**，包括：
   - 清晰的**结论摘要**（summary）；
   - 至少 2 条**证据摘要**（来自 `evidence.sql` / `evidence.logs` 等）；
   - 明确说明「这条结论会被写入长期记忆」。
4. 用户输入：
   - `y`：表示同意 → 调用 `confirm_fact(..., confirmed=true)`；
   - `n`：不同意 → 调用 `confirm_fact(..., confirmed=false)`；
   - 其它文字：视为修改意见 → LLM 先修改提案，再 `confirm_fact(..., confirmed=true)`。
5. `confirm_fact` 写入或更新 `knowledge_facts`。

### 5.3 ReACT 使用长期记忆的方式

在 ReACT orchestrator 初始化时：

- 从 `knowledge_facts` 加载：  

  ```sql
  SELECT fact_key, fact_value
  FROM knowledge_facts
  WHERE confirmed_by_user = 1 AND enabled = 1;
  ```

- 将结果放入一个 `MemoryService` 或 ReACT 内部缓存中。

在以下场景中使用：

- 构造工具参数时：
  - 若用户提到某园区 / P 库 / 表名，先查看是否有匹配的 `fact_key`：
    - 如 `park:p210331212303`，可直接得到 `park_id`、官方名称；
- 生成 SQL 时：
  - 根据 `fact_value` 中的结构（schema、park_id 等），自动选取更合理的库/表。

---

## 6. 与 Orchestrator / chat 模式的集成

主模式（非 ReACT）下，Orchestrator 同样会在多轮对话中积累对表结构和业务含义的理解：

- IntentAgent 识别出反复出现的实体；
- KnowledgeAgent 多次回答同类型问题；
- ExecutionAgent 多次针对同一表/字段生成 SQL。

集成方式与 ReACT 基本一致：

- 当 Orchestrator 发现已多次确认某结论（例如某表/字段的业务语义），并且你显式表示「这个以后要记住」时：
  - 由 LLM 调用 `propose_fact`；
  - 展示证据摘要 + 结论摘要；
  - 走同样的 `confirm_fact` 流程。

好处：

- **两个入口（主模式 + ReACT）共享同一套长期记忆机制和存储表**；
- 避免信息割裂，记忆统一集中在 `knowledge_facts`。

---

## 7. 安全与维护策略

### 7.1 写入安全

- 所有长期记忆写入必须经过 `propose_fact` → 人工确认 → `confirm_fact` 三步；
- LLM 不能直接调用任何“立即写 DB”的记忆接口；
- 默认不做只读模式切换（由你控制是否输入 `y`/`n` 决定写入行为）。

### 7.2 软删除与纠错

- 通过 `enabled` 字段实现软删除：
  - 当发现某条记忆不再正确时，可以通过管理接口将其置为 false；
  - 保留历史记录供日后审计。

### 7.3 审计与可解释性

- `evidence` 字段为每条记忆保存了完整的证据链；
- `summary` 为人类可读的一句话总结；
- `source` 标记来源组件，有助于追踪谁写入了这条事实。

---

## 8. 下一步实施建议

1. **建表**：在 `db_parking_center` 上创建 `knowledge_facts` 表，按本方案字段实现；
2. **实现 MemoryService**：
   - 封装加载 active facts（`confirmed_by_user=1 AND enabled=1`）的逻辑；
   - 提供按 `fact_key` 前缀/完全匹配查询的 API。
3. **在 MVP ReACT 中接入**：
   - 实现 `propose_fact` / `confirm_fact` 工具；
   - 修改 ReACT orchestrator，在合适时机触发记忆提案与确认对话；
   - 在工具执行/SQL 生成前注入 MemoryService 的知识。
4. **在 Orchestrator 中接入（可第二阶段）**：
   - 优先在 KnowledgeAgent/ExecutionAgent 层对表/字段语义进行记忆与复用；
5. **补充维护工具（可选）**：
   - 实现 `list_facts` / `disable_fact`，便于你在 CLI 或 Web UI 中浏览和修正长期记忆。

此设计完成后，本系统将具备：

- 「短期对话记忆」+「可审核的长期知识库」的组合能力；
- 可以在今后类似排错场景中，直接复用你已经确认过的业务结论，减少重复劳动。 

