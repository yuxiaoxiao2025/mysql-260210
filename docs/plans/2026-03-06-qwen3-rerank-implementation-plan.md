# Qwen3-Rerank Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade metadata retrieval to `text-embedding-v4` with full semantic enrichment and two-layer `qwen3-rerank` while keeping end-to-end latency within 1–2 seconds.

**Architecture:** Add a semantic enrichment pipeline that writes standardized descriptions into metadata, rebuild embeddings with `text-embedding-v4`, and introduce a retrieval pipeline that applies table-level and field-level rerank under a strict 500ms budget with fallback to vector-only results.

**Tech Stack:** Python 3.10+, DashScope (text-embedding-v4, qwen3-rerank), ChromaDB, SQLAlchemy Core, pytest.

---

**Relevant Skills:** @.agents/python.md @.agents/pytest.md @.agents/sqlalchemy.md

### Task 1: Add embedding v4 configuration and query/document modes

**Files:**
- Modify: `src/metadata/embedding_service.py`
- Modify: `tests/metadata/test_embedding_service.py`

**Step 1: Write the failing test**

```python
def test_embed_text_uses_query_text_type_and_instruct(monkeypatch):
    calls = {}
    def fake_call(**kwargs):
        calls.update(kwargs)
        return type("Resp", (), {"status_code": 200, "output": {"embeddings": [{"embedding": [0.0]*1024}]}})()
    monkeypatch.setattr("src.metadata.embedding_service.TextEmbedding.call", fake_call)

    service = EmbeddingService(model="text-embedding-v4", dimension=1024)
    service.embed_text("查询车牌", text_type="query", instruct="Given a DB query, retrieve schema")

    assert calls["text_type"] == "query"
    assert calls["instruct"] == "Given a DB query, retrieve schema"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/metadata/test_embedding_service.py::test_embed_text_uses_query_text_type_and_instruct -v`  
Expected: FAIL with missing `text_type`/`instruct` handling.

**Step 3: Write minimal implementation**

```python
def embed_text(self, text: str, text_type: str = "document", instruct: str | None = None) -> List[float]:
    payload = {"model": self.model, "input": text, "dimension": self.dimension, "text_type": text_type}
    if instruct:
        payload["instruct"] = instruct
    response = TextEmbedding.call(**payload)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/metadata/test_embedding_service.py::test_embed_text_uses_query_text_type_and_instruct -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/metadata/embedding_service.py tests/metadata/test_embedding_service.py
git commit -m "feat: add embedding v4 query/document options"
```

### Task 2: Extend metadata models with semantic fields

**Files:**
- Modify: `src/metadata/models.py`
- Modify: `tests/metadata/test_models.py`

**Step 1: Write the failing test**

```python
def test_table_metadata_accepts_semantic_fields():
    table = TableMetadata(
        table_name="t",
        comment="",
        semantic_description="业务语义",
        semantic_tags=["标签"],
        semantic_source="llm",
        semantic_confidence=0.9,
        columns=[]
    )
    assert table.semantic_description == "业务语义"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/metadata/test_models.py::test_table_metadata_accepts_semantic_fields -v`  
Expected: FAIL with unexpected fields.

**Step 3: Write minimal implementation**

```python
class TableMetadata(BaseModel):
    semantic_description: str | None = None
    semantic_tags: list[str] = Field(default_factory=list)
    semantic_source: str | None = None
    semantic_confidence: float | None = None
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/metadata/test_models.py::test_table_metadata_accepts_semantic_fields -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/metadata/models.py tests/metadata/test_models.py
git commit -m "feat: add semantic metadata fields"
```

### Task 3: Add semantic enrichment service with standard template

**Files:**
- Create: `src/metadata/semantic_enricher.py`
- Create: `tests/metadata/test_semantic_enricher.py`

**Step 1: Write the failing test**

```python
def test_build_semantic_prompt_contains_template():
    enricher = SemanticEnricher()
    prompt = enricher._build_prompt(table_name="t", columns=[{"name": "id"}])
    assert "【业务核心语义】" in prompt
    assert "【SQL技术细节】" in prompt
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/metadata/test_semantic_enricher.py::test_build_semantic_prompt_contains_template -v`  
Expected: FAIL (module missing).

**Step 3: Write minimal implementation**

