# 漕河泾停车云数据导出工具

> 基于 SQLAlchemy 和 MySQL 的智能数据管理工具，支持自然语言交互和业务操作

## Project Overview

This is a full-stack application for parking cloud data management with AI-powered natural language processing. It provides both CLI and web interfaces for database operations, with intelligent intent recognition for business-specific operations.

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Backend** | Python 3.8+, FastAPI, SQLAlchemy Core, PyMySQL |
| **Frontend** | React 18, TypeScript, Vite, Ant Design |
| **Database** | MySQL 5.7+ / 8.0+ |
| **AI/LLM** | dashscope (通义千问/Qwen) |
| **Testing** | pytest (target: 80%+ coverage) |
| **Data Processing** | pandas, openpyxl, XlsxWriter |

## Project Structure

```
mysql260227/
├── src/                          # Backend source code
│   ├── api/                      # FastAPI routes and models
│   │   ├── routes/              # API endpoints (query, mutation, schema)
│   │   ├── deps.py              # Dependency injection
│   │   └── models.py            # Request/response models
│   ├── cache/                    # Schema caching layer
│   ├── config.py                 # Configuration management
│   ├── db_manager.py             # Database operations (SQLAlchemy Core)
│   ├── executor/                 # Operation execution engine
│   ├── handlers/                 # Error handling utilities
│   ├── intent/                   # Intent recognition system
│   ├── knowledge/                # Business knowledge base loader
│   ├── learner/                  # Preference learning system
│   ├── llm_client.py             # LLM API client (dashscope)
│   ├── matcher/                  # Table/query matching
│   ├── monitoring/               # Metrics collection and alerting
│   ├── preview/                  # Diff rendering for mutations
│   ├── exporter.py               # Excel export functionality
│   ├── schema_loader.py          # Database schema introspection
│   ├── sql_safety.py             # SQL validation and safety checks
│   └── txn_preview.py            # Transaction preview utilities
├── frontend/                     # React frontend
│   ├── src/                     # TypeScript source
│   ├── package.json             # npm dependencies
│   └── vite.config.ts           # Vite configuration
├── tests/                        # Test files (pytest)
├── docs/                         # Project documentation
├── scripts/                      # Utility scripts
├── data/                         # Data files (knowledge base, etc.)
├── main.py                       # CLI entry point
├── requirements.txt              # Python dependencies
└── pytest.ini                    # pytest configuration
```

## Development Setup

### Prerequisites

- Python 3.8+
- Node.js 18+ (for frontend)
- MySQL 5.7+ or 8.0+

### Backend Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Edit .env with your database credentials

# Run tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Start CLI interface
python main.py

# Start API server
uvicorn src.api.routes.query:app --reload
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Development server
npm run dev

# Build for production
npm run build
```

### Environment Variables

```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=parkcloud
DASHSCOPE_API_KEY=your_api_key
```

## Architecture

### Backend Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       Entry Points                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │   CLI        │  │  FastAPI     │  │   Web Frontend   │  │
│  │  (main.py)   │  │  Routes      │  │   (React)        │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Intent Recognition                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │   Intent     │  │  Knowledge   │  │   LLM Client     │  │
│  │  Recognizer  │──│   Loader     │──│   (dashscope)    │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Operation Execution                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │   Operation  │  │   Schema     │  │   SQL Safety     │  │
│  │   Executor   │──│   Loader     │──│   Validator      │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Data Layer                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │   Database   │  │   Schema     │  │   Excel          │  │
│  │   Manager    │──│   Cache      │──│   Exporter       │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Key Components

| Component | Purpose | File |
|-----------|---------|------|
| **DatabaseManager** | SQLAlchemy Core database operations | `src/db_manager.py` |
| **LLMClient** | Natural language to SQL conversion | `src/llm_client.py` |
| **IntentRecognizer** | Business intent detection | `src/intent/intent_recognizer.py` |
| **KnowledgeLoader** | Operation templates loading | `src/knowledge/knowledge_loader.py` |
| **OperationExecutor** | Execute business operations | `src/executor/operation_executor.py` |
| **SchemaLoader** | Database schema introspection | `src/schema_loader.py` |
| **SQLSafety** | SQL injection prevention | `src/sql_safety.py` |
| **ExcelExporter** | Export query results to Excel | `src/exporter.py` |
| **MetricsCollector** | Performance monitoring | `src/monitoring/metrics_collector.py` |
| **AlertManager** | System alerting | `src/monitoring/alert_manager.py` |

## Coding Standards

### Python (PEP 8 + Project Rules)

This project follows strict coding standards defined in `AGENTS.md`. Key rules:

#### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Variables, functions, methods | `snake_case` | `get_all_tables()` |
| Classes, exceptions | `CapWords` | `DatabaseManager` |
| Constants | `ALL_CAPS` | `MAX_RETRY_COUNT` |
| Protected methods | `_leading_underscore` | `_validate_connection()` |
| Private methods | `__double_underscore` | `__parse_result()` |

#### Import Order

```python
# 1. Standard library
import os
import sys
from pathlib import Path

