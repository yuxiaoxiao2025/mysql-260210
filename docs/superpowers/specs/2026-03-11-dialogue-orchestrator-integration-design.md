# 对话引擎与多智能体架构融合设计

**日期：** 2026-03-11  
**状态：** 已批准

## 1. 概述

将DialogueEngine的概念学习能力整合到多智能体架构中，实现统一的对话和业务操作处理流程。废弃DialogueEngine作为独立组件，将其核心能力分散到IntentAgent和Orchestrator中。

## 2. 问题分析

### 2.1 当前问题

**双轨制混乱：**
- main.py的chat模式使用DialogueEngine
- main.py的普通模式使用Orchestrator
- 两套系统职责重叠，无法协同

**意图识别不完整：**
- IntentAgent能识别chat/qa意图，但处理逻辑在DialogueEngine中
- 概念学习逻辑被困在DialogueEngine，Orchestrator无法使用

**用户体验问题：**
- 用户问"你可以正常和我对话吗"
- DialogueEngine不知道如何处理普通对话
- 错误地进入"执行相关操作"确认流程

### 2.2 根本原因

DialogueEngine设计时假设所有输入都是业务操作，缺少对普通对话和知识问答的支持。

## 3. 设计目标

1. **统一入口**：所有用户输入通过Orchestrator处理
2. **智能路由**：根据意图类型路由到不同的Agent链
3. **概念学习**：IntentAgent整合概念识别和学习能力
4. **流式体验**：知识问答和闲聊支持实时流式输出
5. **Agent独立**：每个Agent可独立升级模型和逻辑

## 4. 架构设计

### 4.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                         用户输入                              │
└────────────────────────┬────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│                    Orchestrator                              │
│  - 统一入口                                                   │
│  - 维护对话上下文 (chat_history)                              │
│  - 智能路由                                                   │
└────────────────────────┬────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│                    IntentAgent                               │
│  - 意图识别 (chat/qa/query/mutation)                         │
│  - 概念识别 (ConceptRecognizer)                              │
│  - 概念学习 (ConceptStore)                                   │
│  - 澄清问题生成 (QuestionGenerator)                          │
└────────────────────────┬────────────────────────────────────┘
                         ↓
              ┌──────────┴──────────┐
              ↓                     ↓
    ┌─────────────────┐   ┌─────────────────┐
    │  业务操作流程    │   │  对话/问答流程   │
    └─────────────────┘   └─────────────────┘
              ↓                     ↓
    RetrievalAgent        RetrievalAgent
              ↓                     ↓
    SecurityAgent         KnowledgeAgent
              ↓                (流式输出)
    PreviewAgent
              ↓
    ReviewAgent
              ↓
    ExecutionAgent
```

### 4.2 Agent职责

| Agent | 职责 | 输入 | 输出 |
|-------|------|------|------|
| **IntentAgent** | 意图识别、概念学习、澄清问题生成 | user_input, chat_history, concept_store | intent (type, need_clarify, reasoning) |
| **RetrievalAgent** | Schema检索、上下文增强 | user_input, intent | schema_context |
| **KnowledgeAgent** | 知识问答、闲聊（流式） | user_input, schema_context | generator (thinking + content) |
| **SecurityAgent** | SQL安全检查 | intent.sql | is_safe, security_report |
| **PreviewAgent** | 变更预览 | intent, schema_context | preview_data |
| **ReviewAgent** | 执行前确认 | intent, preview_data | next_action (continue/ask_user) |
| **ExecutionAgent** | 执行操作 | intent, preview_data | execution_result |

### 4.3 数据模型

**IntentModel增强：**
```python
class IntentModel(BaseModel):
    type: Literal["query", "mutation", "chat", "qa", "clarify"]
    confidence: float
    operation_id: Optional[str] = None
    params: Dict[str, Any] = {}
    sql: Optional[str] = None
    reasoning: str = ""
    
    # 概念学习相关
    need_clarify: bool = False
    clarification_question: Optional[str] = None
    unrecognized_concepts: List[str] = []
