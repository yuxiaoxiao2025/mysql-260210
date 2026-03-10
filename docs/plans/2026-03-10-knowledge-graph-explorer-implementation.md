# Knowledge Graph Explorer Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Streamlit-based interactive database explorer that uses Knowledge Graph visualization and LLM-powered Reranking to help users find tables and generate SQL.

**Architecture:**
- **Frontend**: Streamlit + streamlit-agraph (Visualization) + st-aggrid (Data Grid)
- **Backend Service**: `KnowledgeGraphService` (Graph Building), `RerankService` (Search & Rank)
- **State Management**: Streamlit Session State for history, selection, and graph context.

**Tech Stack:** Python 3.10, Streamlit, NetworkX, Pandas, DashScope (LLM/Embedding)

---

### Task 1: Streamlit App Skeleton & State Management

**Goal**: Create the app structure and robust session state management.

**Files:**
- Create: `src/web/app.py`
- Create: `src/web/state_manager.py`
- Create: `src/web/components/sidebar.py`

**Step 1: Create State Manager**
Define `StateManager` class to handle:
- `history`: List of past queries
- `selected_tables`: Set of currently selected table names
- `graph_data`: Current nodes and edges for rendering
- `search_results`: Current search results (before selection)

**Step 2: Create App Entry Point**
Create `src/web/app.py` that initializes `StateManager` and renders the basic layout (Sidebar, Main, Detail).

**Step 3: Implement Sidebar with History**
Implement `sidebar.py` to show:
- Text area for new query
- Selectbox for "Query History" (mock data first)

**Step 4: Verify**
Run `streamlit run src/web/app.py` and verify layout loads without errors.

---

### Task 2: Knowledge Graph Service (Backend)

**Goal**: Encapsulate graph building logic, reusing `SchemaIndexer`.

**Files:**
- Create: `src/web/services/graph_service.py`
- Test: `tests/web/test_graph_service.py`

**Step 1: Write Test**
Test `get_subgraph_for_tables(table_names)`:
- Input: `['parking_order']`
- Output: Nodes for `parking_order` + its neighbors; Edges connecting them.

**Step 2: Implement Service**
- Initialize with `SchemaIndexer`.
- Use `NetworkX` to build full graph from metadata.
- Implement `get_subgraph` logic: return ego_graph (radius=1) for selected nodes.

**Step 3: Verify**
Run pytest.

---

### Task 3: Visualization Component (Frontend)

**Goal**: Render the graph using `streamlit-agraph`.

**Files:**
- Create: `src/web/components/graph_view.py`
- Modify: `src/web/app.py`

**Step 1: Implement Graph View**
- Convert `NetworkX` graph to `agraph` Nodes/Edges.
- Color coding: Selected=Green, Top Ranked=Blue, Neighbors=Grey.
- Handle click events: update `session_state.selected_tables`.

**Step 2: Integrate**
Add `GraphView` to `app.py`.

---

### Task 4: Rerank Service (Search & Sort)

**Goal**: Implement the "Search + Rerank" logic.

**Files:**
- Create: `src/web/services/rerank_service.py`
- Test: `tests/web/test_rerank_service.py`

**Step 1: Write Test**
Test `search_and_rank(query)`:
- Mock EmbeddingService.
- Verify it returns list of `(table_name, score, reason)`.

**Step 2: Implement Service**
- **Recall**: `graph_store.search(query_embedding)` -> Top 50.
- **Rerank**:
  - Score = `0.7 * vector_sim + 0.3 * domain_match`.
  - (Optional) Call LLM for explanation: "Why is this table relevant?"

**Step 3: Verify**
Run pytest.

---

### Task 5: Data Preview & Combination (Detail View)

**Goal**: Show table details, data sampling, and multi-table preview.

**Files:**
- Create: `src/web/components/detail_panel.py`
- Modify: `src/db_manager.py` (ensure `sample_data` method exists)

**Step 1: Implement Single Table View**
- Show columns (with comments).
- `st.dataframe` showing `SELECT * FROM table LIMIT 5`.

**Step 2: Implement Multi-Table Combination**
- If >1 tables selected:
  - Use `NetworkX.shortest_path` to find join path.
  - Generate `SELECT ... FROM A JOIN B ON ... LIMIT 5`.
  - Execute and show result.

---

### Task 6: SQL Generation & Execution

**Goal**: Generate final SQL and allow natural language correction.

**Files:**
- Create: `src/web/services/sql_generator.py`
- Modify: `src/web/app.py`

**Step 1: Implement Generator**
- Prompt LLM with: User Query + Selected Tables Schema + Join Paths.
- Return SQL.

**Step 2: Execution UI**
- Show generated SQL.
- Button "Run Query".
- Show result grid.
- Input "Refine Query" -> Re-call LLM with history -> Update SQL.

---

### Task 7: History & Session Persistence

**Goal**: Save/Load user sessions.

**Files:**
- Modify: `src/web/state_manager.py`
- Create: `src/web/utils/history_store.py`

**Step 1: Implement History Store**
- Simple JSON file storage: `list of {timestamp, query, selected_tables}`.

**Step 2: Integrate Restore Logic**
- When sidebar history selected -> Load `selected_tables` -> Trigger Graph & SQL regeneration.

