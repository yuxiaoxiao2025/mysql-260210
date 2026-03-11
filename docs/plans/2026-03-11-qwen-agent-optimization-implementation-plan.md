# 实施计划: Qwen Agent 优化（结构化输出/缓存/深度思考/流式输出）

## 概览
- 目标: 在现有 `LLMClient + API` 链路上以 TDD 方式落地结构化输出、上下文缓存、深度思考与流式输出能力，并保证回归兼容。
- 预计工期: 40.8h (含20 %缓冲)
- 关键里程碑: M1-契约测试就绪, M2-结构化输出与缓存落地, M3-深度思考与流式输出联调通过

## 任务清单

### Phase 1: 基线与契约（P0）
- [ ] Task 1.1: 梳理调用面与新增配置开关（预估: 3h, 优先级: P0）
  - 依赖: none
  - 文件路径: `e:\trae-pc\mysql260227\src\llm_client.py`, `e:\trae-pc\mysql260227\src\api\models.py`, `e:\trae-pc\mysql260227\src\api\deps.py`
  - 验收: 明确新增开关（`enable_structured_output`/`enable_thinking`/`enable_stream`/`enable_prompt_cache`）默认值与兼容策略；配置读取单测可运行。
  - 验证命令: `pytest tests/unit -k "llm_client or api_models" -q`
- [ ] Task 1.2: 先写失败测试（结构化输出与流式契约）（预估: 4h, 优先级: P0）
  - 依赖: 1.1
  - 文件路径: `e:\trae-pc\mysql260227\tests\unit\test_llm_client_structured_output.py`, `e:\trae-pc\mysql260227\tests\unit\test_llm_client_streaming.py`
  - 验收: 覆盖 JSON schema/object 两模式、thinking 与 structured 互斥、stream chunk 合并与 usage 收集；初次执行失败且失败原因正确。
  - 验证命令: `pytest tests/unit/test_llm_client_structured_output.py tests/unit/test_llm_client_streaming.py -q`

### Phase 2: 结构化输出与缓存（P0）
- [ ] Task 2.1: 实现结构化输出策略与响应解析器（预估: 5h, 优先级: P0）
  - 依赖: 1.2
  - 文件路径: `e:\trae-pc\mysql260227\src\llm_client.py`, `e:\trae-pc\mysql260227\src\handlers\error_handler.py`
  - 验收: 非思考模式支持 `json_schema/json_object`；JSON 解析失败时输出可观测错误；不破坏现有 `generate_sql/recognize_intent` 返回结构。
  - 验证命令: `pytest tests/unit/test_llm_client_structured_output.py -q`
- [ ] Task 2.2: 实现显式上下文缓存注入与命中统计（预估: 4h, 优先级: P0）
  - 依赖: 2.1
  - 文件路径: `e:\trae-pc\mysql260227\src\llm_client.py`, `e:\trae-pc\mysql260227\src\monitoring\metrics_collector.py`
  - 验收: 长 system/context 段可注入 `cache_control: {"type":"ephemeral"}`；记录 `cache_creation_input_tokens/cached_tokens`；不支持模型自动降级为隐式缓存路径。
  - 验证命令: `pytest tests/unit -k "cache and llm_client" -q`

### Phase 3: 深度思考与流式输出（P0）
- [ ] Task 3.1: 增加深度思考模式与双阶段 JSON 修复流程（预估: 6h, 优先级: P0）
  - 依赖: 2.2
  - 文件路径: `e:\trae-pc\mysql260227\src\llm_client.py`, `e:\trae-pc\mysql260227\src\config.py`
  - 验收: thinking 模式走 `stream=True` + `enable_thinking`；当 thinking 与 structured 冲突时自动切换为“thinking 产出 + 非 thinking 修复为标准 JSON”；错误链路可追踪。
  - 验证命令: `pytest tests/unit -k "thinking or json_fix" -q`
- [ ] Task 3.2: 实现 API 层流式输出接口（SSE）（预估: 6h, 优先级: P0）
  - 依赖: 3.1
  - 文件路径: `e:\trae-pc\mysql260227\src\api\routes\query.py`, `e:\trae-pc\mysql260227\src\api\models.py`
  - 验收: 新增流式路由（如 `/query/confirm_stream`）返回增量 chunk、reasoning 与 usage；客户端中断时安全收尾；非流式接口行为不变。
  - 验证命令: `pytest tests/integration -k "stream or query_confirm" -q`

### Phase 4: 回归、观测与发布准备（P1）
- [ ] Task 4.1: 补齐集成测试与回归测试矩阵（预估: 4h, 优先级: P1）
  - 依赖: 3.2
  - 文件路径: `e:\trae-pc\mysql260227\tests\integration\test_qwen_agent_optimization.py`, `e:\trae-pc\mysql260227\tests\integration\conftest.py`
  - 验收: 覆盖 4 大能力组合（structured-only、cache+structured、thinking-only、thinking+stream）；关键异常路径有断言。
  - 验证命令: `pytest tests/integration/test_qwen_agent_optimization.py -q`
- [ ] Task 4.2: 指标与手工验收脚本（预估: 2h, 优先级: P1）
  - 依赖: 4.1
  - 文件路径: `e:\trae-pc\mysql260227\scripts\manual_test_qwen_agent_optimization.py`, `e:\trae-pc\mysql260227\src\monitoring\metrics_collector.py`
  - 验收: 可输出首 token 延迟、总耗时、cache 命中 token、JSON 修复触发次数；脚本能复现至少 2 条业务查询。
  - 验证命令: `python scripts/manual_test_qwen_agent_optimization.py`

## 依赖关系图
[Task 1.1] --> [Task 1.2] --> [Task 2.1] --> [Task 2.2] --> [Task 3.1] --> [Task 3.2] --> [Task 4.1] --> [Task 4.2]

关键路径(P0): 1.1 -> 1.2 -> 2.1 -> 2.2 -> 3.1 -> 3.2

## 风险与缓解
- 风险: thinking 模式与结构化输出存在协议冲突 | 缓解: 固化双阶段策略（thinking 生成 + 非 thinking JSON 修复）并加集成测试守护
- 风险: 显式缓存命中不稳定（上下文长度、模型差异） | 缓解: 增加命中指标埋点与模型能力白名单，未命中自动降级
- 风险: SSE 中断导致资源泄漏或状态不一致 | 缓解: 在路由与客户端迭代器中实现 finally 收尾与超时保护
- 风险: 第三方 API 变更（DashScope 参数/字段） | 缓解: 封装请求适配层并对 `usage/prompt_tokens_details` 做兼容解析
- 外部依赖: `DASHSCOPE_API_KEY`、可用的 Qwen 模型版本（支持 thinking/stream/cache 的组合）、稳定网络环境

## 完成清单
- [ ] 完成 Task 1.1 并通过对应单测
- [ ] 完成 Task 1.2 并确认测试先失败后通过
- [ ] 完成 Task 2.1 并验证结构化输出稳定
- [ ] 完成 Task 2.2 并验证缓存命中统计
- [ ] 完成 Task 3.1 并验证 thinking 双阶段 JSON 修复
- [ ] 完成 Task 3.2 并验证 SSE 流式输出链路
- [ ] 完成 Task 4.1 并通过集成回归
- [ ] 完成 Task 4.2 并产出性能与命中观测结果
