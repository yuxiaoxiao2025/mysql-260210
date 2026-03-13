# CLAUDE.md

## Commands
```bash
python main.py                          # Run CLI
pytest                                  # Run tests (70% coverage)
pytest tests/unit/test_x.py -v          # Specific test
black src/ tests/                       # Format code
streamlit run src/web/app.py            # Run web UI
```

## Architecture

**Agent Pipeline:** `IntentAgent → RetrievalAgent → KnowledgeAgent/SecurityAgent → PreviewAgent → ExecutionAgent`

**Orchestrator** (`src/agents/orchestrator.py`) coordinates agents:
- IntentAgent: Intent recognition (query/mutation/chat/qa)
- RetrievalAgent: Schema retrieval from vector store
- KnowledgeAgent: Q&A and chat responses
- SecurityAgent: SQL safety validation
- PreviewAgent: Mutation previews
- ExecutionAgent: Operation execution
- ReviewAgent: User confirmation (optional)

**Key Components:**
- `src/metadata/`: ChromaDB + qwen3-reranker retrieval pipeline
- `src/knowledge/business_knowledge.yaml`: Named SQL operations
- `src/memory/`: ConceptStore + ContextMemory

## Configuration (`.env`)
- `DASHSCOPE_API_KEY` - Qwen LLM API key
- `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` - MySQL
- `CHROMA_DB_PATH`, `TABLE_GRAPH_PATH` - Storage paths
- `USE_UNIFIED_REACT` - 是否启用统一 ReACT（`true/false`，默认 `false`）

## Notes
- Windows Git Bash: Use `encoding='utf-8'` for file I/O
- Git commits: Use Chinese messages
- `DialogueEngine` deprecated → use `Orchestrator`