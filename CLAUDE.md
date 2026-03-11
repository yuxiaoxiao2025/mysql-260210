# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Commands

```bash
python main.py                # Run CLI application
python main.py --agent-mode   # Run with Orchestrator mode
pytest                        # Run all tests (70% min coverage)
pytest tests/unit/test_x.py -v  # Run specific test
black src/ tests/             # Format code
```

## Architecture

**Multi-Agent Orchestration** (`src/agents/`):
IntentAgent → RetrievalAgent → KnowledgeAgent/SecurityAgent → PreviewAgent → ExecutionAgent

**Intelligent Retrieval** (`src/metadata/`):
Two-layer pipeline: ChromaDB vector recall → qwen3-reranker (500ms budget)

**Business Knowledge** (`src/knowledge/business_knowledge.yaml`):
Named operations with SQL templates, parameter validation, and multi-step mutations.

**Dialogue Engine** (`src/dialogue/`):
State machine for conversation + context memory for pronoun resolution.

## Key Patterns

```python
# Operation: preview-then-execute
exec_result = operation_executor.execute_operation(
    operation_id="plate_distribute", params=params, preview_only=True
)
# After user confirmation: preview_only=False, auto_commit=True

# LLM SQL generation
result = llm.generate_sql(user_query="...", schema_context=context)

# Context memory resolves pronouns
resolved = context_memory.resolve_reference("它的状态")  # → "沪ABC1234的状态"
```

## Configuration (`.env`)

Required: `DASHSCOPE_API_KEY`, `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`
Paths: `CHROMA_DB_PATH`, `TABLE_GRAPH_PATH`

## Notes

- Windows Git Bash: Always use `encoding='utf-8'`
- Git commits: Use Chinese messages
- Execute plan skill: Must pair with `subagent-driven-development`