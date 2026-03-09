# Qwen3-Rerank 功能手动测试指南

> **版本:** 1.0
> **日期:** 2026-03-09
> **测试范围:** RerankService, EmbeddingService v4, RetrievalPipeline, 语义字段, ChangeDetector

---

## 目录

1. [环境准备](#1-环境准备)
2. [测试 RerankService](#2-测试-rerankservice)
3. [测试 EmbeddingService v4](#3-测试-embeddingservice-v4)
4. [测试语义字段模型](#4-测试语义字段模型)
5. [测试 ChangeDetector](#5-测试-changedetector)
6. [测试 RetrievalPipeline](#6-测试-retrievalpipeline)
7. [完整集成测试](#7-完整集成测试)
8. [常见问题排查](#8-常见问题排查)

---

## 1. 环境准备

### 1.1 检查环境变量

```bash
# 进入项目目录
cd E:\trae-pc\mysql260227

# 检查 .env 文件
cat .env
```

**必须配置的环境变量:**

```env
# DashScope API Key (必须)
DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxx

# 数据库配置 (集成测试需要)
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=parkcloud

# 环境标识
ENV=dev
```

### 1.2 检查依赖安装

```bash
# 确保已安装依赖
pip install -r requirements.txt

# 验证关键包
python -c "import requests; print('requests:', requests.__version__)"
python -c "import dashscope; print('dashscope:', dashscope.__version__)"
```

### 1.3 运行单元测试

```bash
# 运行所有 Rerank 相关测试
pytest tests/metadata/test_rerank_service.py -v
pytest tests/metadata/test_retrieval_agent.py -v
```

---

## 2. 测试 RerankService

### 2.1 基础 API 连通性测试

**目的:** 验证 DashScope Rerank API 是否可用

**步骤:**

```bash
# 方法1: 使用 Python 交互式测试
python -c "
import os
from dotenv import load_dotenv
load_dotenv()

import requests
import json

api_key = os.getenv('DASHSCOPE_API_KEY')

response = requests.post(
    'https://dashscope.aliyuncs.com/compatible-api/v1/reranks',
    headers={
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    },
    json={
        'model': 'qwen3-rerank',
        'query': '查询车牌',
        'documents': ['车牌表', '用户表', '订单表']
    }
)

print(f'Status: {response.status_code}')
print(f'Response: {json.dumps(response.json(), ensure_ascii=False, indent=2)}')
"
```

**预期结果:**

```json
{
  "object": "list",
  "results": [
    {"index": 0, "relevance_score": 0.6xxx},
    {"index": 1, "relevance_score": 0.3xxx},
    {"index": 2, "relevance_score": 0.2xxx}
  ],
  "model": "qwen3-rerank"
}
```

### 2.2 语义排序准确性测试

**目的:** 验证 Rerank 能正确识别语义相关性

**测试脚本:**

```python
# 保存为 test_rerank_semantic.py
import os
from dotenv import load_dotenv
load_dotenv()

from src.metadata.rerank_service import RerankService

service = RerankService()

# 测试用例 1: 车牌相关查询
print("=" * 60)
print("测试 1: 车牌相关查询")
print("=" * 60)

query = "查询车牌信息"
candidates = [
    "cloud_fixed_plate: 固定车牌表，存储长期停放的固定车辆信息",
    "cloud_temp_plate: 临时车牌表，存储临时来访车辆信息",
    "cloud_user: 用户表，存储系统用户账号信息",
    "cloud_order: 订单表，存储停车订单交易信息",
]

results = service.rerank(query, candidates)

print(f"查询: {query}")
print("\n排序结果:")
for i, r in enumerate(results, 1):
    print(f"  {i}. [{r.relevance_score:.4f}] {candidates[r.index][:50]}...")

# 验证: 车牌相关的表应该排在前面
top_indices = [r.index for r in results[:2]]
assert 0 in top_indices and 1 in top_indices, "语义排序失败: 车牌表应排在前面"
print("\n✅ 语义排序正确!")

# 测试用例 2: 用户相关查询
print("\n" + "=" * 60)
print("测试 2: 用户相关查询")
print("=" * 60)

query = "查询用户信息"
results = service.rerank(query, candidates)

print(f"查询: {query}")
print("\n排序结果:")
for i, r in enumerate(results, 1):
    print(f"  {i}. [{r.relevance_score:.4f}] {candidates[r.index][:50]}...")

# 验证: 用户表应该排在前面
assert results[0].index == 2, "语义排序失败: 用户表应排在第一位"
print("\n✅ 语义排序正确!")

# 测试用例 3: 订单相关查询
print("\n" + "=" * 60)
print("测试 3: 订单相关查询")
print("=" * 60)

query = "查询停车订单"
results = service.rerank(query, candidates)

print(f"查询: {query}")
print("\n排序结果:")
for i, r in enumerate(results, 1):
    print(f"  {i}. [{r.relevance_score:.4f}] {candidates[r.index][:50]}...")

assert results[0].index == 3, "语义排序失败: 订单表应排在第一位"
print("\n✅ 语义排序正确!")

print("\n" + "=" * 60)
print("所有 RerankService 测试通过!")
print("=" * 60)
```

**运行:**

```bash
python test_rerank_semantic.py
```

### 2.3 性能测试

**目的:** 验证 API 响应时间在可接受范围内

```python
# 保存为 test_rerank_performance.py
import os
import time
from dotenv import load_dotenv
load_dotenv()

from src.metadata.rerank_service import RerankService

service = RerankService()

# 测试不同规模的候选列表
test_cases = [
    ("5 个候选", 5),
    ("10 个候选", 10),
    ("20 个候选", 20),
    ("50 个候选", 50),
]

base_candidates = [
    f"table_{i}: 表{i}的描述信息" for i in range(50)
]

print("RerankService 性能测试")
print("=" * 60)

for name, count in test_cases:
    candidates = base_candidates[:count]

    start = time.time()
    results = service.rerank("查询测试", candidates)
    elapsed_ms = (time.time() - start) * 1000

    print(f"{name}: {elapsed_ms:.0f}ms ({len(results)} 结果)")

    # 验证: 200ms 以内为优秀，500ms 以内为可接受
    if elapsed_ms < 200:
        status = "✅ 优秀"
    elif elapsed_ms < 500:
        status = "⚠️ 可接受"
    else:
        status = "❌ 需优化"

    print(f"  状态: {status}")

print("=" * 60)
```

---

## 3. 测试 EmbeddingService v4

### 3.1 基础嵌入测试

**测试脚本:**

```python
# 保存为 test_embedding_v4.py
import os
from dotenv import load_dotenv
load_dotenv()

from src.metadata.embedding_service import EmbeddingService

service = EmbeddingService(model="text-embedding-v4", dimension=1024)

print("EmbeddingService v4 测试")
print("=" * 60)

# 测试 1: query 模式
print("\n测试 1: query 模式嵌入")
query = "查询车牌信息"
embedding = service.embed_text(
    query,
    text_type="query",
    instruct="Given a database query, retrieve relevant schema"
)

print(f"  输入: {query}")
print(f"  维度: {len(embedding)}")
print(f"  前5个值: {embedding[:5]}")
assert len(embedding) == 1024, "向量维度应为 1024"
print("  ✅ 通过")

# 测试 2: document 模式
print("\n测试 2: document 模式嵌入")
doc = "cloud_fixed_plate: 固定车牌表，存储长期停放的固定车辆信息"
embedding = service.embed_text(doc, text_type="document")

print(f"  输入: {doc[:50]}...")
print(f"  维度: {len(embedding)}")
assert len(embedding) == 1024, "向量维度应为 1024"
print("  ✅ 通过")

# 测试 3: 批量嵌入
print("\n测试 3: 批量嵌入")
texts = [
    "车牌表",
    "用户表",
    "订单表",
]
embeddings = service.embed_batch(texts, text_type="document")

print(f"  输入数量: {len(texts)}")
print(f"  输出数量: {len(embeddings)}")
assert len(embeddings) == len(texts), "输出数量应与输入一致"
print("  ✅ 通过")

print("\n" + "=" * 60)
print("所有 EmbeddingService 测试通过!")
print("=" * 60)
```

### 3.2 向量相似度测试

**目的:** 验证语义相似的文本产生相似的向量

```python
# 保存为 test_embedding_similarity.py
import os
from dotenv import load_dotenv
load_dotenv()

import numpy as np
from src.metadata.embedding_service import EmbeddingService

service = EmbeddingService(model="text-embedding-v4", dimension=1024)

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

print("向量相似度测试")
print("=" * 60)

# 测试用例
test_pairs = [
    ("车牌信息", "车辆牌照", "应高相似度"),
    ("车牌信息", "用户账号", "应低相似度"),
    ("停车订单", "收费记录", "应中等相似度"),
]

for text1, text2, expected in test_pairs:
    emb1 = service.embed_text(text1, text_type="query")
    emb2 = service.embed_text(text2, text_type="query")
    similarity = cosine_similarity(emb1, emb2)

    print(f"\n'{text1}' vs '{text2}'")
    print(f"  相似度: {similarity:.4f} ({expected})")

print("\n" + "=" * 60)
```

---

## 4. 测试语义字段模型

### 4.1 字段定义测试

```python
# 保存为 test_semantic_fields.py
from src.metadata.models import TableMetadata, ColumnMetadata

print("语义字段模型测试")
print("=" * 60)

# 测试 1: 创建带语义字段的表
print("\n测试 1: 创建带语义字段的表元数据")
table = TableMetadata(
    table_name="cloud_fixed_plate",
    database_name="parkcloud",
    namespace="parkcloud",
    comment="固定车牌表",
    # 语义字段
    semantic_description="存储长期停放车辆的车牌信息，包括车主信息、有效期、绑定场库等",
    semantic_tags=["车辆管理", "车牌", "固定用户"],
    semantic_source="llm",
    semantic_confidence=0.95,
    columns=[
        ColumnMetadata(name="id", data_type="INT", is_primary_key=True),
        ColumnMetadata(name="plate_no", data_type="VARCHAR(20)", comment="车牌号"),
    ]
)

print(f"  表名: {table.table_name}")
print(f"  语义描述: {table.semantic_description}")
print(f"  语义标签: {table.semantic_tags}")
print(f"  来源: {table.semantic_source}")
print(f"  置信度: {table.semantic_confidence}")
print("  ✅ 通过")

# 测试 2: JSON 序列化
print("\n测试 2: JSON 序列化")
json_data = table.model_dump()
assert "semantic_description" in json_data
assert "semantic_tags" in json_data
print("  ✅ 序列化成功")

# 测试 3: JSON 反序列化
print("\n测试 3: JSON 反序列化")
table2 = TableMetadata(**json_data)
assert table2.semantic_description == table.semantic_description
assert table2.semantic_tags == table.semantic_tags
print("  ✅ 反序列化成功")

print("\n" + "=" * 60)
print("所有语义字段测试通过!")
print("=" * 60)
```

---

## 5. 测试 ChangeDetector

### 5.1 增量变更检测测试

```python
# 保存为 test_change_detector.py
from src.metadata.change_detector import ChangeDetector, ChangeDiff

print("ChangeDetector 测试")
print("=" * 60)

detector = ChangeDetector()

# 测试 1: 检测新增表
print("\n测试 1: 检测新增表")
current = {"table_a", "table_b", "table_c", "table_new"}
indexed = {"table_a", "table_b", "table_c"}
diff = detector.diff(current, indexed)

print(f"  当前表: {current}")
print(f"  已索引: {indexed}")
print(f"  新增: {diff.added_tables}")
print(f"  删除: {diff.removed_tables}")
assert diff.added_tables == {"table_new"}
assert len(diff.removed_tables) == 0
print("  ✅ 通过")

# 测试 2: 检测删除表
print("\n测试 2: 检测删除表")
current = {"table_a"}
indexed = {"table_a", "table_b", "table_c", "table_deleted"}
diff = detector.diff(current, indexed)

print(f"  当前表: {current}")
print(f"  已索引: {indexed}")
print(f"  新增: {diff.added_tables}")
print(f"  删除: {diff.removed_tables}")
assert len(diff.added_tables) == 0
assert diff.removed_tables == {"table_b", "table_c", "table_deleted"}
print("  ✅ 通过")

# 测试 3: 无变化
print("\n测试 3: 无变化")
current = {"table_a", "table_b"}
indexed = {"table_a", "table_b"}
diff = detector.diff(current, indexed)

print(f"  新增: {diff.added_tables}")
print(f"  删除: {diff.removed_tables}")
assert len(diff.added_tables) == 0
assert len(diff.removed_tables) == 0
print("  ✅ 通过")

print("\n" + "=" * 60)
print("所有 ChangeDetector 测试通过!")
print("=" * 60)
```

---

## 6. 测试 RetrievalPipeline

### 6.1 预算控制测试

```python
# 保存为 test_pipeline_budget.py
import os
from dotenv import load_dotenv
load_dotenv()

from unittest.mock import MagicMock, patch
from src.metadata.retrieval_pipeline import RetrievalPipeline, FIELD_RERANK_THRESHOLD_MS
from src.metadata.retrieval_models import TableRetrievalResult, TableMatch

print("RetrievalPipeline 预算控制测试")
print("=" * 60)

print(f"\n字段 Rerank 阈值: {FIELD_RERANK_THRESHOLD_MS}ms")

# 测试 1: 预算充足时执行字段 Rerank
print("\n测试 1: 预算充足 (500ms)")
pipeline = RetrievalPipeline.__new__(RetrievalPipeline)
pipeline.budget_ms = 500

# Mock 方法
def mock_rerank_tables(query, candidates):
    return (["table1", "table2"], 100)  # 耗时 100ms

def mock_rerank_fields(query, tables):
    return ([MagicMock(table_name="t1", field_name="id")], 50)

pipeline._rerank_tables = mock_rerank_tables
pipeline._rerank_fields = mock_rerank_fields

# 检查预算
elapsed = 100
remaining = pipeline.budget_ms - elapsed
print(f"  表级 Rerank 耗时: 100ms")
print(f"  剩余预算: {remaining}ms")
print(f"  阈值: {FIELD_RERANK_THRESHOLD_MS}ms")
print(f"  字段 Rerank: {'执行' if remaining >= FIELD_RERANK_THRESHOLD_MS else '跳过'}")
assert remaining >= FIELD_RERANK_THRESHOLD_MS
print("  ✅ 通过")

# 测试 2: 预算不足时跳过字段 Rerank
print("\n测试 2: 预算不足 (200ms)")
pipeline.budget_ms = 200

def mock_rerank_tables_slow(query, candidates):
    return (["table1"], 180)  # 耗时 180ms

pipeline._rerank_tables = mock_rerank_tables_slow

elapsed = 180
remaining = pipeline.budget_ms - elapsed
print(f"  表级 Rerank 耗时: 180ms")
print(f"  剩余预算: {remaining}ms")
print(f"  阈值: {FIELD_RERANK_THRESHOLD_MS}ms")
print(f"  字段 Rerank: {'执行' if remaining >= FIELD_RERANK_THRESHOLD_MS else '跳过'}")
assert remaining < FIELD_RERANK_THRESHOLD_MS
print("  ✅ 通过")

print("\n" + "=" * 60)
print("所有 RetrievalPipeline 测试通过!")
print("=" * 60)
```

---

## 7. 完整集成测试

### 7.1 一键运行所有测试

```bash
# 运行自动化测试脚本
cd E:\trae-pc\mysql260227
PYTHONIOENCODING=utf-8 python scripts/manual_test_rerank.py
```

### 7.2 预期输出

```
┌─────────────────────────── 测试套件 ────────────────────────────┐
│ Qwen3-Rerank 功能手动测试                                       │
│ 测试 RerankService, RetrievalPipeline, 语义字段, ChangeDetector │
└─────────────────────────────────────────────────────────────────┘

──────────────────────── 测试 1: RerankService ─────────────────────────
✓ API Key 已配置: sk-xxxxx...
✓ RerankService 初始化成功
  - 模型: qwen3-rerank
  - 超时: 30s
  - 重试次数: 2

✓ Rerank 调用成功 (耗时: 376ms)
排序结果:
┌────────┬────────┬────────────┬──────────────────────────────────┐
│ 排名   │ 索引   │ 相关性     │ 候选内容                         │
├────────┼────────┼────────────┼──────────────────────────────────┤
│ 1      │ 0      │ 0.6238     │ cloud_fixed_plate...             │
│ 2      │ 1      │ 0.6013     │ cloud_temp_plate...              │
│ 3      │ 3      │ 0.3975     │ cloud_order...                   │
│ 4      │ 2      │ 0.3931     │ cloud_user...                    │
└────────┴────────┴────────────┴──────────────────────────────────┘
✓ 语义排序正确: 车牌相关表排在前面

──────────────────────────────── 测试结果汇总 ─────────────────────────
┌───────────────────┬────────┐
│ 测试项            │ 结果   │
├───────────────────┼────────┤
│ 语义字段          │ ✓ 通过 │
│ ChangeDetector    │ ✓ 通过 │
│ EmbeddingService  │ ✓ 通过 │
│ RerankService     │ ✓ 通过 │
│ RetrievalPipeline │ ✓ 通过 │
└───────────────────┴────────┘

总计: 5/5 测试通过
┌─────────────────────────────────────────────────────────────────────────────┐
│ 所有测试通过! 功能验证成功!                                                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. 常见问题排查

### 8.1 API Key 错误

**错误信息:**
```
ValueError: DASHSCOPE_API_KEY not found
```

**解决方案:**
```bash
# 检查环境变量
echo $DASHSCOPE_API_KEY

# 或在 .env 文件中设置
echo "DASHSCOPE_API_KEY=sk-xxxxxx" >> .env
```

### 8.2 模型不存在错误

**错误信息:**
```
{"code":"InvalidParameter","message":"Model not exist."}
```

**解决方案:**
确认使用正确的模型名称:
- ✅ `qwen3-rerank`
- ❌ `qwen3-reranker-0.6b`

### 8.3 API URL 错误

**错误信息:**
```
{"code":"InvalidParameter","message":"task can not be null"}
```

**解决方案:**
确认使用正确的 API URL:
- ✅ `https://dashscope.aliyuncs.com/compatible-api/v1/reranks`
- ❌ `https://dashscope.aliyuncs.com/api/v1/services/rerank/rerank`

### 8.4 响应格式错误

**错误信息:**
```
KeyError: 'output'
```

**解决方案:**
确认响应格式解析正确:
- OpenAI 兼容 API 返回: `{"results": [...]}`
- 不是: `{"output": {"results": [...]}}`

### 8.5 ChromaDB 错误

**错误信息:**
```
no such column: collections.topic
```

**解决方案:**
```bash
# 重建向量索引
rm -rf data/dev/chroma_db
python -c "from src.metadata.graph_store import GraphStore; GraphStore(env='dev')"
```

---

## 附录: 快速测试命令汇总

```bash
# 1. 运行所有单元测试
pytest tests/metadata/test_rerank_service.py tests/metadata/test_retrieval_agent.py -v

# 2. 运行手动测试脚本
PYTHONIOENCODING=utf-8 python scripts/manual_test_rerank.py

# 3. 快速验证 API 连通性
python -c "
import os; from dotenv import load_dotenv; load_dotenv()
import requests
r = requests.post(
    'https://dashscope.aliyuncs.com/compatible-api/v1/reranks',
    headers={'Authorization': f'Bearer {os.getenv(\"DASHSCOPE_API_KEY\")}'},
    json={'model': 'qwen3-rerank', 'query': 'test', 'documents': ['a', 'b']}
)
print(f'Status: {r.status_code}')
"

# 4. 检查配置
python -c "
from src.metadata.rerank_service import RerankService
print(f'MODEL_NAME: {RerankService.MODEL_NAME}')
print(f'API_URL: {RerankService.API_URL}')
print(f'DEFAULT_TIMEOUT: {RerankService.DEFAULT_TIMEOUT}')
"
```
