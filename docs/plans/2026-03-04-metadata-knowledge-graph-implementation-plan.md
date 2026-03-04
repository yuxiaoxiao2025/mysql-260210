# 元数据知识图谱实施计划

**创建日期:** 2026-03-04
**基于设计文档:** `docs/plans/2026-03-04-metadata-knowledge-graph-design.md`
**预计总工时:** 8-12 小时

---

## 执行摘要

本计划将设计文档中的架构转化为可执行的实施步骤，分 3 个 Phase 递进完成：

| Phase | 核心交付物 | 依赖 | 预计工时 |
|-------|-----------|------|---------|
| Phase 1 | SchemaIndexer + EmbeddingService + GraphStore | 现有 `db_manager.py`, `llm_client.py` | 4-6h |
| Phase 2 | RetrievalAgent（Python 类方法接口） | Phase 1 完成 | 2-3h |
| Phase 3 | 集成测试 + 文档 | Phase 2 完成 | 2-3h |

---

## Phase 1: 核心基础设施

### 1.1 环境准备 (30 min)

**目标:** 安装依赖、创建目录结构、验证 API 连接

**实施步骤:**

```bash
# Step 1: 安装依赖
pip install chromadb pydantic tenacity

# Step 2: 创建目录结构
mkdir -p data/dev/chroma_db data/dev/backups
mkdir -p data/prod/chroma_db data/prod/backups
touch data/dev/.gitkeep data/prod/.gitkeep

# Step 3: 验证 DashScope API
python -c "import dashscope; print('OK')"
```

**验收标准:**
- [ ] `pip list | grep chromadb` 显示已安装
- [ ] `data/dev/.gitkeep` 和 `data/prod/.gitkeep` 存在
- [ ] DashScope API 可连接

**风险:** DashScope API Key 未配置 → 检查 `.env` 文件

---

### 1.2 实现数据模型 (45 min)

**目标:** 创建 Pydantic 模型定义文件

**文件:** `src/metadata/models.py`

**实施步骤:**

1. 创建 `src/metadata/` 目录
2. 创建 `__init__.py`
3. 实现 `models.py` 包含:
   - `ColumnMetadata`
   - `ForeignKeyRelation`
   - `TableMetadata`
   - `KnowledgeGraph`
   - `IndexProgress`
   - `IndexResult`

**代码骨架:**

```python
# src/metadata/models.py
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime

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
    business_domain: str = "其他"
    schema_text: str = ""
    tags: List[str] = Field(default_factory=list)

class KnowledgeGraph(BaseModel):
    """知识图谱（完整结构）"""
    version: str = "1.0"
    created_at: str
    updated_at: str
    tables: List[TableMetadata]

    def get_table(self, name: str) -> Optional[TableMetadata]:
        ...

    def get_foreign_keys_from(self, table_name: str) -> List[ForeignKeyRelation]:
        ...

class IndexProgress(BaseModel):
    """索引进度"""
    status: str = "pending"
    total_tables: int = 0
    indexed_tables: int = 0
    current_batch: int = 0
    last_updated: str = ""
    errors: List[str] = []
    statistics: Dict = Field(default_factory=dict)

class IndexResult(BaseModel):
    """索引结果"""
    success: bool
    total_tables: int
    indexed_tables: int
    failed_tables: List[str] = []
    elapsed_seconds: float
```

**验收标准:**
- [ ] `pytest tests/test_models.py` 通过（需创建单元测试）
- [ ] Pydantic 验证功能正常

---

### 1.3 实现 EmbeddingService (1h)

**目标:** 封装阿里云 DashScope Embedding API

**文件:** `src/metadata/embedding_service.py`

**关键实现点:**
1. 单文本嵌入 `embed_text(text: str) -> List[float]`
2. 批量嵌入 `embed_batch(texts: List[str], batch_size: int = 10) -> List[List[float]]`
3. 重试逻辑（使用 `tenacity` 库）
4. 错误处理 `EmbeddingAPIError`

**接口契约:**

```python
class EmbeddingService:
    def __init__(self, model: str = "text-embedding-v4", dimension: int = 1024):
        self.model = model
        self.dimension = dimension
        self.api_key = os.getenv("DASHSCOPE_API_KEY")

    def embed_text(self, text: str) -> List[float]:
        """单文本嵌入，返回 1024 维向量"""

    def embed_batch(self, texts: List[str], batch_size: int = 10) -> List[List[float]]:
        """批量嵌入，每批最多 10 个文本"""
```

**测试用例:**