```

**AgentContext增强：**
```python
class AgentContext(BaseModel):
    user_input: str
    chat_history: List[Dict[str, str]] = []  # 多轮对话历史
    
    # Agent间传递的数据
    intent: Optional[IntentModel] = None
    schema_context: Optional[str] = None
    is_safe: bool = False
    preview_data: Optional[Any] = None
    execution_result: Optional[Any] = None
    
    # 概念学习状态
    learned_concepts: List[ConceptMapping] = []
    pending_clarification: bool = False
    
    # 审计和调试
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    step_history: List[str] = []
```

## 5. 核心流程

### 5.1 普通对话流程

```
用户: "你可以正常和我对话吗"
  ↓
Orchestrator.process(user_input, chat_history)
  ↓
IntentAgent.run(context)
  - 识别: type="chat", confidence=0.95
  - need_clarify=False
  ↓
Orchestrator检测到type="chat"
  ↓
跳过Security/Preview/Review
  ↓
RetrievalAgent.run(context)  # 可选，获取相关schema
  ↓
KnowledgeAgent.run(context)
  - 返回: generator (流式chunks)
  ↓
Main.py实时打印chunks
  - "当然可以！我是你的停车数据库助手..."
```

### 5.2 概念学习流程

```
用户: "查询ROI"
  ↓
IntentAgent.run(context)
  - ConceptRecognizer识别到"ROI"未知
  - 设置: need_clarify=True
  - 生成: clarification_question="请问ROI具体指什么？"
  - unrecognized_concepts=["ROI"]
  ↓
Orchestrator检测到need_clarify=True
  - 返回context给main.py
  ↓
Main.py显示澄清问题，等待用户输入
  ↓
用户: "投资回报率"
  ↓
Orchestrator.process("投资回报率", chat_history=[
    {"role": "assistant", "content": "请问ROI具体指什么？"},
    {"role": "user", "content": "投资回报率"}
])
  ↓
IntentAgent.run(context)
  - 检测到chat_history中有澄清上下文
  - 学习概念: ConceptStore.add("ROI" → "投资回报率")
  - 重新识别原始意图
  - 设置: need_clarify=False
  ↓
继续正常业务流程
```

### 5.3 业务操作流程

```
用户: "查询沪BAB1565的信息"
  ↓
IntentAgent.run(context)
  - 识别: type="query", operation_id="plate_query"
  - params={"plate": "沪BAB1565"}
  ↓
RetrievalAgent.run(context)
  - 检索相关表结构
  ↓
SecurityAgent.run(context)
  - 验证SQL安全
  ↓
ReviewAgent.run(context)
  - 查询类操作，自动通过
  ↓
ExecutionAgent.run(context)
  - 执行查询，返回结果
```

## 6. 实现细节

### 6.1 IntentAgent增强

**新增依赖：**
```python
class IntentAgent(BaseAgent):
    def __init__(
        self, 
        config: IntentAgentConfig,
        llm_client: LLMClient,
        knowledge_loader: KnowledgeLoader,
        concept_store: ConceptStoreService
    ):
        self.recognizer = IntentRecognizer(llm_client, knowledge_loader)
        self.concept_recognizer = ConceptRecognizer(concept_store)
        self.question_generator = QuestionGenerator()
        self.concept_store = concept_store
```

**核心逻辑：**
```python
def _run_impl(self, context: AgentContext) -> AgentResult:
    # 1. 检查是否是澄清回答
    if self._is_clarification_response(context):
        return self._handle_clarification(context)
    
    # 2. 识别概念
    concepts = self.concept_recognizer.recognize(context.user_input)
    unrecognized = [c for c in concepts if c.needs_clarification]
    
    # 3. 如果有未识别概念，生成澄清问题
    if unrecognized:
        return self._generate_clarification(context, unrecognized)
    
    # 4. 正常意图识别
    recognized = self.recognizer.recognize(context.user_input)
    
    # 5. 映射到IntentModel
    context.intent = self._map_to_intent_model(recognized)
    
    return AgentResult(success=True, data=context.intent)
