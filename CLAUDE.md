# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Commands

```bash
python main.py                # Run CLI application
python main.py --agent-mode   # Run with Orchestrator mode (deprecated, use 'chat' command instead)
pytest                        # Run all tests (70% min coverage required)
pytest tests/unit/test_x.py -v  # Run specific test file
pytest -m unit                # Run only unit tests
pytest -m integration         # Run only integration tests
black src/ tests/             # Format code
streamlit run src/web/app.py  # Run web UI (Knowledge Graph Explorer)
```

## Architecture

### Multi-Agent Orchestration (`src/agents/`)

**Agent Pipeline:**
```
IntentAgent → RetrievalAgent → KnowledgeAgent/SecurityAgent → PreviewAgent → ExecutionAgent
```

**Orchestrator** (`orchestrator.py`) coordinates all agents:
- IntentAgent: Recognizes user intent (query/mutation/chat/qa)
- RetrievalAgent: Retrieves relevant schema from vector store
- KnowledgeAgent: Handles knowledge Q&A and chat
- SecurityAgent: Validates SQL safety
- PreviewAgent: Generates preview for mutations
- ExecutionAgent: Executes operations
- ReviewAgent: Provides user confirmation for dangerous operations

### Intelligent Retrieval (`src/metadata/`)

Two-layer pipeline with budget control:
1. **ChromaDB vector recall** - Initial candidate retrieval
2. **qwen3-reranker** - Relevance scoring (1000ms budget)

Key components:
- `retrieval_pipeline.py` - Main pipeline orchestrator
- `embedding_service.py` - Text embedding generation
- `rerank_service.py` - Reranking with qwen3-rerank
- `graph_store.py` - NetworkX-based schema knowledge graph
- `schema_indexer.py` - Incremental schema sync

### Business Knowledge (`src/knowledge/business_knowledge.yaml`)

Named operations with:
- SQL templates with parameter placeholders (`:param_name`)
- Parameter validation (regex patterns, enum sources)
- Multi-step mutations with `affects_rows` tracking
- Keyword matching for intent recognition

### Memory System (`src/memory/`)

- **ConceptStore**: Persistent concept learning (SQLite-backed)
- **ContextMemory**: Short-term context for pronoun resolution
- Enables the assistant to learn new business concepts from user interactions

### Dialogue System (`src/dialogue/`)

- **StartupWizard**: First-time setup assistant
- **ConceptRecognizer**: Identifies concepts in user input
- **QuestionGenerator**: Generates clarification questions

**Note:** `DialogueEngine` is deprecated. Use `Orchestrator` instead.

## Key Patterns

```python
# Operation: preview-then-execute pattern
exec_result = operation_executor.execute_operation(
    operation_id="plate_distribute", params=params, preview_only=True
)
# After user confirmation: preview_only=False, auto_commit=True

# LLM SQL generation with context
result = llm.generate_sql(
    user_query="查询车牌",
    schema_context=context,
    context=extracted_slots  # SlotTracker provides context
)

# Context memory resolves pronouns
resolved = context_memory.resolve_reference("它的状态")  # → "沪ABC1234的状态"

# Orchestrator processing with chat history
context = orchestrator.process(
    user_input,
    chat_history=[{"role": "user", "content": "..."}],
    user_confirmation=True  # After ReviewAgent confirmation
)
```

## Configuration (`.env`)

**Required:**
- `DASHSCOPE_API_KEY` - Qwen LLM API key
- `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` - MySQL connection

**Paths:**
- `CHROMA_DB_PATH` - Vector store location
- `TABLE_GRAPH_PATH` - Knowledge graph storage

**Budget Control** (`src/config.py`):
- `RERANK_BUDGET_MS = 1000` - Total rerank budget
- `FIELD_RERANK_THRESHOLD_MS = 180` - Field-level rerank threshold

## Test Structure

```
tests/
├── unit/           # Unit tests (fast, mocked dependencies)
│   └── agents/     # Agent-specific unit tests
├── integration/    # Integration tests (real DB connections)
└── dialogue/       # Dialogue system tests
```

Coverage requirements: 70% minimum (`--cov-fail-under=70` in pytest.ini)

## Notes

- Windows Git Bash: Always use `encoding='utf-8'` for file I/O
- Git commits: Use Chinese messages (per user preference)
- Execute plan skill: Must pair with `subagent-driven-development`
- DialogueEngine is deprecated: Use `Orchestrator` from `src.agents.orchestrator`