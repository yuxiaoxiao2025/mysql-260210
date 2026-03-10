"""
History Store for Knowledge Graph Explorer.

Provides JSON file-based storage for query history and session persistence.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class HistoryStore:
    """Manages query history storage using JSON file."""

    DEFAULT_HISTORY_FILE = "data/web/query_history.json"

    def __init__(self, history_file: Optional[str] = None):
        """Initialize HistoryStore.

        Args:
            history_file: Path to history JSON file (optional)
        """
        self.history_file = Path(history_file or self.DEFAULT_HISTORY_FILE)
        self.history_file.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> List[Dict[str, Any]]:
        """Load history from file.

        Returns:
            List of history entries
        """
        if not self.history_file.exists():
            return []

        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load history: {e}")
            return []

    def save(self, history: List[Dict[str, Any]]) -> bool:
        """Save history to file.

        Args:
            history: List of history entries to save

        Returns:
            True if successful
        """
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save history: {e}")
            return False

    def add_entry(
        self,
        query: str,
        selected_tables: List[str],
        generated_sql: Optional[str] = None
    ) -> bool:
        """Add a new history entry.

        Args:
            query: User query text
            selected_tables: List of selected table names
            generated_sql: Generated SQL (optional)

        Returns:
            True if successful
        """
        history = self.load()

        entry = {
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "selected_tables": selected_tables,
            "generated_sql": generated_sql,
        }

        history.append(entry)

        # Keep only last 100 entries
        history = history[-100:]

        return self.save(history)

    def get_latest(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get latest history entries.

        Args:
            limit: Number of entries to return

        Returns:
            List of history entries
        """
        history = self.load()
        return history[-limit:][::-1]

    def clear(self) -> bool:
        """Clear all history.

        Returns:
            True if successful
        """
        return self.save([])

    def restore_session(self, timestamp: str) -> Optional[Dict[str, Any]]:
        """Restore a specific session by timestamp.

        Args:
            timestamp: ISO timestamp of session to restore

        Returns:
            Session data or None if not found
        """
        history = self.load()

        for entry in history:
            if entry.get("timestamp") == timestamp:
                return entry

        return None
