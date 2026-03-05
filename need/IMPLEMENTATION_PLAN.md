# 元数据资产化与检索 Agent 实施计划

**创建日期:** 2026-03-04
**目标:** 解决 900+ 数据库表的认知问题，构建知识图谱和检索 Agent 团队

---

## 需求背景

### 问题
- 数据库有约 900 张表，难以快速定位需要的表
- 表与表之间的关联关系不清晰
- 每次查询都需要手动查找，效率低下

### 解决方案
1. **元数据资产化** - 使用知识图谱技术自动扫描和索引所有表结构、字段、外键关系
2. **检索 Agent** - 构建具有专业检索能力的 Agent，支持语义检索、关系补全、业务域过滤

---

## 项目结构

```
src/
├── metadata/
│   ├── __init__.py
│   ├── schema_indexer.py      # Schema 索引器
│   ├── graph_store.py         # 图谱存储
│   ├── embedding_service.py   # 向量化服务
│   ├── domain_classifier.py   # 业务域分类
│   └── config.py              # 配置
├── agents/
│   ├── __init__.py
│   ├── retrieval_agent.py     # 检索 Agent
│   └── retrieval_skill.py     # 检索技能
├── api/
│   ├── __init__.py
│   └── retrieval_api.py       # FastAPI 端点
├── schemas/
│   └── retrieval_schemas.py   # Pydantic 模型
└── utils/
    └── db_manager.py          # 数据库连接管理
```

---

## Phase 1: 元数据资产化基础设施

### 1.1 Schema 索引器 (`src/metadata/schema_indexer.py`)

**目标:** 自动扫描 900+ 表，构建知识图谱

**功能:**
- 从 `information_schema` 提取表结构、字段、注释、外键
- 使用 Sentence Transformer 生成表描述的向量嵌入
- 存储到 ChromaDB 向量数据库
- 生成 `table_graph.json` 关系图谱

**核心类:** `SchemaGraphBuilder`
- `extract_all_tables()` - 提取所有表结构和关系
- `_infer_business_domain()` - 推断业务领域
- `_extract_tags()` - 提取业务标签

### 1.2 图谱存储 (`src/metadata/graph_store.py`)

**目标:** 提供统一的图谱数据存储接口

**功能:**
- ChromaDB 向量存储封装
- JSON 文件读写
- 缓存管理

### 1.3 向量化服务 (`src/metadata/embedding_service.py`)

**目标:** 提供文本向量化能力

**功能:**
- Sentence Transformer 模型加载
- 批量嵌入生成
- 缓存管理

### 1.4 业务域分类器 (`src/metadata/domain_classifier.py`)

**目标:** 智能识别表所属业务领域

**功能:**
- 基于规则的业务域匹配（订单、用户、库存、财务等）
- 支持自定义关键词扩展
- 支持人工校正

**预定义业务域:**
| 域 | 关键词 |
|----|--------|
| 订单 | order, trade, sale |
| 用户 | user, customer, member |
| 库存 | stock, inventory, warehouse |
| 财务 | finance, account, payment |

---

## Phase 2: 检索 Agent 核心能力

### 2.1 检索 Agent (`src/agents/retrieval_agent.py`)

**能力清单:**

| 能力 | 描述 |
|------|------|
| 语义检索 | 根据用户自然语言查询，向量检索 Top-K 相关表 |
| 关系补全 | 自动查找表的外键关联，构建查询路径 |
| 业务域过滤 | 按业务领域（订单/用户/库存）筛选表 |
| 元数据解释 | 返回表结构、字段含义、关联关系 |

**核心方法:**
- `search_tables(query: str, top_k: int = 10)` - 语义检索
- `get_table_relations(table_name: str)` - 获取关联表
- `get_tables_by_domain(domain: str)` - 按业务域查询
- `explain_table(table_name: str)` - 解释表结构

### 2.2 检索技能 (`src/agents/retrieval_skill.py`)

**目标:** 定义检索 Agent 的技能接口

**技能:**
- 表发现技能
- 关系发现技能
- 业务域分析技能

### 2.3 检索 API (`src/api/retrieval_api.py`)

**API 端点:**

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/retrieve/tables` | POST | 语义检索表 |
| `/api/retrieve/tables/{table_name}/relations` | GET | 获取关联表 |
| `/api/retrieve/domains/{domain}/tables` | GET | 按业务域查询 |
| `/api/retrieve/graph` | GET | 获取完整关系图谱 |

---

## Phase 3: 集成与测试

### 3.1 依赖配置

**`requirements-metadata.txt`:**
```
mysql-connector-python>=8.0.0
chromadb>=0.4.0
sentence-transformers>=2.2.0
fastapi>=0.104.0
uvicorn>=0.24.0
pydantic>=2.0.0
```

### 3.2 测试计划

**单元测试:**
- 索引器测试
- 检索器测试
- 分类器测试

**集成测试:**
- 端到端检索流程
- API 端点测试

**性能测试:**
- 900+ 表索引时间
- 检索延迟

---

## 依赖关系图

```
Phase 1.1 Schema 索引器 ──┬──> Phase 1.2 分类器 ──> Phase 2.1 检索 Agent
                          │
                          └──> ChromaDB 向量库 ──┘
                                                  ↓
                                          Phase 2.2 检索 API
                                                  ↓
                                          Phase 3 测试
```

---

## 风险评估

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| 900+ 表索引时间过长 | 中 | 分批索引、进度报告、断点续传 |
| 中文表名/注释向量化效果 | 中 | 使用 multilingual 模型 |
| ChromaDB 性能瓶颈 | 低 | 轻量级使用场景足够，可迁移至 Qdrant |
| 业务域分类准确率 | 中 | 规则 + LLM 混合方案，支持人工校正 |

---

## 预计工作量

| 模块 | 工时 |
|------|------|
| Phase 1: 元数据基础设施 | 4-6 小时 |
| Phase 2: 检索 Agent | 6-8 小时 |
| Phase 3: 集成测试 | 3-4 小时 |
| **总计** | **13-18 小时** |

---

## 参考资料

- `元数据资产化.md` - 原始需求文档
- `三层 Agent 协作系统.md` - Agent 架构设计
