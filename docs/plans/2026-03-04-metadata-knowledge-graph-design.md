# 元数据知识图谱设计文档

**创建日期:** 2026-03-04
**版本:** v1.0
**状态:** 已批准

---

## 目录

1. [概述](#1-概述)
2. [架构设计](#2-架构设计)
3. [数据模型](#3-数据模型)
   - [3.1 知识图谱结构](#31-知识图谱结构)
   - [3.2 向量索引结构](#32-向量索引结构)
   - [3.3 ChromaDB Collection 设计](#33-chromadb-collection-设计)
   - [3.4 持久化存储格式](#34-持久化存储格式)
   - [3.5 接口契约](#35-接口契约)
4. [核心组件](#4-核心组件)
5. [存储与持久化](#5-存储与持久化)
6. [检索 Agent 设计](#6-检索-agent-设计)
7. [错误处理](#7-错误处理)
8. [测试策略](#8-测试策略)
9. [部署与运维](#9-部署与运维)
10. [LLM Prompt 模板](#10-llm-prompt 模板)

---

## 1. 概述

### 1.1 需求背景

- **问题:** 数据库有约 900 张表，开发人员难以快速定位需要的表
- **痛点:** 表与表之间的关联关系不清晰，每次查询都需要手动查找
- **目标:** 构建知识图谱和检索 Agent，支持语义检索和 Schema Linking

### 1.2 项目目标

| 目标 | 描述 | 验收标准 |
|------|------|----------|
| 元数据资产化 | 自动扫描 900+ 表，构建知识图谱 | 生成 `table_graph.json`，包含所有表、字段、外键关系 |
| 层级嵌入 | 表级 + 字段级双层向量索引 | 支持表级检索（Top-K）和字段级检索（带表过滤） |
| 检索 Agent | Python 类方法接口 | `RetrievalAgent.search()` 可被 Phase 3 直接调用 |

### 1.3 范围界定

**本次实现（Phase 1-3）:**
- Phase 1: Schema 索引器、向量化服务、知识图谱存储
- Phase 2: 检索 Agent（Python 类方法）
- Phase 3: 集成测试（与现有 `db_manager.py`、`llm_client.py` 集成）

**未来扩展:**
- FastAPI REST 接口（给同事提供 Web 界面时）
- 自动增量索引（检测表结构变更）
- 图数据库迁移（Neo4j，支持复杂查询）

---

## 2. 架构设计

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                     用户/NL 查询                              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   RetrievalAgent (Phase 2)                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ search()    │→ │ _search_    │→ │ _search_            │  │
│  │ 统一入口     │  │ tables()    │  │ fields()            │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
            ↓                          ↓
    ┌───────────────┐          ┌───────────────┐
    │ ChromaDB      │          │ ChromaDB      │
    │ table_metadata│          │ field_metadata│
    │ (900 向量)    │          │ (13,500 向量)  │
    └───────────────┘          └───────────────┘
            ↓                          ↓
┌─────────────────────────────────────────────────────────────┐
│              SchemaIndexer (Phase 1)                        │
│  MySQL information_schema → 向量化 → ChromaDB + JSON         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              SQLAgent + LLM (Phase 3)                       │
│  检索结果 → DDL 上下文 → Text-to-SQL                         │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 组件关系

| 组件 | Phase | 依赖 | 被依赖 |
|------|-------|------|--------|
| `SchemaIndexer` | Phase 1 | `DatabaseManager`, `EmbeddingService` | `GraphStore`, `RetrievalAgent` |
| `EmbeddingService` | Phase 1 | DashScope API | `SchemaIndexer` |
| `GraphStore` | Phase 1 | ChromaDB | `SchemaIndexer`, `RetrievalAgent` |
| `RetrievalAgent` | Phase 2 | `GraphStore`, Pydantic | `SQLAgent` (Phase 3) |
| `SQLAgent` | Phase 3 | `RetrievalAgent`, `LLMClient` | - |

---

## 3. 数据模型

### 3.1 知识图谱结构

```python
# Pydantic 模型定义
from pydantic import BaseModel, Field
from typing import List, Dict, Optional

class ColumnMetadata(BaseModel):
    """字段元数据"""
    name: str
    data_type: str
    comment: str = ""
    is_primary_key: bool = False
    is_foreign_key: bool = False
    references_table: Optional[str] = None
    references_column: Optional[str] = None

class ForeignKeyRelation(BaseModel):
    """外键关系"""
    column_name: str
    referenced_table: str
    referenced_column: str

class TableMetadata(BaseModel):
    """表元数据（核心模型）"""
    table_name: str
    database_name: str = ""
    comment: str = ""
    columns: List[ColumnMetadata] = Field(default_factory=list)
    foreign_keys: List[ForeignKeyRelation] = Field(default_factory=list)
    business_domain: str = "其他"  # 订单、用户、库存、财务
    schema_text: str = ""  # 向量化文本
    tags: List[str] = Field(default_factory=list)

class KnowledgeGraph(BaseModel):
    """知识图谱（完整结构）"""
    version: str = "1.0"
    created_at: str
    updated_at: str
    tables: List[TableMetadata]

    def get_table(self, name: str) -> Optional[TableMetadata]:
        for t in self.tables:
            if t.table_name == name:
                return t
        return None

    def get_foreign_keys_from(self, table_name: str) -> List[ForeignKeyRelation]:
        table = self.get_table(table_name)
        return table.foreign_keys if table else []
```

### 3.2 向量索引结构

```python
# 通用字段过滤常量（在 SchemaIndexer 中使用）
GENERIC_FIELDS = {'id', 'created_at', 'updated_at', 'is_deleted', 'deleted_at'}

层级嵌入设计：

Layer 1: 表级嵌入（900 个向量）
┌────────────────────────────────────────────────────────┐
│ 向量化文本格式：                                         │
│ "表名：{table_name}。描述：{comment}。                   │
│  关键字段：{key_columns}。业务域：{business_domain}"    │
│                                                         │
│ 关键字段提取规则：                                       │
│ - 过滤通用字段：id, created_at, updated_at, is_deleted  │
│ - 只保留前 10 个业务字段                                  │
│                                                         │
│ 示例：                                                   │
│ "表名：ec_orders。描述：订单主表。                        │
│  关键字段：user_id, total_amount, status...             │
│  业务域：订单"                                          │
└────────────────────────────────────────────────────────┘

Layer 2: 字段级嵌入（13,500 个向量）
┌────────────────────────────────────────────────────────┐
│ 向量化文本格式：                                         │
│ "{table_name}.{column_name}: {comment}"                │
│                                                         │
│ 示例：                                                   │
│ "ec_orders.user_id: 用户 ID（关联用户表）"               │
│ "ec_orders.status: 订单状态（0-待支付，1-已支付...）"   │
└────────────────────────────────────────────────────────┘
```

### 3.3 ChromaDB Collection 设计

```python
# Collection 命名
COLLECTION_TABLE = "table_metadata"
COLLECTION_FIELD = "field_metadata"

# 表级 Collection 结构
table_collection:
{
    "ids": ["ec_orders", "ec_users", ...],
    "embeddings": [[0.1, 0.2, ...], ...],  # 1024 维
    "metadatas": [
        {
            "table_name": "ec_orders",
            "database_name": "cloudinterface",
            "comment": "订单主表",
            "business_domain": "订单",
            "column_count": 15,
            "tags": "订单，核心，高频"
        },
        ...
    ],
    "documents": ["表名：ec_orders。描述：订单主表。...", ...]
}

# 字段级 Collection 结构
field_collection:
{
    "ids": ["ec_orders.id", "ec_orders.user_id", ...],
    "embeddings": [[0.1, 0.2, ...], ...],  # 1024 维
    "metadatas": [
        {
            "table_name": "ec_orders",
            "column_name": "user_id",
            "level": "field",          # <-- 添加 level 字段用于过滤
            "data_type": "int",
            "comment": "用户 ID",
            "business_domain": "订单"
        },
        ...
    ],
    "documents": ["ec_orders.user_id: 用户 ID", ...]
}

# ChromaDB 集合创建（使用 get_or_create_collection）
def __init__(self, env: str = "dev"):
    self.client = chromadb.PersistentClient(path=f"data/{env}/chroma_db")

    # 创建或获取集合，明确指定余弦距离度量
    self.table_collection = self.client.get_or_create_collection(
        name="table_metadata",
        metadata={"hnsw:space": "cosine"}  # 余弦距离（0-2）
    )
    self.field_collection = self.client.get_or_create_collection(
        name="field_metadata",
        metadata={"hnsw:space": "cosine"}
    )
```

### 3.4 持久化存储格式

#### table_graph.json 结构
```json
{
  "version": "1.0",
  "created_at": "2026-03-04T10:00:00Z",
  "updated_at": "2026-03-04T12:00:00Z",
  "tables": [
    {
      "table_name": "ec_orders",
      "database_name": "cloudinterface",
      "comment": "订单主表",
      "columns": [
        {
          "name": "id",
          "data_type": "bigint",
          "comment": "主键 ID",
          "is_primary_key": true
        }
      ],
      "foreign_keys": [
        {
          "column_name": "user_id",
          "referenced_table": "uc_users",
          "referenced_column": "id"
        }
      ],
      "business_domain": "订单",
      "schema_text": "表名：ec_orders。描述：订单主表...",
      "tags": ["订单", "核心"]
    }
  ]
}
```

#### index_progress.json 结构
```json
{
  "status": "in_progress",
  "total_tables": 900,
  "indexed_tables": 450,
  "current_batch": 45,
  "last_updated": "2026-03-04T11:30:00Z",
  "errors": [],
  "statistics": {
    "table_vectors": 450,
    "field_vectors": 6750,
    "api_calls": 45
  }
}
```

### 3.5 接口契约

#### Phase 1 → Phase 2
- **数据:** `List[TableMetadata]`（Pydantic 模型）
- **存储:** `data/{env}/table_graph.json`（JSON 文件）
- **契约验证:** SchemaIndexer 必须生成符合 TableMetadata 结构的数据

#### Phase 2 → Phase 3
- **接口:** `RetrievalAgent.search(request: RetrievalRequest) → RetrievalResult`
- **Mock 支持:** Phase 3 开发时可注入 `MockRetriever`（固定返回 Top-3 表）

```python
# MockRetriever 示例（供 Phase 3 开发使用）
class MockRetriever:
    def search(self, request: RetrievalRequest) -> RetrievalResult:
        return RetrievalResult(
            query=request.query,
            level=request.level,
            matches=[
                TableMatch(table_name="ec_orders", similarity_score=0.95, ...),
                TableMatch(table_name="ec_users", similarity_score=0.88, ...),
            ],
            execution_time_ms=10,
            metadata={"mock": True}
        )
```

---

## 4. 核心组件

### 4.1 SchemaIndexer（Phase 1）
```python
class SchemaIndexer:
    """Schema 索引器 - 扫描 MySQL 元数据，构建知识图谱"""

    def __init__(self, db_manager, embedding_service, graph_store):
        ...

    def index_all_tables(self) -> IndexResult:
        """全量索引 900+ 表"""
        ...

    def _extract_table_metadata(self, table_name: str) -> TableMetadata:
        """提取单表元数据"""
        ...

    def _generate_schema_text(self, table: TableMetadata) -> str:
        """生成向量化文本"""
        ...
```

### 4.2 EmbeddingService（Phase 1）
```python
class EmbeddingService:
    """向量化服务 - 阿里云 DashScope API 封装"""

    def __init__(self, model: str = "text-embedding-v4", dimension: int = 1024):
        ...

    def embed_text(self, text: str) -> List[float]:
        """单文本嵌入"""
        ...

    def embed_batch(self, texts: List[str], batch_size: int = 10) -> List[List[float]]:
        """批量嵌入（每批最多 10 个）"""
        ...
```

### 4.3 GraphStore（Phase 1）
```python
class GraphStore:
    """图谱存储 - ChromaDB + JSON 持久化"""

    def __init__(self, env: str = "dev"):
        ...

    def add_table(self, table: TableMetadata, embedding: List[float]):
        """添加表到向量索引"""
        ...

    def add_field(self, table_name: str, column: ColumnMetadata, embedding: List[float]):
        """添加字段到向量索引"""
        ...

    def save_graph(self, graph: KnowledgeGraph):
        """保存知识图谱到 JSON"""
        ...
```

### 4.4 DomainClassifier（Phase 1）
```python
class DomainClassifier:
    """业务域分类器 - 规则匹配（优先级处理）"""

    BUSINESS_KEYWORDS = {
        "订单": ["order", "trade", "sale", "订单"],
        "用户": ["user", "customer", "member", "用户"],
        "库存": ["stock", "inventory", "warehouse", "库存"],
        "财务": ["finance", "account", "payment", "财务"]
    }

    # 优先级顺序：先匹配的优先
    DOMAIN_PRIORITY = ["订单", "用户", "库存", "财务"]

    def classify(self, table_name: str, comment: str) -> str:
        """推断业务域（优先级处理）"""
        text = (table_name + " " + comment).lower()
        matched_domains = []

        for domain, keywords in self.BUSINESS_KEYWORDS.items():
            if any(k.lower() in text for k in keywords):
                matched_domains.append(domain)

        if not matched_domains:
            return "其他"

        # 按优先级返回第一个匹配的业务域
        for domain in self.DOMAIN_PRIORITY:
            if domain in matched_domains:
                return domain

        return matched_domains[0]

    def classify_multi(self, table_name: str, comment: str) -> List[str]:
        """推断业务域（返回所有匹配，支持多标签）"""
        text = (table_name + " " + comment).lower()
        matched = []

        for domain, keywords in self.BUSINESS_KEYWORDS.items():
            if any(k.lower() in text for k in keywords):
                matched.append(domain)

        return matched if matched else ["其他"]
```

---

## 5. 存储与持久化

### 5.1 目录结构
```
项目根目录/
├── data/
│   ├── dev/
│   │   ├── chroma_db/              # ChromaDB 向量库（Git 忽略）
│   │   ├── table_graph.json        # 知识图谱
│   │   ├── index_progress.json     # 索引进度
│   │   └── backups/                # 备份目录
│   ├── prod/
│   │   ├── chroma_db/
│   │   ├── table_graph.json
│   │   ├── index_progress.json
│   │   └── backups/
│   └── dev/.gitkeep                # 保留目录结构
│   └── prod/.gitkeep
```

### 5.2 .gitignore 配置
```gitignore
# 数据目录（可重建，不提交）
data/*/chroma_db/
data/*/backups/
data/*/index_progress.json
*.log

# 环境配置（本地使用）
.env

# 但保留目录结构
!data/dev/.gitkeep
!data/prod/.gitkeep
```

### 5.3 环境配置

**.env.example**（提交到 Git）:
```ini
# 环境标识
ENV=dev

# ChromaDB 路径
CHROMA_DB_PATH=data/dev/chroma_db

# 知识图谱路径
TABLE_GRAPH_PATH=data/dev/table_graph.json

# 索引进度路径
INDEX_PROGRESS_PATH=data/dev/index_progress.json

# DashScope API Key（示例）
DASHSCOPE_API_KEY=your_api_key_here
```

**.env**（本地使用，Git 忽略）:
```ini
ENV=dev
CHROMA_DB_PATH=data/dev/chroma_db
TABLE_GRAPH_PATH=data/dev/table_graph.json
INDEX_PROGRESS_PATH=data/dev/index_progress.json
DASHSCOPE_API_KEY=sk-xxx
```

### 5.4 备份脚本

#### scripts/backup_metadata.sh
```bash
#!/bin/bash
# 用法：./scripts/backup_metadata.sh [dev|prod]

ENV=${1:-dev}
SOURCE_DIR="data/${ENV}/chroma_db"
BACKUP_DIR="data/${ENV}/backups/chroma_db_$(date +%Y%m%d_%H%M%S)"

if [ ! -d "$SOURCE_DIR" ]; then
    echo "❌ 错误：$SOURCE_DIR 不存在"
    exit 1
fi

mkdir -p "$BACKUP_DIR"
cp -r "$SOURCE_DIR"/* "$BACKUP_DIR"/

# 同时备份知识图谱 JSON
cp "data/${ENV}/table_graph.json" "$BACKUP_DIR"/ 2>/dev/null || echo "⚠️ table_graph.json 不存在"

echo "✅ 备份完成：$BACKUP_DIR"
# 兼容性判断：Windows Git Bash 中 du 可能不可用
if command -v du &> /dev/null; then
    echo "📊 备份大小：$(du -sh $BACKUP_DIR | cut -f1)"
else
    echo "📊 备份完成（Windows 系统不显示大小）"
fi
```

### 5.5 备份频率建议

| 环境 | 频率 | 方式 |
|------|------|------|
| **dev** | 关键节点手动备份 | Phase 1 完成后执行一次 |
| **prod** | 每周或重新索引后 | 手动执行 `./scripts/backup_metadata.sh prod` |

---

## 6. 检索 Agent 设计

### 6.1 Pydantic 模型

```python
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from enum import Enum

class RetrievalLevel(str, Enum):
    TABLE = "table"      # 表级检索
    FIELD = "field"      # 字段级检索

class RetrievalRequest(BaseModel):
    """检索请求（CTF 格式 - Context 明确输入）"""
    query: str = Field(..., description="用户自然语言查询")
    level: RetrievalLevel = Field(default=RetrievalLevel.TABLE)
    top_k: int = Field(default=5, ge=1, le=20)
    filter_tables: Optional[List[str]] = Field(default=None, description="指定检索范围")

class TableMatch(BaseModel):
    """表级匹配结果"""
    table_name: str
    similarity_score: float  # 归一化相似度：1/(1+distance)，范围 0.33-1.0
    description: str
    business_tags: List[str]

class FieldMatch(BaseModel):
    """字段级匹配结果"""
    table_name: str
    field_name: str
    data_type: str
    description: str
    similarity_score: float  # 归一化相似度：1/(1+distance)，范围 0.33-1.0

class BaseRetrievalResult(BaseModel):
    """检索结果基类（DRY 原则）"""
    query: str
    execution_time_ms: int
    metadata: Dict = Field(default_factory=dict)

class TableRetrievalResult(BaseRetrievalResult):
    """表级检索结果"""
    matches: List[TableMatch]

class FieldRetrievalResult(BaseRetrievalResult):
    """字段级检索结果"""
    matches: List[FieldMatch]

# 统一返回类型（用于类型注解）
RetrievalResult = Union[TableRetrievalResult, FieldRetrievalResult]
```

### 6.2 RetrievalAgent 类

```python
class RetrievalAgent:
    """检索 Agent - 负责向量检索和 Schema 匹配"""

    def __init__(self, env: str = "dev"):
        import chromadb
        import json
        from pathlib import Path

        # 初始化 ChromaDB
        chroma_path = Path(f"data/{env}/chroma_db")
        self.client = chromadb.PersistentClient(path=str(chroma_path))
        self.table_collection = self.client.get_or_create_collection(
            name="table_metadata",
            metadata={"hnsw:space": "cosine"}
        )
        self.field_collection = self.client.get_or_create_collection(
            name="field_metadata",
            metadata={"hnsw:space": "cosine"}
        )

        # 加载知识图谱 JSON（用于外键扩展）
        graph_path = Path(f"data/{env}/table_graph.json")
        self.graph = self._load_graph(graph_path)

    def _load_graph(self, path: Path) -> Optional[KnowledgeGraph]:
        """加载知识图谱 JSON"""
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return KnowledgeGraph(**data)

    def search(self, request: RetrievalRequest) -> RetrievalResult:
        """统一检索入口"""
        import time
        start_time = time.time()

        if request.level == RetrievalLevel.TABLE:
            matches = self._search_tables(request)
            # 外键关系扩展（仅表级检索）
            expanded_tables = self._expand_by_foreign_keys([m.table_name for m in matches])

            return TableRetrievalResult(
                query=request.query,
                matches=matches,
                execution_time_ms=int((time.time() - start_time) * 1000),
                metadata={"expanded_tables": expanded_tables}
            )
        else:
            matches = self._search_fields(request)
            return FieldRetrievalResult(
                query=request.query,
                matches=matches,
                execution_time_ms=int((time.time() - start_time) * 1000),
                metadata={"filter_applied": request.filter_tables is not None}
            )

    def _search_tables(self, request: RetrievalRequest) -> List[TableMatch]:
        """表级检索"""
        results = self.table_collection.query(
            query_texts=[request.query],
            n_results=request.top_k
        )

        matches = []
        for i, metadata in enumerate(results['metadatas'][0]):
            distance = results['distances'][0][i]
            # 转换为归一化相似度：1/(1+distance)，范围 0.33-1.0
            similarity_score = 1.0 / (1.0 + distance)

            matches.append(TableMatch(
                table_name=metadata['table_name'],
                similarity_score=similarity_score,
                description=metadata.get('description', ''),
                business_tags=metadata.get('tags', '').split(',') if metadata.get('tags') else []
            ))
        return matches

    def _search_fields(self, request: RetrievalRequest) -> List[FieldMatch]:
        """字段级检索（支持表过滤）"""
        where_clause = {"level": "field"}  # 使用 3.3 节添加的 level 字段
        if request.filter_tables:
            where_clause["table_name"] = {"$in": request.filter_tables}

        results = self.field_collection.query(
            query_texts=[request.query],
            where=where_clause,
            n_results=request.top_k
        )

        matches = []
        for i, metadata in enumerate(results['metadatas'][0]):
            distance = results['distances'][0][i]
            # 转换为归一化相似度
            similarity_score = 1.0 / (1.0 + distance)

            matches.append(FieldMatch(
                table_name=metadata['table_name'],
                field_name=metadata['column_name'],
                data_type=metadata['data_type'],
                description=metadata.get('comment', ''),
                similarity_score=similarity_score
            ))
        return matches

    def _expand_by_foreign_keys(self, table_names: List[str]) -> List[str]:
        """基于外键关系扩展相关表（Graph Expansion）"""
        if self.graph is None:
            return []  # 图谱未加载

        related = set(table_names)
        for table in table_names:
            fks = self.graph.get_foreign_keys_from(table)
            for fk in fks:
                related.add(fk.referenced_table)

        # 返回扩展的表（排除原始表）
        return list(related - set(table_names))
```

### 6.3 使用示例

```python
if __name__ == "__main__":
    agent = RetrievalAgent(env="dev")

    # 示例 1：表级检索
    result = agent.search(RetrievalRequest(
        query="查询用户订单金额",
        level=RetrievalLevel.TABLE,
        top_k=3
    ))
    print(f"找到表：{[m.table_name for m in result.matches]}")
    print(f"扩展表：{result.metadata.get('expanded_tables', [])}")

    # 示例 2：字段级检索（带表过滤）
    result = agent.search(RetrievalRequest(
        query="状态字段含义",
        level=RetrievalLevel.FIELD,
        filter_tables=["ec_orders", "ec_payment"],
        top_k=10
    ))
    print(f"找到字段：{[(m.table_name, m.field_name) for m in result.matches]}")
```

---

## 7. 错误处理

### 7.1 API 失败处理

```python
from tenacity import retry, stop_after_attempt, wait_exponential
import logging

logger = logging.getLogger(__name__)

class EmbeddingAPIError(Exception):
    """DashScope API 调用失败"""
    pass

class EmbeddingService:
    def embed_batch(self, texts: List[str], batch_size: int = 10) -> List[List[float]]:
        from dashscope import TextEmbedding

        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10)
        )
        def _embed_batch_impl(batch: List[str]) -> List[List[float]]:
            try:
                response = TextEmbedding.call(
                    model='text-embedding-v4',
                    input=batch,
                    dimensions=1024
                )
                if response.status_code != 200:
                    raise EmbeddingAPIError(f"API Error: {response.code}")
                return [emb.embedding for emb in response.output.embeddings]
            except Exception as e:
                logger.error(f"嵌入失败：{e}")
                raise

        # 分批处理
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            embeddings = _embed_batch_impl(batch)
            all_embeddings.extend(embeddings)

        return all_embeddings
```

### 7.2 索引中断恢复

```python
class IndexProgress(BaseModel):
    """索引进度"""
    status: str = "pending"  # pending, in_progress, completed, failed
    total_tables: int
    indexed_tables: int
    current_batch: int
    last_updated: str
    errors: List[str] = []

class SchemaIndexer:
    def index_all_tables(self) -> IndexResult:
        # 加载进度
        progress = self._load_progress()

        if progress.status == "completed":
            logger.info("索引已完成，跳过")
            return

        # 断点续传
        start_index = progress.indexed_tables

        for i, table in enumerate(tables[start_index:], start_index):
            try:
                self._index_table(table)
                progress.indexed_tables = i + 1
                self._save_progress(progress)
            except Exception as e:
                progress.errors.append(f"{table}: {e}")
                logger.error(f"索引失败 {table}: {e}")
                # 继续下一张表
```

---

## 8. 测试策略

### 8.1 单元测试

```python
# test_schema_indexer.py
def test_extract_table_metadata():
    indexer = SchemaIndexer(...)
    metadata = indexer._extract_table_metadata("ec_orders")
    assert metadata.table_name == "ec_orders"
    assert len(metadata.columns) > 0

# test_embedding_service.py
def test_embed_single_text():
    service = EmbeddingService()
    embedding = service.embed_text("测试文本")
    assert len(embedding) == 1024

# test_retrieval_agent.py
def test_table_search():
    agent = RetrievalAgent(env="dev")
    result = agent.search(RetrievalRequest(
        query="订单表",
        level=RetrievalLevel.TABLE,
        top_k=3
    ))
    assert len(result.matches) == 3
    assert any("order" in m.table_name.lower() for m in result.matches)
```

### 8.2 集成测试

```python
# test_integration.py
def test_end_to_end_retrieval():
    # Phase 1: 索引
    indexer = SchemaIndexer(...)
    indexer.index_all_tables()

    # Phase 2: 检索
    agent = RetrievalAgent(env="dev")
    result = agent.search(RetrievalRequest(
        query="用户订单",
        level=RetrievalLevel.TABLE,
        top_k=3
    ))

    # Phase 3: 生成 DDL 上下文
    ddl_context = generate_ddl_context(result.matches)
    assert "CREATE TABLE" in ddl_context
```

---

## 9. 部署与运维

### 9.1 环境依赖

```txt
# requirements-metadata.txt
mysql-connector-python>=8.0.0
chromadb>=0.4.0
dashscope>=1.14.0
pydantic>=2.0.0
python-dotenv>=1.0.0
tenacity>=8.0.0  # 重试逻辑（替代已停止维护的 retry 包）
```

### 9.2 监控指标

| 指标 | 阈值 | 告警 |
|------|------|------|
| 索引时间 | >30 分钟 | 邮件通知 |
| API 失败率 | >5% | 邮件通知 |
| 检索延迟 | >500ms | 日志记录 |
| ChromaDB 大小 | >1GB | 日志记录 |

---

## 10. LLM Prompt 模板（开发时使用）

### 10.1 代码生成 Prompt

```markdown
# Context
你是 Python 专家，正在开发 MySQL 元数据索引系统。
当前环境：Windows + Git Bash，使用 ChromaDB 和阿里云 Embedding API。

# Task
实现{具体组件}，要求：
1. 遵循设计文档第 X 章的接口定义
2. 使用 Pydantic 做数据验证
3. 包含错误处理和日志记录
4. 添加类型提示（typing）

# Format
输出完整可运行的 Python 代码，包含：
- 类定义和方法实现
- 使用示例（if __name__ == "__main__"）
- 关键注释说明设计决策
```

### 10.2 各组件开发 Prompt

#### Phase 1: SchemaIndexer
```markdown
# Task
实现 SchemaIndexer 类，要求：
1. 遵循设计文档第 3.1 节的 TableMetadata 模型
2. 从 MySQL information_schema 提取表结构
3. 调用 EmbeddingService 生成向量
4. 保存到 ChromaDB 和 JSON 文件
5. 支持断点续传（index_progress.json）
```

#### Phase 1: EmbeddingService
```markdown
# Task
实现 EmbeddingService 类，要求：
1. 封装 dashscope.TextEmbedding API
2. 支持单文本和批量嵌入（batch_size=10）
3. 使用 text-embedding-v4 模型，1024 维度
4. 包含重试逻辑（3 次，指数退避）
```

#### Phase 2: RetrievalAgent
```markdown
# Task
实现 RetrievalAgent 类，要求：
1. 遵循设计文档第 6 节的接口定义
2. 支持表级和字段级检索
3. 支持 metadata 过滤（filter_tables）
4. 使用 Pydantic 验证输入输出
```

---

## 附录 A：设计决策记录

| 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|
| 向量模型 | 本地 vs 云 API | 云 API（text-embedding-v4） | 中文优化好，与现有 LLM 同一 API |
| 知识图谱 | JSON vs Neo4j | JSON + NetworkX | 平衡实现复杂度和查询能力 |
| 索引策略 | 全量 vs 增量 | 全量 + 断点续传 | 完整，支持中断恢复 |
| 层级嵌入 | 单层 vs 双层 | 双层（表 + 字段） | Schema Linking 最佳实践 |

---

## 附录 B：参考资料

- [阿里云百炼 text-embedding-v4 文档](https://bailian.console.aliyun.com/)
- [ChromaDB 官方文档](https://docs.trychroma.com/)
- [Schema Linking 论文（微软）](https://arxiv.org/abs/2305.15602)