```

### 6.2 Orchestrator路由逻辑

```python
def process(self, user_input: str, chat_history: List[Dict] = None) -> AgentContext:
    context = AgentContext(
        user_input=user_input,
        chat_history=chat_history or []
    )
    
    # 1. 意图识别
    intent_result = self.intent_agent.run(context)
    if not intent_result.success:
        return context
    
    # 2. 检查是否需要澄清
    if context.intent.need_clarify:
        context.pending_clarification = True
        return context  # 返回给用户，等待澄清
    
    # 3. 根据意图类型路由
    if context.intent.type in ["chat", "qa"]:
        return self._handle_conversation(context)
    elif context.intent.type in ["query", "mutation"]:
        return self._handle_business_operation(context)
    else:
        return context

def _handle_conversation(self, context: AgentContext) -> AgentContext:
    """处理对话和知识问答"""
    # 检索相关schema（可选）
    self.retrieval_agent.run(context)
    
    # 流式问答
    knowledge_result = self.knowledge_agent.run(context)
    context.execution_result = knowledge_result.data  # generator
    context.step_history.append("knowledge")
    
    return context

def _handle_business_operation(self, context: AgentContext) -> AgentContext:
    """处理业务操作"""
    # 完整的业务流程
    self.retrieval_agent.run(context)
    
    if not self.security_agent.run(context).success:
        return context
    
    if context.intent.type == "mutation":
        self.preview_agent.run(context)
    
    review_result = self.review_agent.run(context)
    if review_result.next_action == "ask_user":
        return context  # 等待用户确认
    
    self.execution_agent.run(context)
    return context
```

### 6.3 Main.py统一处理

```python
def chat_mode(orchestrator: Orchestrator):
    """统一的chat模式"""
    print("进入对话模式")
    print("你好，我是你的停车数据库助手，有什么可以帮你？")
    
    chat_history = []
    
    while True:
        user_input = input("\n[对话] > ").strip()
        if not user_input:
            continue
        
        if user_input.lower() in ['exit', 'quit', '退出']:
            print("退出对话模式")
            break
        
        # 统一调用Orchestrator
        context = orchestrator.process(user_input, chat_history)
        
        # 处理澄清
        if context.pending_clarification:
            print(f"\n[助手] {context.intent.clarification_question}")
            chat_history.append({
                "role": "assistant",
                "content": context.intent.clarification_question
            })
            chat_history.append({
                "role": "user",
                "content": user_input
            })
            continue
        
        # 处理确认
        if context.step_history and "review" in context.step_history:
            review_result = context.execution_result
            if review_result.next_action == "ask_user":
                print(f"\n[助手] {review_result.message}")
                confirm = input("确认执行？(y/n) > ").strip().lower()
                if confirm == 'y':
                    context = orchestrator.process(
                        user_input, 
                        chat_history,
                        user_confirmation=True
                    )
                else:
                    print("[助手] 已取消操作")
                    continue
        
        # 处理流式输出
        if isinstance(context.execution_result, types.GeneratorType):
            print("\n[助手] ", end="", flush=True)
            for chunk in context.execution_result:
                if chunk["type"] == "thinking":
                    # 可选：显示思考过程
                    pass
                elif chunk["type"] == "content":
                    print(chunk["content"], end="", flush=True)
            print()  # 换行
        else:
            # 非流式结果
            print(f"\n[助手] {context.execution_result}")
        
        # 更新对话历史
        chat_history.append({"role": "user", "content": user_input})
        # assistant的回复已经通过流式输出显示，这里只记录
