#!/usr/bin/env python
"""
Verify metadata knowledge graph system for Phase 1 acceptance.

This script performs a comprehensive check of:
1. Knowledge graph JSON persistence
2. ChromaDB vector storage
3. RetrievalAgent initialization and functionality

Usage:
    python scripts/verify_metadata_system.py
"""

import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def check_json_graph() -> dict:
    """Check if knowledge graph JSON exists and is valid."""
    result = {
        "name": "Knowledge Graph JSON",
        "status": "unknown",
        "message": "",
        "details": {},
    }

    json_path = Path("data/dev/table_graph.json")
    if not json_path.exists():
        result["status"] = "warning"
        result["message"] = f"JSON file not found: {json_path}"
        return result

    try:
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)

        table_count = len(data.get("tables", []))
        result["status"] = "success"
        result["message"] = f"Valid JSON with {table_count} tables"
        result["details"] = {
            "path": str(json_path),
            "table_count": table_count,
            "version": data.get("version", "unknown"),
            "updated_at": data.get("updated_at", "unknown"),
        }
    except json.JSONDecodeError as e:
        result["status"] = "error"
        result["message"] = f"Invalid JSON: {e}"
    except Exception as e:
        result["status"] = "error"
        result["message"] = f"Failed to read: {e}"

    return result


def check_chromadb() -> dict:
    """Check if ChromaDB has indexed vectors."""
    result = {
        "name": "ChromaDB Vector Storage",
        "status": "unknown",
        "message": "",
        "details": {},
    }

    try:
        from src.metadata.graph_store import GraphStore

        store = GraphStore(env="dev")
        table_count = store.get_table_count()
        field_count = store.get_field_count()

        if table_count > 0:
            result["status"] = "success"
            result["message"] = f"{table_count} tables, {field_count} fields indexed"
        else:
            result["status"] = "warning"
            result["message"] = "No tables indexed (run indexing first)"

        result["details"] = {
            "table_count": table_count,
            "field_count": field_count,
            "chroma_path": str(store.chroma_path),
        }
    except ImportError as e:
        result["status"] = "error"
        result["message"] = f"Import error: {e}"
    except Exception as e:
        result["status"] = "error"
        result["message"] = f"Failed to connect: {e}"

    return result


def check_retrieval_agent() -> dict:
    """Check if RetrievalAgent can be initialized and used."""
    result = {
        "name": "RetrievalAgent",
        "status": "unknown",
        "message": "",
        "details": {},
    }

    try:
        from src.metadata.retrieval_agent import RetrievalAgent
        from src.metadata.retrieval_models import RetrievalRequest, RetrievalLevel

        agent = RetrievalAgent(env="dev")

        if agent.graph is None:
            result["status"] = "warning"
            result["message"] = "Agent initialized but no graph loaded (run indexing)"
        else:
            result["status"] = "success"
            result["message"] = f"Agent ready with {len(agent.graph.tables)} tables"

        result["details"] = {
            "graph_loaded": agent.graph is not None,
            "table_count": agent.store.get_table_count(),
            "field_count": agent.store.get_field_count(),
        }
    except ImportError as e:
        result["status"] = "error"
        result["message"] = f"Import error: {e}"
    except Exception as e:
        result["status"] = "error"
        result["message"] = f"Failed to initialize: {e}"

    return result


def check_llm_integration() -> dict:
    """Check if LLMClient has retrieval integration."""
    result = {
        "name": "LLMClient Integration",
        "status": "unknown",
        "message": "",
        "details": {},
    }

    try:
        from src.llm_client import LLMClient

        client = LLMClient()

        # Check if retrieval_agent attribute exists
        has_retrieval_attr = hasattr(client, "retrieval_agent")
        has_get_retrieval = hasattr(client, "_get_retrieval_agent")
        has_build_context = hasattr(client, "_build_retrieval_context")

        if has_retrieval_attr and has_get_retrieval and has_build_context:
            result["status"] = "success"
            result["message"] = "LLMClient has retrieval integration methods"
        else:
            result["status"] = "warning"
            result["message"] = "LLMClient missing some retrieval methods"

        result["details"] = {
            "has_retrieval_agent_attr": has_retrieval_attr,
            "has_get_retrieval_agent": has_get_retrieval,
            "has_build_retrieval_context": has_build_context,
        }
    except ImportError as e:
        result["status"] = "error"
        result["message"] = f"Import error: {e}"
    except Exception as e:
        result["status"] = "error"
        result["message"] = f"Failed to check: {e}"

    return result


def print_header(title: str) -> None:
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)


def print_result(result: dict) -> None:
    """Print a formatted result."""
    status_icons = {
        "success": "[PASS]",
        "warning": "[WARN]",
        "error": "[FAIL]",
        "unknown": "[????]",
    }
    icon = status_icons.get(result["status"], "[????]")

    # Color codes for terminal
    colors = {
        "success": "\033[92m",  # Green
        "warning": "\033[93m",  # Yellow
        "error": "\033[91m",  # Red
        "unknown": "\033[90m",  # Gray
    }
    reset = "\033[0m"
    color = colors.get(result["status"], "")

    print(f"\n{color}{icon}{reset} {result['name']}")
    print(f"    {result['message']}")

    if result["details"]:
        for key, value in result["details"].items():
            print(f"    - {key}: {value}")


def main() -> int:
    """Run all verification checks and return exit code."""
    print_header("Metadata Knowledge Graph System Verification")

    print("\nRunning verification checks...\n")

    # Run all checks
    checks = [
        check_json_graph(),
        check_chromadb(),
        check_retrieval_agent(),
        check_llm_integration(),
    ]

    # Print results
    for check in checks:
        print_result(check)

    # Summary
    print_header("Summary")

    success_count = sum(1 for c in checks if c["status"] == "success")
    warning_count = sum(1 for c in checks if c["status"] == "warning")
    error_count = sum(1 for c in checks if c["status"] == "error")

    print(f"\n    Passed: {success_count}/{len(checks)}")
    print(f"    Warnings: {warning_count}")
    print(f"    Errors: {error_count}")

    # Recommendations
    if warning_count > 0 or error_count > 0:
        print("\n    Recommendations:")
        if any(c["status"] == "warning" and "No tables indexed" in c["message"] for c in checks):
            print("    - Run indexing: python -m src.metadata.schema_indexer")
        if any(c["status"] == "warning" and "no graph loaded" in c["message"] for c in checks):
            print("    - Build knowledge graph: python scripts/index_metadata.py")
        if any("JSON file not found" in c["message"] for c in checks):
            print("    - Initialize data directory and run indexing")

    print("\n" + "=" * 60)

    # Return exit code
    if error_count > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())