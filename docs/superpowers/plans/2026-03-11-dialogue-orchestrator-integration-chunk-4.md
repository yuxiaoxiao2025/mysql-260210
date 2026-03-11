# Chunk 4: Main.py统一chat模式

> **前置依赖：** [Chunk 3: Orchestrator路由增强](./2026-03-11-dialogue-orchestrator-integration-chunk-3.md)
> **后续文件：** [Chunk 5: 集成测试和清理](./2026-03-11-dialogue-orchestrator-integration-chunk-5.md)

---

### Task 9: Main.py修改chat模式使用Orchestrator

**Files:**
- Modify: `main.py`
- Test: 手工测试

- [ ] **Step 1: 备份当前chat模式实现**

```bash
# 创建备份分支
git checkout -b backup-dialogue-engine
git checkout main
```

- [ ] **Step 2: 修改main.py的chat模式**

```python
# main.py (找到chat模式的代码，大约在259-297行)
# 替换为以下实现：

# 新增：chat 命令 - 进入对话模式（使用Orchestrator）
if user_input.lower() == 'chat':
    print("\n" + "=" * 60)
    print("进入对话模式")
    print("你好，我是你的停车数据库助手，有什么可以帮你？")
    print("输入 'exit' 或 'quit' 退出对话模式")
    print("=" * 60)

    chat_history = []

    while True:
        try:
            chat_input = input("\n[对话] > ").strip()
            if not chat_input:
                continue

            if chat_input.lower() in ['exit', 'quit', '退出']:
                print("退出对话模式")
                break

            # 使用Orchestrator处理输入
            context = orchestrator.process(chat_input, chat_history)

            # 处理澄清
            if context.pending_clarification:
                print(f"\n[助手] {context.intent.clarification_question}")
                chat_history.append({
                    "role": "assistant",
                    "content": context.intent.clarification_question
                })
                chat_history.append({
                    "role": "user",
                    "content": chat_input
                })
                continue

            # 处理确认（ReviewAgent）
            if context.step_history and "review" in context.step_history:
                from src.agents.models import AgentResult
                if isinstance(context.execution_result, AgentResult):
                    if context.execution_result.next_action == "ask_user":
                        print(f"\n[助手] {context.execution_result.message}")
                        confirm = input("确认执行？(y/n) > ").strip().lower()
                        if confirm == 'y':
                            context = orchestrator.process(
                                chat_input,
                                chat_history,
                                user_confirmation=True
                            )
                        else:
                            print("[助手] 已取消操作")
                            continue

            # 处理流式输出
            import types
            if isinstance(context.execution_result, types.GeneratorType):
                print("\n[助手] ", end="", flush=True)
                for chunk in context.execution_result:
                    if chunk.get("type") == "thinking":
                        # 可选：显示思考过程
                        pass
                    elif chunk.get("type") == "content":
                        print(chunk.get("content", ""), end="", flush=True)
                print()  # 换行
            else:
                # 非流式结果（业务操作）
                if context.execution_result:
                    print(f"\n[助手] 操作已完成")
                else:
                    print(f"\n[助手] 处理完成")

            # 更新对话历史
            chat_history.append({"role": "user", "content": chat_input})

        except KeyboardInterrupt:
            print("\n退出对话模式")
            break
        except Exception as e:
            logger.error(f"对话模式错误: {e}", exc_info=True)
            print(f"[ERR] 对话出错: {e}")

    print("=" * 60)
    continue
```

- [ ] **Step 3: 确保Orchestrator在main.py中正确初始化**

检查main.py中orchestrator的初始化，确保包含concept_store：

```python
# main.py (在orchestrator初始化部分)
from src.agents.orchestrator import Orchestrator

# 初始化Orchestrator（确保传入concept_store）
orchestrator = Orchestrator(
    llm_client=llm_client,
    knowledge_loader=knowledge_loader
)

# 为IntentAgent注入concept_store
orchestrator.intent_agent.concept_store = concept_store
orchestrator.intent_agent.concept_recognizer = ConceptRecognizer(concept_store)
orchestrator.intent_agent.question_generator = QuestionGenerator()
```

- [ ] **Step 4: 手工测试chat模式**

Run: `python main.py`

测试场景1：普通对话
```
[MySQL/AI] > chat
[对话] > 你可以正常和我对话吗
期望：流式输出友好回复
```

测试场景2：知识问答
```
[对话] > 数据库有哪些表？
期望：基于schema流式回答
```

测试场景3：概念学习
```
[对话] > 查询ROI
期望：询问"ROI具体指什么？"
[对话] > 投资回报率
期望：学习概念并继续
```

- [ ] **Step 5: 提交**

```bash
git add main.py
git commit -m "feat(main): 统一chat模式使用Orchestrator，支持对话、澄清和业务操作"
```

---

**Chunk 4 完成！** 继续执行 [Chunk 5: 集成测试和清理](./2026-03-11-dialogue-orchestrator-integration-chunk-5.md)