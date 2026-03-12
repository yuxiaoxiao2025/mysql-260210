# 极简智能数据库助手设计方案

> 设计日期: 2026-03-12
> 状态: 草案，待实施
> 分支建议: `feature/minimal-smart-assistant`

---

## 一、项目目标

### 1.1 核心目的

> 通过自然语言操作数据库：
> - 查询：这辆车在XX园区停了多久？
> - 导出：导出车牌表
> - 下发：把XX车辆下发到全部园区/某个园区
> - CRUD：新增、更新、删除记录

### 1.2 设计原则

1. **极简**：删除所有不必要的组件
2. **智能**：让模型自主推理，减少硬编码
3. **安全**：修改操作需要确认
4. **可学习**：越用越准确

---

## 二、核心设计

### 2.1 分层信任机制

| 操作类型 | 风险等级 | 执行方式 | 用户感知 |
|----------|----------|----------|----------|
| **SELECT 查询** | 低 | 直接执行 | 只看结果，不看SQL |
| **UPDATE/DELETE** | 高 | 预览→确认→执行 | 简要说明操作内容 |
| **INSERT** | 中 | 预览→确认→执行 | 简要说明操作内容 |

### 2.2 多轮修正对话

```
用户："查询车牌 沪A12345 在国际商务中心停了多久"
    ↓
模型执行 → 返回结果
    ↓
用户："不对，应该用park_id关联"
    ↓
模型修正 → 重新执行 → 返回结果
    ↓
用户："这次对了"
    ↓
系统学习并记忆
```

### 2.3 学习记忆机制

**确认学习 + 本地向量库**

```
触发学习：用户明确说"对了"、"正确"、"OK"
存储方式：本地向量库（复用现有 ChromaDB）
检索方式：语义相似度匹配
```

---

## 三、架构设计

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                           CLI / Web 入口                             │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        ReACT Orchestrator                            │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │  1. 检查记忆库 → 有成功记录？ → 直接用模板执行                 │ │
│  │  2. 没有 → 模型推理生成SQL                                    │ │
│  │  3. 执行 → 返回结果                                           │ │
│  │  4. 用户反馈 → 修正 → 学习                                    │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                  │                                  │
│                                  ▼                                  │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │                      工具层 (4个工具)                          │ │
│  │                                                               │ │
│  │  search_schema(query)    → 搜索表结构                         │ │
│  │  execute_sql(sql)        → 执行SQL                            │ │
│  │  execute_operation(...)  → 执行预定义操作（可选）              │ │
│  │  list_operations()       → 列出可用操作                       │ │
│  │                                                               │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                  │                                  │
│                                  ▼                                  │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │                      记忆层 (新增)                             │ │
│  │                                                               │ │
│  │  LearnedOperationStore:                                       │ │
│  │  - 存储：意图 → SQL模板 + 成功次数                            │ │
│  │  - 检索：语义相似度匹配                                       │ │
│  │  - 学习：用户确认后自动保存                                   │ │
│  │                                                               │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                  │                                  │
│                                  ▼                                  │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │                      服务层 (已存在)                           │ │
│  │                                                               │ │
│  │  RetrievalPipeline  │  OperationExecutor  │  DatabaseManager  │ │
│  │  (向量索引+重排序)   │  (业务操作执行)     │  (数据库连接)      │ │
│  │                                                               │ │
│  └───────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 与现有架构对比

| 维度 | 现有架构 | 新架构 |
|------|----------|--------|
| **Agent数量** | 6个 | 0个 |
| **概念映射** | 17个概念，人工维护 | 删除 |
| **启动向导** | 问一堆问题 | 删除 |
| **记忆机制** | 无 | 学习记忆库 |
| **修正机制** | 无 | 多轮修正对话 |
| **系统提示** | 复杂模板 | 简洁描述 |

---

## 四、交互设计

### 4.1 查询操作

```
用户：查询车牌 沪A12345

系统：（检查记忆库 → 有记录 → 直接用模板）
      或
      （无记录 → 模型生成SQL → 执行）

返回：车牌 沪A12345，状态=已下发，绑定园区=国际商务中心

提示：需要查看停车记录吗？
```

**特点**：用户只看结果，不看SQL

### 4.2 修改操作

```
用户：下发车牌 沪A12345 到 万达广场

系统：将执行以下操作：
      - 更新车牌 沪A12345 的绑定园区为"万达广场"
      - 设置状态为"已下发"

      确认执行？(y/n)

用户：y

系统：操作成功！车牌已下发到万达广场。

      结果正确吗？(正确/不对)
```