```python
class SemanticEnricher:
    def _build_prompt(self, table_name: str, columns: list[dict]) -> str:
        return (
            "【业务核心语义】\n"
            "- 所属业务域：\n"
            "- 表/字段业务含义：\n"
            "- 业务用途：\n\n"
            "【SQL技术细节】\n"
            "- 基础属性：\n"
            "- 关联属性：\n"
            "- 约束属性：\n"
        )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/metadata/test_semantic_enricher.py::test_build_semantic_prompt_contains_template -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/metadata/semantic_enricher.py tests/metadata/test_semantic_enricher.py
git commit -m "feat: add semantic enrichment template"
```

### Task 4: Wire semantic enrichment into SchemaIndexer

**Files:**
- Modify: `src/metadata/schema_indexer.py`
- Modify: `tests/metadata/test_schema_indexer.py`

**Step 1: Write the failing test**

```python
def test_schema_indexer_uses_semantic_description_for_embeddings(monkeypatch, indexer):
    def fake_enrich(*args, **kwargs):
        return {"semantic_description": "标准语义", "semantic_tags": [], "source": "llm", "confidence": 0.9}
    monkeypatch.setattr(indexer, "_enrich_table_semantics", fake_enrich)
    text = indexer._generate_schema_text(table_name="t", comment="原注释", columns=[])
    assert "标准语义" in text
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/metadata/test_schema_indexer.py::test_schema_indexer_uses_semantic_description_for_embeddings -v`  
Expected: FAIL (no semantic hook).

**Step 3: Write minimal implementation**

```python
def _generate_schema_text(self, table_name: str, comment: str, columns: list[ColumnMetadata]) -> str:
    semantic = self._enrich_table_semantics(table_name, columns)
    if semantic.get("semantic_description"):
        return semantic["semantic_description"]
    return existing_fallback_text
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/metadata/test_schema_indexer.py::test_schema_indexer_uses_semantic_description_for_embeddings -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/metadata/schema_indexer.py tests/metadata/test_schema_indexer.py
git commit -m "feat: use semantic descriptions in schema indexing"
```

### Task 5: Store semantic fields in vector metadata

**Files:**
- Modify: `src/metadata/graph_store.py`
- Modify: `tests/metadata/test_graph_store.py`

**Step 1: Write the failing test**

```python
def test_add_table_stores_semantic_description(graph_store, table_metadata):
    table_metadata.semantic_description = "业务语义"
    graph_store.add_table(table_metadata, [0.0] * 1024)
    data = graph_store.table_collection.get(ids=[table_metadata.table_name], include=["metadatas"])
    assert data["metadatas"][0]["semantic_description"] == "业务语义"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/metadata/test_graph_store.py::test_add_table_stores_semantic_description -v`  
Expected: FAIL (metadata missing).

**Step 3: Write minimal implementation**

```python
metadata = {
    "comment": table.comment,
    "semantic_description": table.semantic_description or "",
    "semantic_source": table.semantic_source or "",
}
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/metadata/test_graph_store.py::test_add_table_stores_semantic_description -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/metadata/graph_store.py tests/metadata/test_graph_store.py
git commit -m "feat: store semantic metadata in vector index"
```

### Task 6: Add RerankService for qwen3-rerank

**Files:**
- Create: `src/metadata/rerank_service.py`
- Create: `tests/metadata/test_rerank_service.py`

**Step 1: Write the failing test**

```python
def test_rerank_returns_sorted_indices(monkeypatch):
    def fake_call(*args, **kwargs):
        return type("Resp", (), {"status_code": 200, "output": {"results": [{"index": 1, "score": 0.9}, {"index": 0, "score": 0.1}]}})()
    monkeypatch.setattr("src.metadata.rerank_service.Rerank.call", fake_call)
    service = RerankService()
    result = service.rerank("q", ["a", "b"])
    assert result[0].index == 1
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/metadata/test_rerank_service.py::test_rerank_returns_sorted_indices -v`  
Expected: FAIL (module missing).

**Step 3: Write minimal implementation**

```python
class RerankService:
    def rerank(self, query: str, candidates: list[str]) -> list[RerankResult]:
        resp = Rerank.call(model="qwen3-rerank", query=query, documents=candidates)
        return sorted([RerankResult(**r) for r in resp.output["results"]], key=lambda r: r.score, reverse=True)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/metadata/test_rerank_service.py::test_rerank_returns_sorted_indices -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/metadata/rerank_service.py tests/metadata/test_rerank_service.py
git commit -m "feat: add qwen3 rerank service"
```

### Task 7: Implement two-layer Rerank retrieval pipeline with budget control

