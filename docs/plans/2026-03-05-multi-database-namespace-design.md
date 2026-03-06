# 多库命名空间架构升级设计文档

**创建日期:** 2026-03-05
**版本:** v1.0
**状态:** 待审批
**关联文档:** [2026-03-04-metadata-knowledge-graph-design.md](./2026-03-04-metadata-knowledge-graph-design.md)

---

## 目录

1. [概述](#1-概述)
2. [现状分析](#2-现状分析)
3. [架构设计](#3-架构设计)
4. [数据模型升级](#4-数据模型升级)
5. [核心组件升级](#5-核心组件升级)
6. [园区库模板机制](#6-园区库模板机制)
7. [增量索引策略](#7-增量索引策略)
8. [ChromaDB 性能分析](#8-chromadb-性能分析)
9. [测试策略](#9-测试策略)
10. [实施计划](#10-实施计划)
11. [附录](#附录-a设计决策记录)

---

## 1. 概述

### 1.1 需求背景

| 维度 | 期望值 | 当前实际值 | 差距 |
|------|--------|-----------|------|
| **数据库数量** | 76 个业务库 | 1 个库 (`parkcloud`) | ❌ 缺少 75 个库 |
| **表总数** | 9715 张 | 145 张 | ❌ 缺少 9570 张表 |
| **索引范围** | 全库（除系统库外） | 仅连接的库 | ❌ 跨库查询不支持 |
| **命名空间** | `database.table` 格式 | 仅 `table` | ❌ 同名表冲突 |

### 1.2 项目目标

| 目标 | 描述 | 验收标准 |
|------|------|----------|
| 全库索引 | 索引所有业务库（排除系统库和 `parkstandard`） | 生成包含 76 个库的知识图谱 |
| 命名空间管理 | 支持 `database.table` 格式的跨库表引用 | 搜索结果区分不同库的同名表 |
| 园区库优化 | 70 个 `p*` 园区库结构相同，仅索引 1 个模板 | embedding 生成量从 9715 减少到 341 张表 |
| 增量索引 | 支持结构变化检测和增量更新 | 新增/修改表可增量索引，无需全量重建 |

### 1.3 范围界定

**本次实现:**
- Phase 1: `DatabaseManager` 跨库查询能力
- Phase 2: 数据模型升级（命名空间支持）
- Phase 3: `SchemaIndexer` 多库索引 + 园区库模板
- Phase 4: `GraphStore` 命名空间过滤
- Phase 5: 增量索引机制

**排除范围:**
- `parkstandard` 库（标准化模板库，不索引）
- 系统库（`information_schema`, `mysql`, `performance_schema`, `sys`）

### 1.4 关键决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 命名空间格式 | `database.table` | SQL 标准格式，直观易懂 |
| 园区库模板选择 | 字典序第一个 | 简单可靠，结构一致 |
| embedding 存储 | 模板引用（复制） | ChromaDB 查询效率更高 |
| 搜索排序 | 主库优先 + 相似度 | 业务库优先级更高 |

---

## 2. 现状分析

### 2.1 数据库分布

```
服务器: 101.231.132.10:33306

业务库分类：
├── 独立业务库（需独立索引）
│   ├── parkcloud:         145 张表  - 主业务库
│   ├── db_parking_center:  56 张表  - 线下场库中心
│   └── cloudinterface:      9 张表  - 云云接口配置
│
├── 园区库（p* 开头，结构相同）
│   ├── 模板库（选 1 个）: ~131 张表
│   └── 实例库（69 个）:   ~9,039 张表（复用模板）
│
└── 排除库
    └── parkstandard:       51 张表  - 标准化模板库

系统库（自动排除）:
└── information_schema, mysql, performance_schema, sys
```

### 2.2 当前代码问题

| 文件 | 问题 | 影响 |
|------|------|------|
| `src/config.py:6-14` | `get_db_url()` 固定连接单库 | 无法跨库查询 |
| `src/db_manager.py:68-71` | `get_all_tables()` 仅返回当前库表 | 缺少 9570 张表 |
| `src/metadata/schema_indexer.py:236-243` | `WHERE TABLE_SCHEMA = DATABASE()` | 仅查当前库 |
| `src/metadata/graph_store.py:90` | `table_id = table.table_name` | 同名表 ID 冲突 |

### 2.3 实际索引量计算

| 类型 | 表数量 | 需生成 embedding | 说明 |
|------|--------|-----------------|------|
| parkcloud | 145 | ✅ 是 | 主业务库 |
| db_parking_center | 56 | ✅ 是 | 线下场库中心 |
| cloudinterface | 9 | ✅ 是 | 云云接口配置 |
| 园区库模板（1个） | ~131 | ✅ 是 | 选字典序第一个 |
| 园区库实例（69个） | ~9,039 | ❌ 复用模板 | 仅复制元数据 |
| **总计** | ~9,715 | **341 张表** | **节省 96.5% embedding 调用** |

### 2.4 ChromaDB 承载能力评估

| 指标 | ChromaDB 能力 | 本项目场景 | 评估 |
|------|--------------|-----------|------|
| 最大向量数 | 百万级 | ~7,000 | ✅ 绰绰有余 |
| 查询延迟 (10万向量) | <10ms | 预计 <1ms | ✅ 极快 |
| 内存占用 | ~1KB/向量 | ~7MB | ✅ 可忽略 |
| 磁盘占用 | 取决于配置 | 几十 MB | ✅ 可接受 |

---

## 3. 架构设计

### 3.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                     多库命名空间知识图谱                              │
├─────────────────────────────────────────────────────────────────────┤
│  namespace: "parkcloud"                                             │
│  ├── cloud_fixed_plate (表元数据 + embedding)                       │
│  ├── cloud_operator                                                 │
│  └── ... (145 张表)                                                 │
├─────────────────────────────────────────────────────────────────────┤
│  namespace: "db_parking_center"                                     │
│  ├── t_in_info                                                      │
│  ├── t_out_info                                                     │
│  └── ... (56 张表)                                                  │
├─────────────────────────────────────────────────────────────────────┤
│  namespace: "cloudinterface"                                        │
│  ├── config                                                         │
│  └── ... (9 张表)                                                   │
├─────────────────────────────────────────────────────────────────────┤
│  namespace: "p* (park_template)"                                    │
│  ├── 模板表结构 (131 张表的元数据 + embedding)                       │
│  ├── is_template: true                                              │
│  └── instance_databases: [p210113175340, p210121185450, ...]        │
│      └── 69 个园区库复用此模板（仅复制元数据，不生成 embedding）       │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 索引流程设计

```
┌─────────────────────────────────────────────────────────────────────┐
│                      全库索引流程                                    │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Step 1: 获取数据库分类                                              │
│   - 独立业务库: [parkcloud, db_parking_center, cloudinterface]      │
│   - 园区库模板: 选字典序第一个作为 p_template                        │
│   - 园区库实例: 其余 69 个 p* 库                                    │
│   - 排除: parkstandard, 系统库                                      │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Step 2: 索引独立业务库（可并行）                                     │
│   ├── 索引 parkcloud (145 张表)                                     │
│   ├── 索引 db_parking_center (56 张表)                              │
│   └── 索引 cloudinterface (9 张表)                                  │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Step 3: 索引园区库模板                                              │
│   - 选择第一个园区库作为模板（如 p210113175340）                     │
│   - 索引 131 张表的元数据和 embedding                               │
│   - 标记 is_template = True                                         │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Step 4: 克隆模板到其他园区库                                        │
│   - 复制元数据，修改 database_name                                   │
│   - 复用 embedding（不重新生成）                                     │
│   - 记录映射关系                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Step 5: 保存知识图谱                                                │
│   - 保存命名空间映射                                                 │
│   - 保存模板关系                                                     │
│   - 保存园区库实例列表                                               │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.3 查询流程设计

```
用户查询: "查询车牌相关的表"
        │
        ▼
┌───────────────────────────────────────────┐
│ EmbeddingService.embed_text()             │
│ 生成查询向量                               │
└───────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────┐
│ GraphStore.search_with_namespace()        │
│ namespace=None (搜索所有库)                │
│ 或 namespace="parkcloud" (限定单库)        │
└───────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────┐
│ 结果排序策略:                             │
│ 1. 主业务库优先 (parkcloud > 其他)        │
│ 2. 按相似度分数排序                       │
│ 3. 按库名字典序                           │
└───────────────────────────────────────────┘
        │
        ▼
返回结果:
[
  {id: "parkcloud.cloud_fixed_plate", score: 0.95, namespace: "parkcloud"},
  {id: "db_parking_center.t_plate_info", score: 0.89, namespace: "db_parking_center"},
  {id: "p_template.cloud_fixed_plate", score: 0.88, namespace: "p_template"},
  ...
]
```

---

## 4. 数据模型升级

### 4.1 TableMetadata 升级

```python
class TableMetadata(BaseModel):
    """表元数据（升级版）"""
    table_name: str
    database_name: str = ""
    namespace: str = ""                # 新增：命名空间标识 (database_name)

    # 园区库模板相关
    is_template: bool = False          # 新增：是否为模板表
    template_for: List[str] = []       # 新增：复用此模板的库名列表
    template_source: Optional[str] = None  # 新增：模板来源库名（实例表用）

    # 现有字段保持不变
    comment: str = ""
    columns: List[ColumnMetadata] = Field(default_factory=list)
    foreign_keys: List[ForeignKeyRelation] = Field(default_factory=list)
    business_domain: str = "其他"
    schema_text: str = ""
    tags: List[str] = Field(default_factory=list)

    @property
    def qualified_name(self) -> str:
        """获取完全限定名: database.table"""
        if self.database_name:
            return f"{self.database_name}.{self.table_name}"
        return self.table_name
```

### 4.2 KnowledgeGraph 升级

```python
class KnowledgeGraph(BaseModel):
    """知识图谱（升级版）"""
    version: str = "2.0"  # 版本升级
    created_at: str
    updated_at: str
    tables: List[TableMetadata]

    # 新增：命名空间索引
    namespaces: Dict[str, str] = {}    # {库名: 命名空间类型}
    # 命名空间类型: "primary" | "secondary" | "park_template" | "park_instance"

    # 新增：模板映射
    template_mapping: Dict[str, str] = {}  # {园区库名: 模板库名}

    # 新增：园区库实例列表
    park_instances: List[str] = []     # 所有 p* 库名

    # 新增：数据库分类
    database_classification: Dict[str, str] = {}  # {库名: 分类}

    def get_table_by_qualified_name(self, qualified_name: str) -> Optional[TableMetadata]:
        """通过完全限定名获取表"""
        for table in self.tables:
            if table.qualified_name == qualified_name:
                return table
        return None

    def get_tables_by_namespace(self, namespace: str) -> List[TableMetadata]:
        """获取指定命名空间的所有表"""
        return [t for t in self.tables if t.namespace == namespace]

    def get_template_instances(self, template_db: str) -> List[str]:
        """获取使用指定模板的所有实例库"""
        return [k for k, v in self.template_mapping.items() if v == template_db]
```

### 4.3 新增 DatabaseClassification 模型

```python
from enum import Enum

class DatabaseType(str, Enum):
    """数据库类型枚举"""
    PRIMARY = "primary"           # 主业务库 (parkcloud)
    SECONDARY = "secondary"       # 次要业务库 (db_parking_center, cloudinterface)
    PARK_TEMPLATE = "park_template"  # 园区库模板
    PARK_INSTANCE = "park_instance"  # 园区库实例
    EXCLUDED = "excluded"         # 排除的库

class DatabaseClassification(BaseModel):
    """数据库分类配置"""
    primary_databases: List[str] = ["parkcloud"]
    secondary_databases: List[str] = ["db_parking_center", "cloudinterface"]
    excluded_databases: List[str] = ["parkstandard"]

    # 园区库配置
    park_prefix: str = "p"
    park_template_db: Optional[str] = None  # 自动选择第一个园区库

    # 系统库（自动排除）
    system_databases: List[str] = [
        "information_schema",
        "mysql",
        "performance_schema",
        "sys"
    ]

    def classify_database(self, db_name: str) -> DatabaseType:
        """分类单个数据库"""
        if db_name in self.system_databases or db_name in self.excluded_databases:
            return DatabaseType.EXCLUDED
        if db_name in self.primary_databases:
            return DatabaseType.PRIMARY
        if db_name in self.secondary_databases:
            return DatabaseType.SECONDARY
        if db_name.startswith(self.park_prefix):
            if db_name == self.park_template_db:
                return DatabaseType.PARK_TEMPLATE
            return DatabaseType.PARK_INSTANCE
        return DatabaseType.SECONDARY  # 默认为次要业务库
```

### 4.4 索引进度模型升级

```python
class MultiDatabaseIndexProgress(BaseModel):
    """多库索引进度"""
    status: str = "pending"
    total_databases: int = 0
    indexed_databases: int = 0
    current_database: str = ""

    # 详细进度
    database_progress: Dict[str, IndexProgress] = {}  # {库名: 单库进度}

    # 模板进度
    template_indexed: bool = False
    template_cloned: bool = False
    clone_progress: int = 0  # 已克隆的实例数

    last_updated: str = ""
    errors: List[str] = []

    def get_overall_progress(self) -> float:
        """获取整体进度百分比"""
        if self.total_databases == 0:
            return 0.0
        return (self.indexed_databases / self.total_databases) * 100
```

---

## 5. 核心组件升级

### 5.1 DatabaseManager 升级

**新增跨库查询方法：**

```python
class DatabaseManager:
    """数据库管理器（升级版）"""

    def __init__(self, specific_db: Optional[str] = None):
        """
        初始化数据库管理器

        Args:
            specific_db: 指定连接的数据库，None 表示不指定（可跨库查询）
        """
        self.specific_db = specific_db
        self.db_url = self._build_db_url(specific_db)
        # ... 其他初始化代码

    def _build_db_url(self, db_name: Optional[str]) -> str:
        """构建数据库连接 URL"""
        base_url = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/"
        if db_name:
            return base_url + db_name
        return base_url  # 不指定数据库，支持跨库查询

    def get_all_databases(self, exclude_system: bool = True) -> List[str]:
        """获取所有数据库列表"""
        with self.get_connection() as conn:
            result = conn.execute(text("SHOW DATABASES"))
            databases = [row[0] for row in result.fetchall()]

        if exclude_system:
            system_dbs = {'information_schema', 'mysql', 'performance_schema', 'sys'}
            databases = [db for db in databases if db not in system_dbs]

        return databases

    def get_tables_in_database(self, db_name: str) -> List[str]:
        """获取指定数据库的所有表名"""
        sql = """
            SELECT TABLE_NAME
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = :db_name
            AND TABLE_TYPE = 'BASE TABLE'
        """
        with self.get_connection() as conn:
            result = conn.execute(text(sql), {"db_name": db_name})
            return [row[0] for row in result.fetchall()]

    def get_table_schema_cross_db(self, db_name: str, table_name: str) -> List[Dict]:
        """跨库获取表结构信息"""
        # ... 实现代码

    def check_tables_structure_match(self, db1: str, db2: str) -> bool:
        """检查两个数据库的表结构是否相同"""
        # ... 实现代码
```

### 5.2 SchemaIndexer 升级

**新增多库索引方法：**

```python
class SchemaIndexer:
    """Schema 索引器（升级版）"""

    def __init__(self, ...):
        # 跨库模式初始化
        self.db_manager = db_manager or DatabaseManager(specific_db=None)

    def index_all_databases(self) -> MultiDatabaseIndexResult:
        """全库索引主流程"""
        # Step 1: 获取数据库分类
        databases = self.db_manager.get_all_databases(exclude_system=True)
        classified = self._classify_databases(databases)

        # Step 2: 索引独立业务库
        for db_name in classified['primary'] + classified['secondary']:
            self.index_database(db_name)

        # Step 3: 索引园区库模板
        if classified['park']:
            template_db = sorted(classified['park'])[0]
            self.index_park_template(template_db)

            # Step 4: 克隆模板到其他园区库
            other_park_dbs = [db for db in classified['park'] if db != template_db]
            self.clone_template_to_instances(template_db, other_park_dbs)

        # Step 5: 保存知识图谱
        self._save_multi_database_graph(results, classified)

    def index_database(self, db_name: str) -> IndexResult:
        """索引单个数据库"""
        # ... 实现代码

    def index_park_template(self, template_db: str) -> IndexResult:
        """索引园区库模板"""
        # ... 实现代码

    def clone_template_to_instances(self, template_db: str, instance_dbs: List[str]) -> CloneResult:
        """将模板克隆到其他园区库实例"""
        # ... 实现代码
```

### 5.3 GraphStore 升级

**新增命名空间支持：**

```python
class GraphStore:
    """图谱存储（升级版）"""

    def add_table_with_namespace(self, table: TableMetadata, embedding: List[float], namespace: str) -> None:
        """添加带命名空间的表向量"""
        # 使用完全限定名作为 ID
        table_id = f"{namespace}.{table.table_name}"

        metadata = {
            "table_name": table.table_name,
            "database_name": namespace,
            "namespace": namespace,
            "business_domain": table.business_domain,
            "is_template": table.is_template,
            # ...
        }

        self.table_collection.upsert(
            ids=[table_id],
            embeddings=[embedding],
            metadatas=[metadata]
        )

    def search_with_namespace(self, embedding: List[float], namespace: Optional[str] = None, top_k: int = 10) -> List[Dict]:
        """支持命名空间过滤的搜索"""
        where_filter = None
        if namespace:
            where_filter = {"namespace": namespace}

        results = self.table_collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            where=where_filter
        )

        # 排序：主业务库优先
        formatted = self._format_results(results)
        if namespace is None:
            formatted.sort(key=lambda x: (
                0 if x["namespace"] == "parkcloud" else 1,
                -x["similarity_score"]
            ))

        return formatted[:top_k]

    def clone_namespace(self, source_namespace: str, target_namespace: str) -> None:
        """克隆命名空间（复制元数据，复用 embedding）"""
        # 获取源命名空间的所有向量
        results = self.table_collection.get(where={"namespace": source_namespace})

        if results["ids"]:
            # 修改 ID 和元数据
            new_ids = [id.replace(f"{source_namespace}.", f"{target_namespace}.") for id in results["ids"]]
            new_metadatas = [{**m, "namespace": target_namespace} for m in results["metadatas"]]

            # 写入目标命名空间（复用 embedding）
            self.table_collection.upsert(
                ids=new_ids,
                embeddings=results["embeddings"],
                metadatas=new_metadatas
            )

    def mark_as_template(self, namespace: str) -> None:
        """标记命名空间为模板"""
        # ... 实现代码
```

---

## 6. 园区库模板机制

### 6.1 模板选择策略

```python
def select_park_template(databases: List[str]) -> str:
    """
    选择园区库模板

    策略：选择字典序第一个园区库作为模板

    Args:
        databases: 园区库列表

    Returns:
        模板数据库名
    """
    park_dbs = [db for db in databases if db.startswith('p')]
    if not park_dbs:
        raise ValueError("没有找到园区库")
    return sorted(park_dbs)[0]
```

### 6.2 结构验证

```python
def validate_park_structure(
    db_manager: DatabaseManager,
    template_db: str,
    instance_dbs: List[str]
) -> Tuple[List[str], List[str]]:
    """
    验证园区库结构一致性

    Returns:
        (匹配的库列表, 不匹配的库列表)
    """
    matched = []
    mismatched = []

    for instance_db in instance_dbs:
        if db_manager.check_tables_structure_match(template_db, instance_db):
            matched.append(instance_db)
        else:
            mismatched.append(instance_db)
            logger.warning(f"结构不匹配: {instance_db}")

    return matched, mismatched
```

### 6.3 模板克隆流程

```
源（模板）: p210113175340
├── 表向量 (131 个)
│   ├── p210113175340.cloud_fixed_plate → embedding_A
│   └── ...
└── 字段向量 (~2620 个)

克隆操作:
1. 读取源命名空间的所有向量和元数据
2. 修改 ID: p210113175340.* → p210121185450.*
3. 修改元数据: namespace, database_name, is_template
4. 复用 embedding（不重新生成）
5. 写入目标命名空间

目标（实例）: p210121185450
├── 表向量 (131 个，复用 embedding)
│   ├── p210121185450.cloud_fixed_plate → embedding_A (复用)
│   └── ...
└── 字段向量 (~2620 个，复用 embedding)
```

---

## 7. 增量索引策略

### 7.1 变化检测机制

```python
class ChangeDetector:
    """数据库变化检测器"""

    def detect_changes(self, db_name: str) -> ChangeReport:
        """检测数据库结构变化"""
        # 获取当前数据库的表
        current_tables = set(self.db_manager.get_tables_in_database(db_name))

        # 获取已索引的表
        graph = self.graph_store.load_graph()
        indexed_tables = {t.table_name for t in graph.tables if t.database_name == db_name}

        # 计算变化
        added_tables = current_tables - indexed_tables
        removed_tables = indexed_tables - current_tables
        modified_tables = self._detect_modified_tables(db_name, current_tables & indexed_tables)

        return ChangeReport(
            database=db_name,
            added_tables=list(added_tables),
            removed_tables=list(removed_tables),
            modified_tables=modified_tables
        )
```

### 7.2 增量索引流程

```
触发条件：
├── 定时检测（每日/每周）
├── 手动触发
└── API 调用触发

检测流程：
┌─────────────────┐
│ 获取当前库结构   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     结构一致      ┌─────────────────┐
│ 与已索引结构对比  │ ───────────────→ │ 跳过，无需更新   │
└────────┬────────┘                   └─────────────────┘
         │ 结构变化
         ▼
┌─────────────────┐
│ 判断变化类型     │
└────────┬────────┘
         │
    ┌────┴────┬─────────────┐
    │         │             │
    ▼         ▼             ▼
┌───────┐ ┌───────┐   ┌───────────┐
│新增表  │ │删除表  │   │字段变化   │
└───┬───┘ └───┬───┘   └─────┬─────┘
    │         │             │
    ▼         ▼             ▼
┌───────┐ ┌───────┐   ┌───────────┐
│增量索引│ │删除向量│   │更新表向量  │
└───────┘ └───────┘   └───────────┘
```

### 7.3 园区库增量同步

```python
def sync_park_instances(indexer: SchemaIndexer, template_db: str, instance_dbs: List[str]) -> SyncResult:
    """
    同步园区库模板到所有实例

    当模板库结构变化时，自动同步到所有实例库
    """
    # 检测模板变化
    detector = ChangeDetector(indexer.graph_store, indexer.db_manager)
    template_changes = detector.detect_changes(template_db)

    if not template_changes.has_changes():
        return SyncResult(template_db=template_db, synced=[], mismatched=[])

    # 重新索引模板
    indexer.index_park_template(template_db)

    # 验证并同步到实例
    synced = []
    mismatched = []

    for instance_db in instance_dbs:
        if indexer.db_manager.check_tables_structure_match(template_db, instance_db):
            indexer.graph_store.delete_namespace(instance_db)
            indexer.graph_store.clone_namespace(template_db, instance_db)
            synced.append(instance_db)
        else:
            mismatched.append(instance_db)

    return SyncResult(template_db=template_db, synced=synced, mismatched=mismatched)
```

---

## 8. ChromaDB 性能分析

### 8.1 向量数量估算

| 类型 | 数量 | 说明 |
|------|------|------|
| 表级向量 | ~341 | 3 个独立库 + 1 个模板库 |
| 字段级向量 | ~6,820 | 341 表 × 平均 20 字段 |
| **总向量数** | **~7,161** | 远低于 9715 |

### 8.2 性能基准

| 指标 | ChromaDB 能力 | 本项目场景 | 评估 |
|------|--------------|-----------|------|
| 最大向量数 | 百万级 | ~7,000 | ✅ 绰绰有余 |
| 查询延迟 (10万向量) | <10ms | 预计 <1ms | ✅ 极快 |
| 内存占用 | ~1KB/向量 | ~7MB | ✅ 可忽略 |

### 8.3 查询优化策略

```python
# 1. 命名空间过滤（减少搜索范围）
results = graph_store.search_with_namespace(
    embedding=query_embedding,
    namespace="parkcloud",  # 仅搜索 parkcloud 库
    top_k=10
)

# 2. 园区库查询优化（搜索模板即可）
results = graph_store.search_with_namespace(
    embedding=query_embedding,
    namespace="p_template",  # 搜索模板库
    top_k=10
)

# 3. 主业务库优先排序
results.sort(key=lambda x: (
    0 if x["namespace"] == "parkcloud" else 1,
    -x["similarity_score"]
))
```

---

## 9. 测试策略

### 9.1 单元测试

```python
# tests/metadata/test_multi_database.py

class TestDatabaseManager:
    """DatabaseManager 跨库功能测试"""

    def test_get_all_databases_excludes_system(self, db_manager):
        databases = db_manager.get_all_databases(exclude_system=True)
        assert "information_schema" not in databases
        assert "parkcloud" in databases

    def test_check_tables_structure_match(self, db_manager):
        park_dbs = [db for db in db_manager.get_all_databases() if db.startswith('p')]
        if len(park_dbs) >= 2:
            result = db_manager.check_tables_structure_match(park_dbs[0], park_dbs[1])
            assert result == True


class TestGraphStore:
    """GraphStore 命名空间测试"""

    def test_search_with_namespace_filter(self, graph_store):
        results = graph_store.search_with_namespace(
            embedding=[0.1] * 1024,
            namespace="parkcloud",
            top_k=10
        )
        for r in results:
            assert r["namespace"] == "parkcloud"
```

### 9.2 集成测试

```python
class TestMultiDatabaseIndexing:
    """多库索引集成测试"""

    def test_full_indexing_workflow(self):
        indexer = SchemaIndexer(env="test")
        result = indexer.index_all_databases()

        assert result.success
        assert "parkcloud" in result.databases

        graph = indexer.graph_store.load_graph()
        assert "parkcloud" in graph.namespaces
```

### 9.3 性能测试

```python
class TestChromaDBPerformance:
    """ChromaDB 性能测试"""

    def test_query_latency(self, graph_store):
        latencies = []
        for _ in range(100):
            start = time.time()
            graph_store.search_with_namespace(query_embedding, top_k=10)
            latencies.append(time.time() - start)

        avg_latency = sum(latencies) / len(latencies) * 1000
        assert avg_latency < 10, f"平均延迟 {avg_latency:.2f}ms 超过阈值"
```

---

## 10. 实施计划

### 10.1 阶段划分

| 阶段 | 任务 | 预计工时 | 依赖 |
|------|------|---------|------|
| **Phase 1** | DatabaseManager 跨库查询 | 2h | 无 |
| **Phase 2** | 数据模型升级 | 1h | 无 |
| **Phase 3** | SchemaIndexer 多库索引 | 4h | Phase 1, 2 |
| **Phase 4** | GraphStore 命名空间 | 2h | Phase 2 |
| **Phase 5** | 园区库模板机制 | 3h | Phase 3, 4 |
| **Phase 6** | 增量索引机制 | 2h | Phase 3, 4 |
| **Phase 7** | 测试与验证 | 2h | Phase 1-6 |
| **总计** | - | **16h** | - |

### 10.2 详细任务清单

#### Phase 1: DatabaseManager 跨库查询 (2h)

- [ ] 1.1 新增 `_build_db_url()` 方法支持无数据库连接
- [ ] 1.2 新增 `get_all_databases()` 方法
- [ ] 1.3 新增 `get_tables_in_database()` 方法
- [ ] 1.4 新增 `get_table_schema_cross_db()` 方法
- [ ] 1.5 新增 `check_tables_structure_match()` 方法
- [ ] 1.6 编写单元测试

#### Phase 2: 数据模型升级 (1h)

- [ ] 2.1 升级 `TableMetadata` 添加命名空间字段
- [ ] 2.2 升级 `KnowledgeGraph` 添加命名空间索引
- [ ] 2.3 新增 `DatabaseClassification` 模型
- [ ] 2.4 新增 `MultiDatabaseIndexProgress` 模型

#### Phase 3-6: 略（详见各阶段设计）

### 10.3 验收标准

| 验收项 | 标准 | 验证方法 |
|--------|------|---------|
| 索引范围 | 索引 76 个业务库（排除 parkstandard） | 检查 `table_graph.json` |
| 向量数量 | 约 7,161 个向量（341 表 + 6820 字段） | 检查 ChromaDB count |
| 查询性能 | 平均延迟 < 10ms | 运行性能测试 |
| 命名空间 | 支持 `database.table` 格式 | 测试同名表查询 |
| 园区库优化 | 69 个实例库复用模板 embedding | 验证 embedding 复用 |
| 增量索引 | 支持新增/修改/删除表检测 | 运行增量索引测试 |

---

## 附录 A：设计决策记录

| 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|
| 命名空间格式 | `db.table` vs `table@db` | `db.table` | SQL 标准格式，直观易懂 |
| 园区库模板选择 | 第一个 vs 随机 vs 手动指定 | 字典序第一个 | 简单可靠，结构一致 |
| embedding 存储 | 每表一份 vs 模板引用 | 模板引用（复制） | ChromaDB 查询效率更高 |
| 搜索排序 | 相似度优先 vs 命名空间优先 | 主库优先 + 相似度 | 业务库优先级更高 |
| 增量检测 | 轮询 vs 事件触发 | 手动触发 + 定时 | MySQL 无原生 DDL 事件 |

---

## 附录 B：API 参考

### DatabaseManager 新增方法

```python
# 获取所有数据库
databases = db_manager.get_all_databases(exclude_system=True)

# 获取指定库的表
tables = db_manager.get_tables_in_database("parkcloud")

# 跨库获取表结构
columns = db_manager.get_table_schema_cross_db("parkcloud", "cloud_fixed_plate")

# 检查结构匹配
match = db_manager.check_tables_structure_match("p210113175340", "p210121185450")
```

### SchemaIndexer 新增方法

```python
# 全库索引
result = indexer.index_all_databases()

# 单库索引
result = indexer.index_database("parkcloud")

# 园区库模板索引
result = indexer.index_park_template("p210113175340")

# 克隆模板到实例
result = indexer.clone_template_to_instances("p210113175340", ["p210121185450"])
```

### GraphStore 新增方法

```python
# 带命名空间的搜索
results = graph_store.search_with_namespace(
    embedding=query_embedding,
    namespace="parkcloud",  # 可选
    top_k=10
)

# 标记为模板
graph_store.mark_as_template("p210113175340")

# 克隆命名空间
graph_store.clone_namespace("p210113175340", "p210121185450")
```

---

**文档完成。**