```python
# tests/test_embedding_service.py
def test_embed_single_text():
    service = EmbeddingService()
    embedding = service.embed_text("测试文本")
    assert len(embedding) == 1024

def test_embed_batch():
    service = EmbeddingService()
    texts = ["文本1", "文本2", "文本3"]
    embeddings = service.embed_batch(texts)
    assert len(embeddings) == 3
    assert all(len(e) == 1024 for e in embeddings)
```

**验收标准:**
- [ ] 单元测试通过
- [ ] API 调用成功率 100%
- [ ] 重试逻辑正常工作

---

### 1.4 实现 GraphStore (1h)

**目标:** ChromaDB 向量存储 + JSON 持久化

**文件:** `src/metadata/graph_store.py`

**关键实现点:**
1. 初始化 ChromaDB 集合（`table_metadata`, `field_metadata`）
2. `add_table(table: TableMetadata, embedding: List[float])`
3. `add_field(table_name: str, column: ColumnMetadata, embedding: List[float])`
4. `save_graph(graph: KnowledgeGraph)` - 保存 JSON
5. `load_graph()` - 加载 JSON
6. 使用 `get_or_create_collection` 避免重复创建

**接口契约:**

```python
class GraphStore:
    def __init__(self, env: str = "dev"):
        self.env = env
        self.chroma_path = Path(f"data/{env}/chroma_db")
        self.client = chromadb.PersistentClient(path=str(self.chroma_path))

        # 创建集合（余弦距离）
        self.table_collection = self.client.get_or_create_collection(
            name="table_metadata",
            metadata={"hnsw:space": "cosine"}
        )
        self.field_collection = self.client.get_or_create_collection(
            name="field_metadata",
            metadata={"hnsw:space": "cosine"}
        )

    def add_table(self, table: TableMetadata, embedding: List[float]) -> None:
        """添加表向量"""

    def add_field(self, table_name: str, column: ColumnMetadata,
                  embedding: List[float]) -> None:
        """添加字段向量"""

    def save_graph(self, graph: KnowledgeGraph) -> None:
        """保存知识图谱到 JSON"""

    def load_graph(self) -> Optional[KnowledgeGraph]:
        """加载知识图谱"""

    def clear_all(self) -> None:
        """清空所有向量（用于重建索引）"""
```

**验收标准:**
- [ ] ChromaDB 持久化正常
- [ ] JSON 文件读写正常
- [ ] 向量查询返回正确结果

---

### 1.5 实现 DomainClassifier (30 min)

**目标:** 业务域分类器（规则匹配）

**文件:** `src/metadata/domain_classifier.py`

**关键实现点:**
1. 关键词匹配规则
2. 优先级处理
3. 多标签支持

**代码实现:**

```python
class DomainClassifier:
    BUSINESS_KEYWORDS = {
        "订单": ["order", "trade", "sale", "订单"],
        "用户": ["user", "customer", "member", "用户"],
        "库存": ["stock", "inventory", "warehouse", "库存"],
        "财务": ["finance", "account", "payment", "财务"]
    }

    DOMAIN_PRIORITY = ["订单", "用户", "库存", "财务"]

    def classify(self, table_name: str, comment: str) -> str:
        """推断业务域（单标签）"""

    def classify_multi(self, table_name: str, comment: str) -> List[str]:
        """推断业务域（多标签）"""
```

---

### 1.6 实现 SchemaIndexer (1.5h)

**目标:** 主索引器，协调所有组件完成全量索引

**文件:** `src/metadata/schema_indexer.py`

**关键实现点:**
1. 从 MySQL `information_schema` 提取表结构
2. 提取外键关系
3. 生成向量化文本（表级 + 字段级）
4. 断点续传支持
5. 批量处理（每批 10 个表）

**接口契约:**

```python
class SchemaIndexer:
    def __init__(self, db_manager: DatabaseManager,
                 embedding_service: EmbeddingService,
                 graph_store: GraphStore):
        self.db_manager = db_manager
        self.embedding_service = embedding_service
        self.graph_store = graph_store

    def index_all_tables(self, batch_size: int = 10) -> IndexResult:
        """全量索引所有表"""

    def _extract_table_metadata(self, table_name: str) -> TableMetadata:
        """提取单表元数据"""

    def _generate_schema_text(self, table: TableMetadata) -> str:
        """生成向量化文本"""

    def _index_batch(self, tables: List[str]) -> Dict:
        """索引一批表"""

    def _save_progress(self, progress: IndexProgress) -> None:
        """保存索引进度"""

    def _load_progress(self) -> IndexProgress:
        """加载索引进度"""
```

**向量化文本格式:**

```
# 表级
"表名：{table_name}。描述：{comment}。关键字段：{key_columns}。业务域：{business_domain}"

# 字段级
"{table_name}.{column_name}: {comment}"
```

