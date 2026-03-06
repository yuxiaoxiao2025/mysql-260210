# Qwen3-Rerank + Embedding v4 设计方案

**日期:** 2026-03-06  
**范围:** 元数据检索增强（向量召回 + 两层 Rerank + 语义补全）  
**推荐方案:** 方案 B（text-embedding-v4 + 两层 Rerank + 语义补全）

**目标**
- 将自然语言查询的表/字段命中率显著提升，支持跨表关联准确召回。
- 将两层 Rerank 总耗时稳定控制在 500ms 预算内。
- 覆盖率优先完成 9000+ 表元数据语义补全，作为向量与精排的统一输入。

**非目标**
- 不引入多模态向量。
- 不在本阶段改造业务 SQL 生成器的核心逻辑。
- 不引入独立的图数据库（仍使用 JSON 知识图谱）。

**现状概览**
- 向量库为 ChromaDB 持久化存储，路径 `data/{env}/chroma_db`。
- 知识图谱为 JSON 文件 `data/{env}/table_graph.json`。
- 表/字段向量由 `EmbeddingService` 生成，当前默认 `text-embedding-v3`，维度 1024。
- 检索入口为 `RetrievalAgent`，具备向量召回与外键扩展。

**总体架构**
用户自然语言提问 → 检索增强层（向量召回 + 两层 Rerank + 图谱扩展） → 精简 Schema → Text-to-SQL

**关键组件**
- `EmbeddingService` 升级为 `text-embedding-v4`。
- `RerankService` 新增，调用 DashScope `qwen3-rerank`。
- `RetrievalPipeline` 新增或增强 `RetrievalAgent`，实现两层 Rerank 与预算控制。
- `SchemaIndexer` 使用“语义补全文本”做向量化输入。

**模型与向量策略**
- 向量模型: `text-embedding-v4`。
- 向量维度: 1024（性能与成本平衡）。
- 入库向量: `text_type=document`。
- 查询向量: `text_type=query`。
- 可选指令: 为 query 侧增加 `instruct`，提升“查库场景”召回效果。
- Phase 1 仅使用 dense 向量，保持与 ChromaDB 兼容。

**语义补全与标准化模板（覆盖率优先）**
模板固定为：
【业务核心语义】
- 所属业务域：...
- 表/字段业务含义：...
- 业务用途：...

【SQL技术细节】
- 基础属性：库名.表名.字段名、类型、长度/精度、是否为空、默认值
- 关联属性：主键/外键、关联表/字段、索引类型
- 约束属性：枚举范围、取值规则

补全产物字段：
- `semantic_description`
- `semantic_tags`
- `source`（comment | rule | llm）
- `confidence`

语义补全输出将作为向量化与 Rerank 的统一输入。

**两层 Rerank 设计**
第一层（表级）：
- 向量召回 Top50 表。
- 候选文本 = 表语义 + 3~5 个字段摘要。
- 输出 Top8~10 表。

第二层（字段级）：
- 候选规模 = Top8~10 表 × 每表 Top10 字段。
- 候选文本 = 表语义摘要（2~3行）+ 字段语义。
- 输出 Top30 字段。

**预算控制与降级**
- 总预算 500ms。
- 表级完成后计算剩余预算。
- 预算不足或超时直接跳过字段 Rerank。
- 降级输出 = 表级 TopK + 字段向量 TopN。

**图谱增强**
- 表级结果通过外键扩展补齐关联表。
- 图谱数据源仍为 JSON `table_graph.json`。

**数据同步**
- 通过 `information_schema` 生成结构指纹。
- 新增表/字段 → 语义补全 + 向量入库 + 图谱更新。
- 删除表/字段 → 向量删除 + 图谱删除。
- 字段变更 → 该表重算向量与图谱。
- 生成增量变更报告用于审计。

**缓存策略**
- 表级缓存：`query_norm -> top_tables`。
- 字段级缓存：`query_norm + table -> top_fields`。
- 命中缓存直接绕过 Rerank，降低延迟。

**性能目标**
- 两层 Rerank 总耗时 < 500ms。
- 全链路查询 1~2 秒内完成。
- 降级比例可观测并可配置阈值。

**测试与评测**
- 单元测试：RerankService、候选组装、预算降级。
- 集成测试：向量召回 + 两层 Rerank + 图谱扩展 + SQL 生成。
- 指标：Top1/Top5/Top10 命中率、SQL 执行成功率、修正率、耗时分布。

**风险与缓解**
- 远程 Rerank 延迟波动：预算控制与降级策略。
- 元数据补全误导：source + confidence 标记，保留原注释可回溯。
- 全量向量重建成本：分批构建，先离线完成后切换。

**结论**
采用方案 B：`text-embedding-v4` + 两层 Rerank + 全覆盖语义补全，兼顾召回精度、可控成本与上线节奏。
