# DialogueEngine迁移指南

## 概述

DialogueEngine已被废弃，其功能已整合到多智能体架构中：
- **概念学习** → IntentAgent
- **对话流程管理** → Orchestrator
- **流式输出** → KnowledgeAgent

## 迁移步骤

### 旧代码（使用DialogueEngine）

```python
from src.dialogue.dialogue_engine import DialogueEngine

dialogue_engine = DialogueEngine(
    concept_store=concept_store,
    context_memory=context_memory
)

response = dialogue_engine.process_input(user_input)
print(response.message)
```

### 新代码（使用Orchestrator）

```python
from src.agents.orchestrator import Orchestrator

orchestrator = Orchestrator(
    llm_client=llm_client,
    knowledge_loader=knowledge_loader
)

# 注入concept_store到IntentAgent
orchestrator.intent_agent.concept_store = concept_store
orchestrator.intent_agent.concept_recognizer = ConceptRecognizer(concept_store)
orchestrator.intent_agent.question_generator = QuestionGenerator()

# 处理输入
chat_history = []
context = orchestrator.process(user_input, chat_history)

# 处理澄清
if context.pending_clarification:
    print(context.intent.clarification_question)
    # 等待用户回答...

# 处理流式输出
import types
if isinstance(context.execution_result, types.GeneratorType):
    for chunk in context.execution_result:
        if chunk["type"] == "content":
            print(chunk["content"], end="", flush=True)
```

## 功能对照表

| DialogueEngine | 新架构 | 说明 |
|----------------|--------|------|
| `process_input()` | `Orchestrator.process()` | 统一入口 |
| `DialogueState.CLARIFYING` | `context.pending_clarification` | 澄清状态 |
| `DialogueResponse.message` | `context.intent.clarification_question` | 澄清问题 |
| `DialogueResponse.options` | `context.intent.unrecognized_concepts` | 未识别概念 |
| `_learn_concept()` | `IntentAgent._handle_clarification()` | 概念学习 |
| `reset()` | 创建新的chat_history | 重置对话 |

## 优势

1. **职责清晰**：每个Agent专注单一职责
2. **易于测试**：可独立测试每个Agent
3. **易于扩展**：可单独升级某个Agent的模型或逻辑
4. **统一入口**：所有对话和业务操作通过Orchestrator统一处理

## 常见问题

**Q: 我需要修改现有代码吗？**
A: 如果你在使用main.py的chat模式，不需要修改。如果直接使用DialogueEngine，请参考迁移指南更新代码。

**Q: 概念学习数据会丢失吗？**
A: 不会。概念数据存储在concept_store中，迁移后继续可用。

**Q: 可以继续使用DialogueEngine吗？**
A: 不建议。DialogueEngine已废弃，未来版本将移除。请尽快迁移到Orchestrator。

## 相关文档
- [设计文档](../superpowers/specs/2026-03-11-dialogue-orchestrator-integration-design.md)
- [实施计划](../superpowers/plans/2026-03-11-dialogue-orchestrator-integration-index.md)
