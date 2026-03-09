"""Query and feedback logger for the feedback loop system.

This module provides functionality to log user queries, results, and feedback
for analysis and system improvement.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union

from src.feedback.intent_parser import FeedbackIntent


class QueryLogger:
    """Logger for queries and user feedback.

    Logs query-execution-feedback cycles to a JSONL file for later analysis.
    Each log entry includes timestamp, query, result summary, and feedback.

    Attributes:
        log_file: Path to the log file (JSONL format).

    Examples:
        >>> logger = QueryLogger("logs/feedback.jsonl")
        >>> feedback = FeedbackIntent(type="confirm")
        >>> logger.log("查询车牌沪A12345", {"rows": 5}, feedback)
    """

    DEFAULT_LOG_FILE = "logs/query_feedback.jsonl"

    def __init__(self, log_file: Optional[Union[str, Path]] = None) -> None:
        """Initialize the query logger.

        Args:
            log_file: Path to the log file. If None, uses DEFAULT_LOG_FILE.
        """
        self.log_file = Path(log_file) if log_file else Path(self.DEFAULT_LOG_FILE)

    def _ensure_directory(self) -> None:
        """Ensure the log directory exists."""
        parent_dir = self.log_file.parent
        if parent_dir and not parent_dir.exists():
            parent_dir.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        query: str,
        result: dict[str, Any],
        feedback: FeedbackIntent,
    ) -> None:
        """Log a query-feedback cycle.

        Args:
            query: The original user query.
            result: The query execution result (will be serialized to JSON).
            feedback: The parsed feedback intent.

        Examples:
            >>> logger = QueryLogger()
            >>> feedback = FeedbackIntent(type="correction", content="我要出场记录")
            >>> logger.log("查询入场记录", {"rows": []}, feedback)
        """
        self._ensure_directory()

        # Build log entry
        entry: dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "result": result,
            "feedback_type": feedback.type,
        }

        # Include content only for corrections
        if feedback.content is not None:
            entry["feedback_content"] = feedback.content

        # Append to log file
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def get_logs(self, limit: Optional[int] = None) -> list[dict[str, Any]]:
        """Retrieve logged entries.

        Args:
            limit: Maximum number of entries to return (most recent first).
                   If None, returns all entries.

        Returns:
            List of log entries.

        Examples:
            >>> logger = QueryLogger()
            >>> logs = logger.get_logs(limit=10)
        """
        if not self.log_file.exists():
            return []

        entries = []
        with open(self.log_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))

        # Return most recent first if limit specified
        if limit is not None:
            entries = entries[-limit:]

        return entries

    def clear_logs(self) -> None:
        """Clear all logs.

        Examples:
            >>> logger = QueryLogger()
            >>> logger.clear_logs()
        """
        if self.log_file.exists():
            self.log_file.unlink()