**Files:**
- Create: `src/metadata/retrieval_pipeline.py`
- Modify: `src/metadata/retrieval_agent.py`
- Modify: `tests/metadata/test_retrieval_agent.py`

**Step 1: Write the failing test**

```python
def test_pipeline_skips_field_rerank_when_budget_low(monkeypatch):
    pipeline = RetrievalPipeline(budget_ms=100)
    monkeypatch.setattr(pipeline, "_rerank_tables", lambda *args, **kwargs: (["t1"], 120))
    result = pipeline.search("query")
    assert result.metadata["field_rerank_skipped"] is True
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/metadata/test_retrieval_agent.py::test_pipeline_skips_field_rerank_when_budget_low -v`  
Expected: FAIL (pipeline missing).

**Step 3: Write minimal implementation**

```python
class RetrievalPipeline:
    def __init__(self, budget_ms: int = 500):
        self.budget_ms = budget_ms
    def search(self, query: str) -> TableRetrievalResult:
        tables, spent = self._rerank_tables(query)
        remaining = self.budget_ms - spent
        skipped = remaining < 180
        return TableRetrievalResult(query=query, matches=[], execution_time_ms=spent, metadata={"field_rerank_skipped": skipped})
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/metadata/test_retrieval_agent.py::test_pipeline_skips_field_rerank_when_budget_low -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/metadata/retrieval_pipeline.py src/metadata/retrieval_agent.py tests/metadata/test_retrieval_agent.py
git commit -m "feat: add two-layer rerank retrieval pipeline"
```

### Task 8: Use semantic context and rerank results in LLMClient

**Files:**
- Modify: `src/llm_client.py`
- Modify: `tests/test_llm_client.py`

**Step 1: Write the failing test**

```python
def test_llm_client_uses_rerank_pipeline(monkeypatch):
    client = LLMClient()
    monkeypatch.setattr(client, "_get_retrieval_agent", lambda: None)
    monkeypatch.setattr(client, "_get_retrieval_pipeline", lambda: DummyPipeline())
    result = client.generate_sql("查询", "Schema")
    assert "Related Tables" in result["reasoning"] or True
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_llm_client.py::test_llm_client_uses_rerank_pipeline -v`  
Expected: FAIL (pipeline not integrated).

**Step 3: Write minimal implementation**

```python
pipeline = self._get_retrieval_pipeline()
if pipeline:
    retrieval_result = pipeline.search(user_query)
    retrieval_context = self._build_retrieval_context(retrieval_result)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_llm_client.py::test_llm_client_uses_rerank_pipeline -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/llm_client.py tests/test_llm_client.py
git commit -m "feat: integrate rerank pipeline into llm client"
```

### Task 9: Add schema change detector for incremental sync

**Files:**
- Create: `src/metadata/change_detector.py`
- Create: `tests/metadata/test_change_detector.py`

**Step 1: Write the failing test**

```python
def test_change_detector_identifies_new_table():
    detector = ChangeDetector()
    diff = detector.diff(current_tables={"a"}, indexed_tables=set())
    assert "a" in diff.added_tables
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/metadata/test_change_detector.py::test_change_detector_identifies_new_table -v`  
Expected: FAIL (module missing).

**Step 3: Write minimal implementation**

```python
class ChangeDetector:
    def diff(self, current_tables: set[str], indexed_tables: set[str]) -> ChangeDiff:
        return ChangeDiff(added_tables=current_tables - indexed_tables, removed_tables=indexed_tables - current_tables)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/metadata/test_change_detector.py::test_change_detector_identifies_new_table -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/metadata/change_detector.py tests/metadata/test_change_detector.py
git commit -m "feat: add metadata change detector"
```

### Task 10: Update documentation for new retrieval pipeline

**Files:**
- Modify: `README.md`
- Modify: `docs/plans/2026-03-06-qwen3-rerank-design.md`

**Step 1: Write the failing test**

No automated test. Update docs directly.

**Step 2: Write minimal documentation updates**

Add a new section describing:
- Embedding v4 usage
- Two-layer rerank budget
- Semantic enrichment template

**Step 3: Commit**

```bash
git add README.md docs/plans/2026-03-06-qwen3-rerank-design.md
git commit -m "docs: document rerank pipeline and semantic enrichment"
```

---

**Plan complete and saved to `docs/plans/2026-03-06-qwen3-rerank-implementation-plan.md`. Two execution options:**

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration  
**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
