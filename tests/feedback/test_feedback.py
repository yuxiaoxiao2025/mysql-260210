"""Tests for feedback parser and query logger."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from src.feedback.intent_parser import FeedbackParser, FeedbackIntent
from src.feedback.query_logger import QueryLogger


class TestFeedbackParser:
    """Test cases for FeedbackParser."""

    @pytest.fixture
    def parser(self):
        """Create a FeedbackParser instance."""
        return FeedbackParser()

    def test_parse_confirm_y(self, parser):
        """Test parsing 'y' as confirm."""
        intent = parser.parse("y")
        assert intent.type == "confirm"
        assert intent.content is None

    def test_parse_confirm_yes(self, parser):
        """Test parsing 'yes' as confirm."""
        intent = parser.parse("yes")
        assert intent.type == "confirm"
        assert intent.content is None

    def test_parse_confirm_uppercase(self, parser):
        """Test parsing uppercase 'Y' as confirm."""
        intent = parser.parse("Y")
        assert intent.type == "confirm"

    def test_parse_reject_n(self, parser):
        """Test parsing 'n' as reject."""
        intent = parser.parse("n")
        assert intent.type == "reject"
        assert intent.content is None

    def test_parse_reject_no(self, parser):
        """Test parsing 'no' as reject."""
        intent = parser.parse("no")
        assert intent.type == "reject"
        assert intent.content is None

    def test_parse_reject_uppercase(self, parser):
        """Test parsing uppercase 'N' as reject."""
        intent = parser.parse("N")
        assert intent.type == "reject"

    def test_parse_more(self, parser):
        """Test parsing 'more' as more."""
        intent = parser.parse("more")
        assert intent.type == "more"
        assert intent.content is None

    def test_parse_more_uppercase(self, parser):
        """Test parsing uppercase 'MORE' as more."""
        intent = parser.parse("MORE")
        assert intent.type == "more"

    def test_parse_correction(self, parser):
        """Test parsing correction text."""
        intent = parser.parse("不对，我要的是出场记录")
        assert intent.type == "correction"
        assert intent.content == "不对，我要的是出场记录"

    def test_parse_correction_with_prefix(self, parser):
        """Test parsing correction with common prefix."""
        intent = parser.parse("不对，查询沪A12345的入场记录")
        assert intent.type == "correction"
        assert "沪A12345" in intent.content

    def test_parse_empty_string(self, parser):
        """Test parsing empty string as correction."""
        intent = parser.parse("")
        assert intent.type == "correction"
        assert intent.content == ""

    def test_parse_whitespace(self, parser):
        """Test parsing whitespace-only string."""
        intent = parser.parse("   ")
        assert intent.type == "correction"
        assert intent.content == "   "

    def test_parse_with_whitespace(self, parser):
        """Test parsing feedback with surrounding whitespace."""
        intent = parser.parse("  y  ")
        assert intent.type == "confirm"

    def test_parse_none(self, parser):
        """Test parsing None as correction."""
        intent = parser.parse(None)
        assert intent.type == "correction"
        assert intent.content == ""


class TestQueryLogger:
    """Test cases for QueryLogger."""

    @pytest.fixture
    def temp_log_file(self):
        """Create a temporary log file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl', encoding='utf-8') as f:
            temp_path = f.name
        yield temp_path
        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)

    @pytest.fixture
    def logger(self, temp_log_file):
        """Create a QueryLogger instance with temp file."""
        return QueryLogger(log_file=temp_log_file)

    def test_log_creates_file(self, logger, temp_log_file):
        """Test that logging creates the log file."""
        feedback = FeedbackIntent(type="confirm")
        logger.log("查询车牌沪A12345", {"result": "test"}, feedback)

        assert os.path.exists(temp_log_file)

    def test_log_writes_valid_json(self, logger, temp_log_file):
        """Test that log writes valid JSON."""
        feedback = FeedbackIntent(type="confirm")
        logger.log("查询车牌沪A12345", {"result": "test"}, feedback)

        with open(temp_log_file, 'r', encoding='utf-8') as f:
            line = f.readline()
            record = json.loads(line)

        assert record["query"] == "查询车牌沪A12345"
        assert record["feedback_type"] == "confirm"

    def test_log_includes_timestamp(self, logger, temp_log_file):
        """Test that log includes timestamp."""
        feedback = FeedbackIntent(type="confirm")
        logger.log("test query", {}, feedback)

        with open(temp_log_file, 'r', encoding='utf-8') as f:
            record = json.loads(f.readline())

        assert "timestamp" in record
        assert isinstance(record["timestamp"], str)

    def test_log_multiple_entries(self, logger, temp_log_file):
        """Test logging multiple entries."""
        feedback1 = FeedbackIntent(type="confirm")
        feedback2 = FeedbackIntent(type="reject")

        logger.log("query1", {"r": 1}, feedback1)
        logger.log("query2", {"r": 2}, feedback2)

        with open(temp_log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        assert len(lines) == 2

        records = [json.loads(line) for line in lines]
        assert records[0]["query"] == "query1"
        assert records[1]["query"] == "query2"

    def test_log_with_correction_content(self, logger, temp_log_file):
        """Test logging correction with content."""
        feedback = FeedbackIntent(type="correction", content="我要出场记录")
        logger.log("查询入场", {"result": []}, feedback)

        with open(temp_log_file, 'r', encoding='utf-8') as f:
            record = json.loads(f.readline())

        assert record["feedback_type"] == "correction"
        assert record["feedback_content"] == "我要出场记录"

    def test_log_without_correction_content(self, logger, temp_log_file):
        """Test logging confirm without content."""
        feedback = FeedbackIntent(type="confirm")
        logger.log("查询", {}, feedback)

        with open(temp_log_file, 'r', encoding='utf-8') as f:
            record = json.loads(f.readline())

        assert record["feedback_type"] == "confirm"
        assert record.get("feedback_content") is None

    def test_default_log_file(self):
        """Test that default log file is used."""
        logger = QueryLogger()
        assert logger.log_file is not None
        assert isinstance(logger.log_file, (str, Path))

    def test_log_directory_creation(self):
        """Test that log directory is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "logs" / "feedback.jsonl"
            logger = QueryLogger(log_file=str(log_path))

            feedback = FeedbackIntent(type="confirm")
            logger.log("test", {}, feedback)

            assert log_path.exists()

    def test_get_logs_empty(self, temp_log_file):
        """Test getting logs from empty file."""
        logger = QueryLogger(log_file=temp_log_file)
        logs = logger.get_logs()
        assert logs == []

    def test_get_logs_with_entries(self, temp_log_file):
        """Test getting logs with entries."""
        logger = QueryLogger(log_file=temp_log_file)

        logger.log("query1", {"r": 1}, FeedbackIntent(type="confirm"))
        logger.log("query2", {"r": 2}, FeedbackIntent(type="reject"))
        logger.log("query3", {"r": 3}, FeedbackIntent(type="more"))

        logs = logger.get_logs()
        assert len(logs) == 3
        assert logs[0]["query"] == "query1"
        assert logs[1]["query"] == "query2"
        assert logs[2]["query"] == "query3"

    def test_get_logs_with_limit(self, temp_log_file):
        """Test getting logs with limit."""
        logger = QueryLogger(log_file=temp_log_file)

        logger.log("query1", {"r": 1}, FeedbackIntent(type="confirm"))
        logger.log("query2", {"r": 2}, FeedbackIntent(type="reject"))
        logger.log("query3", {"r": 3}, FeedbackIntent(type="more"))

        logs = logger.get_logs(limit=2)
        assert len(logs) == 2
        # Should return most recent
        assert logs[0]["query"] == "query2"
        assert logs[1]["query"] == "query3"

    def test_clear_logs(self, temp_log_file):
        """Test clearing logs."""
        logger = QueryLogger(log_file=temp_log_file)

        logger.log("query1", {"r": 1}, FeedbackIntent(type="confirm"))
        assert Path(temp_log_file).exists()

        logger.clear_logs()
        assert not Path(temp_log_file).exists()

    def test_clear_logs_nonexistent(self, temp_log_file):
        """Test clearing logs when file doesn't exist."""
        logger = QueryLogger(log_file=temp_log_file)
        # Should not raise
        logger.clear_logs()
        assert not Path(temp_log_file).exists()