```

## 7. 废弃组件

### 7.1 完全删除

- `src/dialogue/dialogue_engine.py` - DialogueEngine类
- `src/dialogue/dialogue_engine.py` - DialogueState枚举
- `src/dialogue/dialogue_engine.py` - DialogueResponse类

### 7.2 保留为工具类

- `src/dialogue/concept_recognizer.py` - ConceptRecognizer（IntentAgent使用）
- `src/dialogue/question_generator.py` - QuestionGenerator（IntentAgent使用）
- `src/memory/concept_store.py` - ConceptStoreService（IntentAgent使用）
- `src/memory/context_memory.py` - ContextMemoryService（可选，用于高级对话管理）

## 8. 迁移策略

### 8.1 阶段1：IntentAgent增强（不破坏现有功能）

1. 为IntentAgent添加concept_store参数（可选）
2. 实现概念识别和学习逻辑
3. 保持向后兼容，不影响现有业务流程
4. 测试：单元测试验证概念学习功能

### 8.2 阶段2：Orchestrator路由增强

1. 添加chat_history参数支持
2. 实现智能路由逻辑（chat/qa vs business）
3. 添加澄清循环处理
4. 测试：集成测试验证完整流程

### 8.3 阶段3：Main.py统一

1. 修改chat模式，使用Orchestrator替代DialogueEngine
2. 实现流式输出处理
3. 实现澄清和确认循环
4. 测试：手工测试验证用户体验

### 8.4 阶段4：清理

1. 删除DialogueEngine相关代码
2. 更新文档和注释
3. 回归测试确保无破坏性变更

## 9. 测试策略

### 9.1 单元测试

**IntentAgent概念学习：**
```python
def test_intent_agent_concept_learning():
    """测试概念学习流程"""
    agent = IntentAgent(config, llm_client, knowledge_loader, concept_store)
    
    # 第一次：未知概念
    context = AgentContext(user_input="查询ROI")
    result = agent.run(context)
    assert context.intent.need_clarify is True
    assert "ROI" in context.intent.unrecognized_concepts
    
    # 第二次：学习概念
    context = AgentContext(
        user_input="投资回报率",
        chat_history=[
            {"role": "assistant", "content": "请问ROI具体指什么？"},
            {"role": "user", "content": "投资回报率"}
        ]
    )
    result = agent.run(context)
    
    # 验证概念已学习
    concept = concept_store.find_by_user_term("ROI")
    assert concept is not None
    assert "投资回报率" in concept.description
```

**Orchestrator路由：**
```python
def test_orchestrator_chat_routing():
    """测试对话路由"""
    orch = Orchestrator(...)
    context = orch.process("你好")
    
    assert "knowledge" in context.step_history
    assert isinstance(context.execution_result, types.GeneratorType)

def test_orchestrator_business_routing():
    """测试业务操作路由"""
    orch = Orchestrator(...)
    context = orch.process("查询车牌沪A12345")
    
    assert "intent" in context.step_history
    assert "retrieval" in context.step_history
    assert "security" in context.step_history
    assert "execution" in context.step_history
```

### 9.2 集成测试

**完整对话流程：**
```python
def test_full_conversation_flow():
    """测试完整对话流程"""
    orch = Orchestrator(...)
    
    # 普通对话
    context = orch.process("你好")
    assert context.execution_result is not None
    
    # 知识问答
    context = orch.process("数据库有哪些表？")
    assert "knowledge" in context.step_history
    
    # 业务操作
    context = orch.process("查询车牌沪A12345")
    assert "execution" in context.step_history
```

**概念学习流程：**
```python
def test_concept_learning_flow():
    """测试概念学习流程"""
    orch = Orchestrator(...)
    
    # 第一次：触发澄清
    context = orch.process("查询ROI")
    assert context.pending_clarification is True
    
    # 第二次：学习并继续
    context = orch.process(
        "投资回报率",
        chat_history=[...]
    )
    assert context.pending_clarification is False
    assert "execution" in context.step_history