**特点**：预览 + 确认 + 结果验证

### 4.3 修正操作

```
用户：查询车牌 沪A12345 在国际商务中心停了多久

系统：（执行SQL...）
      找到 2 条停车记录：
      - 2026-03-10 10:00 - 14:30
      - 2026-03-08 09:00 - 18:00

用户：不对，应该用park_id关联

系统：明白，让我修正查询...
      （重新执行修正后的SQL...）

      找到 3 条停车记录（修正后）：
      - 2026-03-12 08:00 - 12:00
      - 2026-03-10 10:00 - 14:30
      - 2026-03-08 09:00 - 18:00

用户：这次对了

系统：（学习并记忆此操作模式）
      好的，已记住！下次查询停车时长会直接用正确的方式。
```

**特点**：支持自然语言修正 + 自动学习

---

## 五、学习记忆设计

### 5.1 存储结构

```python
# 文件：data/dev/learned_operations.json

{
  "version": "1.0.0",
  "operations": [
    {
      "id": "op_001",
      "intent": "查询停车时长",
      "trigger_patterns": ["停车多久", "停了多久", "停车时长", "多长时间"],
      "sql_template": "SELECT io.in_time, io.out_time FROM {park_db}.in_out io JOIN cloud_park p ON io.park_id = p.id WHERE io.plate = :plate AND p.name = :park_name",
      "table_insights": ["需要通过park_id关联cloud_park表"],
      "success_count": 5,
      "created_at": "2026-03-12T10:00:00",
      "last_used": "2026-03-12T14:00:00"
    },
    {
      "id": "op_002",
      "intent": "下发车牌",
      "trigger_patterns": ["下发车牌", "下发到", "同步到"],
      "sql_steps": [
        "UPDATE cloud_fixed_plate_park SET park_id = (SELECT id FROM cloud_park WHERE name = :park_name) WHERE plate_id = (SELECT id FROM cloud_fixed_plate WHERE plate = :plate)",
        "UPDATE cloud_fixed_plate SET state = 0 WHERE plate = :plate"
      ],
      "success_count": 3,
      "created_at": "2026-03-12T11:00:00",
      "last_used": "2026-03-12T15:00:00"
    }
  ]
}
```

### 5.2 记忆检索流程

```python
def find_learned_operation(user_input: str, embedding: List[float]) -> Optional[LearnedOperation]:
    """检索已学习的操作"""

    # 1. 向量相似度检索
    similar_ops = vector_store.search(embedding, top_k=3)

    # 2. 关键词匹配增强
    for op in similar_ops:
        if any(pattern in user_input for pattern in op.trigger_patterns):
            return op

    # 3. 相似度阈值判断
    if similar_ops and similar_ops[0].similarity > 0.85:
        return similar_ops[0]

    return None
```

### 5.3 学习触发条件

| 触发方式 | 说明 |
|----------|------|
| 用户说"对了"、"正确"、"OK" | 学习当前操作 |
| 用户说"不对"、修正后说"这次对了" | 学习修正后的操作 |
| 连续3次相同意图成功执行 | 自动学习 |

### 5.4 学习内容

```python
def learn_from_interaction(user_input: str, sql: str, result: str, user_feedback: str):
    """从交互中学习"""

    learned_op = LearnedOperation(
        intent=extract_intent(user_input),  # 提取意图
        trigger_patterns=extract_patterns(user_input),  # 提取触发模式
        sql_template=parameterize_sql(sql),  # 参数化SQL
        table_insights=extract_insights(sql),  # 提取表关联洞察
        success_count=1,
        created_at=now()
    )

    # 存储到向量库
    vector_store.add(learned_op)

    # 存储到JSON文件
    json_store.save(learned_op)
```

---

## 六、工具设计

### 6.1 四个核心工具

```python
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_schema",
            "description": "搜索数据库中与查询相关的表和字段",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_sql",
            "description": "执行SQL语句。SELECT直接执行，修改操作需要用户确认。",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {"type": "string", "description": "SQL语句"},
                    "description": {"type": "string", "description": "操作描述（给用户看的）"}
                },
                "required": ["sql"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_operations",
            "description": "列出系统支持的预定义操作",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_operation",
            "description": "执行预定义的业务操作",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation_id": {"type": "string", "description": "操作ID"},
                    "params": {"type": "object", "description": "操作参数"}
                },
                "required": ["operation_id"]
            }
        }
    }
]
```

### 6.2 系统提示（极简）

