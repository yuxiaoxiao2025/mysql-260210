"""Tests for context enhancer components."""
import pytest

from src.context.slot_tracker import SlotTracker
from src.context.query_rewriter import QueryRewriter


class TestSlotTracker:
    """Test cases for SlotTracker."""

    def test_slot_tracker_extracts_plate(self):
        """Test that SlotTracker extracts plate number from query."""
        tracker = SlotTracker()
        slots = tracker.extract("查沪BAB1565的记录")
        assert slots.get("plate") == "沪BAB1565"

    def test_slot_tracker_extracts_plate_with_space(self):
        """Test plate extraction with spaces around it."""
        tracker = SlotTracker()
        slots = tracker.extract("查询 沪A12345 的停车记录")
        assert slots.get("plate") == "沪A12345"

    def test_slot_tracker_returns_empty_dict_when_no_plate(self):
        """Test that empty dict is returned when no plate found."""
        tracker = SlotTracker()
        slots = tracker.extract("查询所有记录")
        assert slots == {}

    def test_slot_tracker_extracts_multiple_plates(self):
        """Test extraction when multiple plates present (returns first)."""
        tracker = SlotTracker()
        slots = tracker.extract("比较沪A11111和沪B22222的记录")
        assert slots.get("plate") == "沪A11111"

    def test_slot_tracker_handles_plate_with_7_chars(self):
        """Test plate with 7 characters (new energy vehicles)."""
        tracker = SlotTracker()
        slots = tracker.extract("查询沪AD12345的充电记录")
        assert slots.get("plate") == "沪AD12345"


class TestQueryRewriter:
    """Test cases for QueryRewriter."""

    def test_rewrite_query_with_context(self):
        """Test rewriting query with context substitution."""
        rewriter = QueryRewriter()
        context = {"plate": "沪BAB1565"}
        new_query = rewriter.rewrite("这辆车3月出入过哪些园区", context)
        assert "沪BAB1565" in new_query
        assert "这辆车" not in new_query

    def test_rewrite_query_with_pronoun_it(self):
        """Test rewriting query with '它' pronoun."""
        rewriter = QueryRewriter()
        context = {"plate": "沪A12345"}
        new_query = rewriter.rewrite("它昨天停在哪里", context)
        assert "沪A12345" in new_query
        assert "它" not in new_query

    def test_rewrite_query_without_context(self):
        """Test that query is unchanged when no context provided."""
        rewriter = QueryRewriter()
        new_query = rewriter.rewrite("查询沪A12345的记录", {})
        assert new_query == "查询沪A12345的记录"

    def test_rewrite_query_with_empty_context(self):
        """Test that query is unchanged when context is empty."""
        rewriter = QueryRewriter()
        new_query = rewriter.rewrite("这辆车停在哪里", {})
        assert new_query == "这辆车停在哪里"

    def test_rewrite_query_with_multiple_pronouns(self):
        """Test rewriting query with multiple pronouns."""
        rewriter = QueryRewriter()
        context = {"plate": "沪BAB1565"}
        new_query = rewriter.rewrite("这辆车和它的记录", context)
        assert "沪BAB1565" in new_query
        assert "这辆车" not in new_query
        assert "它" not in new_query