```

### 9.3 手工测试场景

1. **普通对话**
   - 输入："你可以正常和我对话吗"
   - 期望：流式输出友好回复

2. **知识问答**
   - 输入："数据库有哪些表？"
   - 期望：基于schema_context流式回答

3. **概念学习**
   - 输入："查询ROI"
   - 期望：询问"ROI具体指什么？"
   - 输入："投资回报率"
   - 期望：学习概念并继续查询

4. **业务操作**
   - 输入："查询车牌沪BAB1565"
   - 期望：正常执行并返回结果

5. **变更确认**
   - 输入："删除车牌沪A12345"
   - 期望：显示预览并要求确认

## 10. 性能和可观测性

### 10.1 性能指标

- **首token延迟**：KnowledgeAgent流式输出的首个chunk延迟
- **概念学习命中率**：已学习概念的复用率
- **路由准确率**：IntentAgent意图分类的准确率

### 10.2 日志和追踪

```python
# 在AgentContext中记录关键事件
context.step_history = [
    "intent",           # IntentAgent完成
    "concept_learned",  # 学习了新概念
    "retrieval",        # RetrievalAgent完成
    "knowledge",        # KnowledgeAgent完成（对话）
    "security",         # SecurityAgent完成
    "preview",          # PreviewAgent完成
    "review",           # ReviewAgent完成
    "execution"         # ExecutionAgent完成
]

# 使用trace_id关联整个请求链路
logger.info(f"[{context.trace_id}] IntentAgent: type={context.intent.type}")
```

## 11. 风险和缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 概念学习逻辑迁移出错 | 用户无法学习新概念 | 充分的单元测试，保留原ConceptStore逻辑 |
| 流式输出中断 | 用户体验差 | 添加异常处理和超时保护 |
| 路由逻辑错误 | 业务操作被误判为对话 | 添加置信度阈值和fallback机制 |
| 对话历史过长 | 内存占用高 | 限制chat_history长度（如最近20轮） |
| DialogueEngine删除后回归问题 | 现有功能受影响 | 分阶段迁移，充分测试后再删除 |

## 12. 后续优化方向

1. **多轮对话上下文管理**
   - 使用ContextMemoryService管理长期对话状态
   - 支持代词引用解析（"它"、"这个"等）

2. **Agent独立升级**
   - 为每个Agent添加版本号和配置
   - 支持A/B测试不同的模型配置

3. **智能缓存**
   - 缓存常见问题的schema_context
   - 缓存已学习的概念映射

4. **多模态支持**
   - 支持图片输入（如车牌照片识别）
   - 支持语音输入输出

## 13. 验收标准

### 13.1 功能验收

- [ ] 用户输入"你可以正常和我对话吗"，系统流式输出友好回复
- [ ] 用户输入"数据库有哪些表"，系统基于schema回答
- [ ] 用户输入未知概念（如"ROI"），系统询问并学习
- [ ] 用户输入业务操作，系统正常执行
- [ ] 用户输入变更操作，系统要求确认

### 13.2 性能验收

- [ ] 流式输出首token延迟 < 2秒
- [ ] 概念学习后，相同概念识别成功率 > 95%
- [ ] 意图路由准确率 > 90%

### 13.3 代码质量验收

- [ ] 单元测试覆盖率 > 80%
- [ ] 集成测试覆盖核心流程
- [ ] 无明显代码重复
- [ ] 所有Agent职责清晰，接口统一

## 14. 总结

本设计通过将DialogueEngine的核心能力整合到IntentAgent和Orchestrator中，实现了统一的多智能体架构。关键改进包括：

1. **统一入口**：所有请求通过Orchestrator处理
2. **智能路由**：根据意图类型自动选择处理流程
3. **概念学习**：IntentAgent负责概念识别和学习
4. **流式体验**：KnowledgeAgent提供实时流式输出
5. **职责清晰**：每个Agent独立可升级

这个架构既满足了业务操作的需求，也提供了良好的对话体验，为未来的功能扩展奠定了坚实基础。