```python
SYSTEM_PROMPT = """你是智能停车数据库助手。

## 工作方式

1. 理解用户需求
2. 调用工具执行操作
3. 用简洁的中文返回结果

## 规则

- 查询操作直接执行，只返回结果给用户
- 修改操作需要先预览，用户确认后再执行
- 如果用户说"不对"或要求修正，重新生成并执行
- 如果用户说"对了"或"正确"，回复"好的，已记住"

## 不要

- 不要向用户显示SQL语句
- 不要问用户技术性问题
- 用自然语言描述操作内容即可"""
```

---

## 七、删除的组件

| 组件 | 文件 | 删除原因 |
|------|------|----------|
| 概念映射系统 | `src/memory/concept_store.py` | 模型已经懂 |
| 概念识别器 | `src/dialogue/concept_recognize.py` | 不需要 |
| 启动向导 | `src/dialogue/startup_wizard.py` | 不需要问问题 |
| 问题生成器 | `src/dialogue/question_generator.py` | 不需要 |
| 对话引擎 | `src/dialogue/dialogue_engine.py` | 已废弃 |
| IntentAgent | `src/agents/impl/intent_agent.py` | 模型自己判断 |
| RetrievalAgent | `src/agents/impl/retrieval_agent.py` | 封装到工具 |
| SecurityAgent | `src/agents/impl/security_agent.py` | 封装到工具 |
| PreviewAgent | `src/agents/impl/preview_agent.py` | 封装到工具 |
| ReviewAgent | `src/agents/impl/review_agent.py` | 封装到工具 |
| ExecutionAgent | `src/agents/impl/execution_agent.py` | 封装到工具 |
| KnowledgeAgent | `src/agents/impl/knowledge_agent.py` | 不需要 |
| 旧 Orchestrator | `src/agents/orchestrator.py` | 替换 |

---

## 八、新增组件

### 8.1 目录结构

```
src/
├── react/                     # 新增：ReACT 核心
│   ├── __init__.py
│   ├── orchestrator.py        # ReACT 编排器
│   ├── tools.py               # 工具定义
│   ├── tool_service.py        # 工具实现
│   └── memory.py              # 学习记忆模块
├── metadata/                  # 保留
│   ├── retrieval_pipeline.py
│   └── ...
├── executor/                  # 保留
│   └── operation_executor.py
├── knowledge/                 # 保留（预定义操作模板，可选使用）
│   └── knowledge_loader.py
├── llm_client.py              # 增强：添加工具调用支持
└── db_manager.py              # 保留
```

### 8.2 学习记忆模块

```python
# src/react/memory.py

class LearnedOperationStore:
    """学习记忆存储"""

    def __init__(self, env: str = "dev"):
        self.json_path = Path(f"data/{env}/learned_operations.json")
        self.vector_store = ChromaDBCollection("learned_operations")
        self._load()

    def find_similar(self, query: str, embedding: List[float]) -> Optional[dict]:
        """检索相似的操作"""
        pass

    def save(self, operation: dict):
        """保存学习到的操作"""
        pass

    def update_success_count(self, operation_id: str):
        """更新成功次数"""
        pass
```

---

## 九、实施计划

### 9.1 阶段划分

| 阶段 | 任务 | 预计时间 |
|------|------|----------|
| **P0** | 修复 None 问题 | 1小时 |
| **P1** | 创建 ReACT 模块框架 | 2小时 |
| **P2** | 实现工具层（4个工具） | 3小时 |
| **P3** | 实现学习记忆模块 | 3小时 |
| **P4** | 改造 LLMClient（工具调用） | 2小时 |
| **P5** | 改造 main.py | 2小时 |
| **P6** | 删除旧代码 | 1小时 |
| **P7** | 端到端测试 | 2小时 |
| **总计** | | **~16小时** |

### 9.2 验收标准

- [ ] 启动不再问问题
- [ ] "查询车牌 沪A12345" 能正确返回结果
- [ ] "下发车牌 沪A12345 到 国际商务中心" 能预览+确认+执行
- [ ] 用户说"不对"能修正
- [ ] 用户说"对了"能学习记忆
- [ ] 下次相同意图能直接用记忆的模板
- [ ] 无用组件已删除

---

## 十、风险与对策

| 风险 | 对策 |
|------|------|
| 模型生成错误SQL | 预览+确认机制，用户可修正 |
| 学习到错误模板 | 成功次数阈值，可清除记忆 |
| 记忆库污染 | 提供清除命令，定期清理 |
| Qwen工具调用不稳定 | 重试机制，fallback处理 |

---

*本设计文档整合了所有讨论要点，待用户最终确认后实施*