**验收标准:**
- [ ] 能够索引 900+ 表
- [ ] 断点续传正常工作
- [ ] 生成 `table_graph.json` 和 ChromaDB 向量

---

### 1.7 Phase 1 验收 (30 min)

**验收清单:**
- [ ] 运行 `python -m src.metadata.schema_indexer` 完成全量索引
- [ ] 检查 `data/dev/table_graph.json` 生成
- [ ] 检查 ChromaDB 向量数量

**验收脚本:**

```python
# scripts/verify_phase1.py
from src.metadata.graph_store import GraphStore
from src.metadata.models import KnowledgeGraph
import json

# 检查 JSON
with open("data/dev/table_graph.json") as f:
    graph = KnowledgeGraph(**json.load(f))
    print(f"✅ 表数量: {len(graph.tables)}")

# 检查 ChromaDB
store = GraphStore(env="dev")
print(f"✅ 表向量: {store.table_collection.count()}")
print(f"✅ 字段向量: {store.field_collection.count()}")
```

---

## Phase 2: 检索 Agent

### 2.1 实现检索模型 (30 min)

**目标:** 定义检索请求/响应模型

**文件:** `src/metadata/retrieval_models.py`

**关键模型:**
- `RetrievalLevel` (Enum)
- `RetrievalRequest`
- `TableMatch`
- `FieldMatch`
- `TableRetrievalResult`
- `FieldRetrievalResult`

**代码实现:**

```python
from enum import Enum
from typing import Union

class RetrievalLevel(str, Enum):
    TABLE = "table"
    FIELD = "field"

class RetrievalRequest(BaseModel):
    query: str
    level: RetrievalLevel = RetrievalLevel.TABLE
    top_k: int = Field(default=5, ge=1, le=20)
    filter_tables: Optional[List[str]] = None

class TableMatch(BaseModel):
    table_name: str
    similarity_score: float  # 归一化相似度：1/(1+distance)
    description: str
    business_tags: List[str]

class FieldMatch(BaseModel):
    table_name: str
    field_name: str
    data_type: str
    description: str
    similarity_score: float

class TableRetrievalResult(BaseModel):
    query: str
    matches: List[TableMatch]
    execution_time_ms: int
    metadata: Dict = Field(default_factory=dict)

class FieldRetrievalResult(BaseModel):
    query: str
    matches: List[FieldMatch]
    execution_time_ms: int
    metadata: Dict = Field(default_factory=dict)

RetrievalResult = Union[TableRetrievalResult, FieldRetrievalResult]
```

---

### 2.2 实现 RetrievalAgent (1.5h)

**目标:** 检索 Agent 核心实现

**文件:** `src/metadata/retrieval_agent.py`

**关键实现点:**
1. 统一检索入口 `search(request: RetrievalRequest) -> RetrievalResult`
2. 表级检索 `_search_tables()`
3. 字段级检索 `_search_fields()`（支持表过滤）
4. 外键关系扩展 `_expand_by_foreign_keys()`

**接口契约:**

```python
class RetrievalAgent:
    def __init__(self, env: str = "dev"):
        self.env = env
        self.store = GraphStore(env=env)
        self.graph = self.store.load_graph()

    def search(self, request: RetrievalRequest) -> RetrievalResult:
        """统一检索入口"""

    def _search_tables(self, request: RetrievalRequest) -> List[TableMatch]:
        """表级检索"""

    def _search_fields(self, request: RetrievalRequest) -> List[FieldMatch]:
        """字段级检索"""

    def _expand_by_foreign_keys(self, table_names: List[str]) -> List[str]:
        """基于外键关系扩展相关表"""
```

**相似度转换:**

```python
# ChromaDB 返回 distance (余弦距离，范围 0-2)
# 转换为归一化相似度：1/(1+distance)，范围 0.33-1.0
similarity_score = 1.0 / (1.0 + distance)
```

---

### 2.3 Phase 2 验收 (30 min)

**验收清单:**
- [ ] 表级检索返回 Top-K 结果
- [ ] 字段级检索支持表过滤
- [ ] 外键扩展正常工作

**验收脚本:**

```python
# scripts/verify_phase2.py
from src.metadata.retrieval_agent import RetrievalAgent
from src.metadata.retrieval_models import RetrievalRequest, RetrievalLevel

agent = RetrievalAgent(env="dev")

# 测试表级检索
result = agent.search(RetrievalRequest(
    query="订单表",
    level=RetrievalLevel.TABLE,
    top_k=3
))
print(f"✅ 表级检索: {len(result.matches)} 个匹配")
print(f"   扩展表: {result.metadata.get('expanded_tables', [])}")

# 测试字段级检索
result = agent.search(RetrievalRequest(
    query="状态字段",
    level=RetrievalLevel.FIELD,
    filter_tables=["ec_orders"],
    top_k=5
))
print(f"✅ 字段级检索: {len(result.matches)} 个匹配")
```