# 2. Third-party packages
import pandas as pd
from sqlalchemy import create_engine

# 3. Local modules
from src.config import get_db_url
from src.db_manager import DatabaseManager
```

#### Code Quality Requirements

- **Type hints**: Required for all function signatures
- **Line length**: 88 characters (black default)
- **String formatting**: f-strings preferred
- **Path handling**: Use `pathlib.Path` instead of `os.path`
- **Data structures**: Prefer dataclasses or Pydantic models
- **Docstrings**: Google or NumPy style for public functions

### Prohibited Patterns

```python
# ❌ WRONG: Hardcoded credentials
db_password = "secret123"

# ❌ WRONG: Tab indentation
def bad():
	pass  # Tab used

# ❌ WRONG: Bare except
try:
    do_something()
except:  # Catches too much
    pass

# ❌ WRONG: Mutable default arguments
def func(items=[]):  # Dangerous!
    pass

# ❌ WRONG: Star imports
from module import *
```

### Required Patterns

```python
# ✅ CORRECT: Environment variables
import os
db_password = os.getenv('DB_PASSWORD')

# ✅ CORRECT: 4-space indentation
def good():
    pass  # 4 spaces

# ✅ CORRECT: Specific exceptions
try:
    do_something()
except ValueError as e:
    logger.error(f"Validation error: {e}")
    raise

# ✅ CORRECT: None as default
def func(items=None):
    items = items or []

# ✅ CORRECT: Explicit imports
from module import specific_function
```

### Database Operations

```python
# ✅ CORRECT: Parameterized queries
from sqlalchemy import text

query = text("SELECT * FROM users WHERE id = :user_id")
result = conn.execute(query, {"user_id": user_id})

# ✅ CORRECT: Context managers
with db.engine.connect() as conn:
    result = conn.execute(query)

# ❌ WRONG: String formatting (SQL injection risk)
query = f"SELECT * FROM users WHERE id = {user_id}"
```

### Testing Standards

```python
# Test file naming: test_*.py
# Test function naming: test_*

import pytest

class TestDatabaseManager:
    """Test cases for DatabaseManager."""

    @pytest.fixture
    def db(self):
        """Create test database connection."""
        return DatabaseManager()

    def test_get_all_tables_returns_list(self, db):
        """Test that get_all_tables returns a list."""
        # Arrange
        expected_type = list

        # Act
        tables = db.get_all_tables()

        # Assert
        assert isinstance(tables, expected_type)
        assert len(tables) > 0

    @pytest.mark.parametrize("table_name,expected", [
        ("cloud_fixed_plate", True),
        ("nonexistent_table", False),
    ])
    def test_table_exists(self, db, table_name, expected):
        """Test table existence check."""
        result = table_name in db.get_all_tables()
        assert result == expected
```

## Common Commands

| Task | Command |
|------|---------|
| Install dependencies | `pip install -r requirements.txt` |
| Run tests | `pytest` |
| Run tests (verbose) | `pytest -v` |
| Test coverage | `pytest --cov=src --cov-report=html` |
| Start CLI | `python main.py` |
| Start API server | `uvicorn src.api.routes.query:app --reload` |
| Format code | `black src/ tests/` |
| Sort imports | `isort src/ tests/` |
| Type check | `mypy src/` |
| Lint | `ruff check src/ tests/` |

## Business Operations

This tool supports intelligent business operations for parking management:

### Supported Operations

| Operation | Example Command |
|-----------|-----------------|
| Query plate | `查询车牌 沪ABC1234` |
| Distribute plate | `下发车牌 沪ABC1234 到 国际商务中心` |
| Batch distribute | `下发车牌 沪ABC1234 到 所有场库` |
| Update remarks | `更新车牌 沪ABC1234 的备注为 VIP客户` |
| Clear remarks | `把沪ABC1234的车辆备注删除掉` |
| Check expiring | `查看今天到期的车牌` |
| Query bindings | `查一下沪ABC1234都绑定了哪些场库` |

### Operation Templates

Operation templates are defined in `data/` directory as YAML files. Each template specifies:

- Operation ID and name
- Required and optional parameters
- SQL templates with parameter placeholders
- Enum sources for parameter validation

## Security Considerations

### SQL Injection Prevention

1. **All SQL must use parameterized queries**
2. **User input is validated before execution**
3. **Dangerous operations (DROP, TRUNCATE) are blocked**
4. **Mutation operations require confirmation**

### Credential Management

- **Never hardcode credentials** - use environment variables
- **Never commit `.env` files**
- **API keys must be in environment variables**

## Related Documentation

- [AGENTS.md](AGENTS.md) - Detailed coding standards and conventions
- [README.md](README.md) - User-facing documentation
- [docs/USER_GUIDE.md](docs/USER_GUIDE.md) - User operation manual
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) - Common issues and solutions
- [docs/API_REFERENCE.md](docs/API_REFERENCE.md) - API documentation
- [CONTRIBUTING.md](CONTRIBUTING.md) - Contribution guidelines