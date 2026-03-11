# 对话引擎与多智能体架构融合实施计划（索引）

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将DialogueEngine的概念学习能力整合到IntentAgent和Orchestrator中，实现统一的对话和业务操作处理流程，废弃DialogueEngine作为独立组件。

**Architecture:** 采用分阶段迁移策略，先增强IntentAgent和Orchestrator，再统一main.py的chat模式，最后清理废弃代码。每个阶段保持向后兼容，确保现有功能不受影响。

**Tech Stack:** Python 3.10+, Pydantic, Pytest, TDD

---

## 计划文件索引

本文档已按逻辑拆分为以下独立文件，请按顺序执行：

| 序号 | 文件名 | 内容 | Task范围 |
|------|--------|------|----------|
| 1 | `2026-03-11-dialogue-orchestrator-integration-chunk-1.md` | 数据模型增强 | Task 1-2 |
| 2 | `2026-03-11-dialogue-orchestrator-integration-chunk-2.md` | IntentAgent概念学习增强 | Task 3-5 |
| 3 | `2026-03-11-dialogue-orchestrator-integration-chunk-3.md` | Orchestrator路由增强 | Task 6-8 |
| 4 | `2026-03-11-dialogue-orchestrator-integration-chunk-4.md` | Main.py统一chat模式 | Task 9 |
| 5 | `2026-03-11-dialogue-orchestrator-integration-chunk-5.md` | 集成测试和清理 | Task 10-13 |

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

## 架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         Orchestrator                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ IntentAgent │  │RetrievalAgent│  │KnowledgeAgent│             │
│  │  (增强)     │  │             │  │             │              │
│  │ +概念识别   │  │             │  │             │              │
│  │ +概念学习   │  │             │  │             │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
│         │                │                │                      │
│         ▼                ▼                ▼                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │SecurityAgent│  │ PreviewAgent│  │ExecutionAgent│             │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

**关键变更：**
1. **IntentAgent增强**：添加概念识别（ConceptRecognizer）和概念学习（从澄清回答中学习）功能
2. **Orchestrator智能路由**：根据intent.type路由到对话流程（chat/qa）或业务操作流程（query/mutation）
3. **澄清循环**：通过`context.pending_clarification`标志控制澄清流程
4. **废弃DialogueEngine**：作为独立组件删除，功能整合到多智能体架构

---

## 验收标准

### 功能验收

- [ ] AgentContext支持chat_history、pending_clarification、learned_concepts字段
- [ ] IntentModel支持clarification_question、unrecognized_concepts字段
- [ ] IntentAgent能识别未知概念并生成澄清问题
- [ ] IntentAgent能从澄清回答中学习概念
- [ ] Orchestrator能根据intent类型智能路由
- [ ] Orchestrator能处理澄清循环
- [ ] main.py的chat模式使用Orchestrator
- [ ] DialogueEngine被废弃，相关测试通过
- [ ] 所有现有测试继续通过（无破坏性变更）

### 性能验收

- [ ] 意图识别延迟 < 500ms
- [ ] 概念学习不影响正常流程性能
- [ ] 流式输出首字节延迟 < 1s

### 代码质量验收

- [ ] 单元测试覆盖率 > 80%
- [ ] 所有测试通过
- [ ] 无pylint警告
- [ ] 迁移文档完整

---

## 风险和缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 现有chat功能中断 | 高 | 先在备份分支测试，逐步迁移 |
| 概念学习影响性能 | 中 | 概念识别只在特定场景触发 |
| 测试覆盖不足 | 中 | 每个Task都有对应的单元测试 |
| 迁移文档不清晰 | 低 | 提供详细的迁移指南和代码示例 |

---

## 总结

本计划将DialogueEngine的功能整合到多智能体架构中，实现：
1. **统一入口**：所有对话通过Orchestrator.process()处理
2. **职责清晰**：概念学习在IntentAgent，对话流程在Orchestrator
3. **易于扩展**：可独立升级各Agent的实现
4. **向后兼容**：现有功能不受影响，渐进式迁移

**下一步：** 开始执行 [Chunk 1: 数据模型增强](./2026-03-11-dialogue-orchestrator-integration-chunk-1.md)