---

## Phase 3: 集成与测试

### 3.1 单元测试 (1h)

**目标:** 完善测试覆盖率达到 80%+

**文件:** `tests/metadata/`

**测试文件:**
- `test_models.py` - Pydantic 模型测试
- `test_embedding_service.py` - Embedding API 测试
- `test_graph_store.py` - ChromaDB 操作测试
- `test_domain_classifier.py` - 分类器测试
- `test_schema_indexer.py` - 索引器测试
- `test_retrieval_agent.py` - 检索 Agent 测试

**运行测试:**

```bash
pytest tests/metadata/ -v --cov=src/metadata --cov-report=html
```

---

### 3.2 集成测试 (1h)

**目标:** 端到端测试，验证与现有系统集成

**文件:** `tests/integration/test_metadata_integration.py`

**测试场景:**

1. **索引流程:** MySQL → SchemaIndexer → ChromaDB + JSON
2. **检索流程:** NL Query → RetrievalAgent → TableMatch
3. **DDL 生成:** TableMatch → DDL Context → LLM

**测试代码:**

```python
def test_end_to_end_retrieval():
    # Phase 1: 索引（如果未完成）
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

### 3.3 与现有系统集成 (1h)

**目标:** 集成到 `LLMClient.generate_sql()` 流程

**修改文件:** `src/llm_client.py`

**集成点:**

```python
# 在 generate_sql() 方法中
from src.metadata.retrieval_agent import RetrievalAgent
from src.metadata.retrieval_models import RetrievalRequest, RetrievalLevel

def generate_sql(self, user_query, schema_context, error_context=None):
    # 新增：使用检索 Agent 获取相关表
    if self.retrieval_agent:
        retrieval_result = self.retrieval_agent.search(RetrievalRequest(
            query=user_query,
            level=RetrievalLevel.TABLE,
            top_k=5
        ))
        # 构建增强的 schema_context
        schema_context = self._build_enhanced_context(retrieval_result)

    # 原有逻辑...
```

---

### 3.4 文档更新 (30 min)

**目标:** 更新项目文档

**更新文件:**
- `README.md` - 添加元数据知识图谱章节
- `docs/API_REFERENCE.md` - 添加 RetrievalAgent API 文档
- `docs/USER_GUIDE.md` - 添加使用示例

---

## 执行检查清单

### Phase 1 检查清单

- [ ] 依赖安装完成 (`chromadb`, `pydantic`, `tenacity`)
- [ ] 目录结构创建完成 (`data/dev/`, `data/prod/`)
- [ ] `src/metadata/models.py` 实现并通过测试
- [ ] `src/metadata/embedding_service.py` 实现并通过测试
- [ ] `src/metadata/graph_store.py` 实现并通过测试
- [ ] `src/metadata/domain_classifier.py` 实现并通过测试
- [ ] `src/metadata/schema_indexer.py` 实现并通过测试
- [ ] 全量索引完成，生成 `table_graph.json`
- [ ] ChromaDB 向量数量正确（表级 ~900，字段级 ~13500）

### Phase 2 检查清单

- [ ] `src/metadata/retrieval_models.py` 实现并通过测试
- [ ] `src/metadata/retrieval_agent.py` 实现并通过测试
- [ ] 表级检索功能正常
- [ ] 字段级检索功能正常（支持表过滤）
- [ ] 外键扩展功能正常

### Phase 3 检查清单

- [ ] 单元测试覆盖率 ≥ 80%
- [ ] 集成测试通过
- [ ] 与 `LLMClient` 集成完成
- [ ] 文档更新完成

---

## 风险与缓解

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| DashScope API 限流 | 索引中断 | 中 | 实现重试逻辑，控制 batch_size=10 |
| 表结构变更 | 向量过期 | 低 | 设计增量索引接口（Phase 4） |
| ChromaDB 版本兼容 | 功能异常 | 低 | 锁定 `chromadb>=0.4.0,<0.5.0` |
| 900 表索引时间过长 | 用户体验差 | 中 | 实现断点续传，显示进度 |

---

## 下一步行动

1. **立即执行:** Phase 1.1 环境准备
2. **代码实现:** 按顺序实现 Phase 1.2 - 1.6
3. **验证:** 运行 Phase 1 验收脚本
4. **继续 Phase 2:** 实现 RetrievalAgent
5. **集成测试:** Phase 3 集成

---

**计划状态:** 待批准
**预计开始日期:** 2026-03-04
**预计完成日期:** 2026-03-05