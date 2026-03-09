"""Feedback intent parser for user feedback on query results.

This module provides functionality to parse user feedback into structured
intent objects for the feedback loop system.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class FeedbackIntent:
    """Represents a parsed feedback intent.

    Attributes:
        type: The type of feedback. One of "confirm", "reject", "more", "correction".
        content: The raw feedback content for correction types, None for others.
    """

    type: str
    content: Optional[str] = None


class FeedbackParser:
    """Parser for user feedback on query results.

    Recognizes the following feedback types:
    - confirm: "y", "yes" (case-insensitive)
    - reject: "n", "no" (case-insensitive)
    - more: "more" (case-insensitive)
    - correction: Any other text

    Examples:
        >>> parser = FeedbackParser()
        >>> parser.parse("y")
        FeedbackIntent(type='confirm', content=None)
        >>> parser.parse("不对，我要出场记录")
        FeedbackIntent(type='correction', content='不对，我要出场记录')
    """

    # Feedback type mappings (normalized to lowercase)
    CONFIRM_KEYWORDS = {"y", "yes"}
    REJECT_KEYWORDS = {"n", "no"}
    MORE_KEYWORDS = {"more"}

    def parse(self, feedback: str) -> FeedbackIntent:
        """Parse user feedback into a FeedbackIntent.

        Args:
            feedback: The raw feedback string from the user.

        Returns:
            A FeedbackIntent object representing the parsed feedback.

        Examples:
            >>> parser = FeedbackParser()
            >>> parser.parse("y")
            FeedbackIntent(type='confirm', content=None)
            >>> parser.parse("Y")
            FeedbackIntent(type='confirm', content=None)
            >>> parser.parse("n")
            FeedbackIntent(type='reject', content=None)
            >>> parser.parse("no")
            FeedbackIntent(type='reject', content=None)
            >>> parser.parse("more")
            FeedbackIntent(type='more', content=None)
            >>> parser.parse("不对，我要出场记录")
            FeedbackIntent(type='correction', content='不对，我要出场记录')
        """
        if feedback is None:
            return FeedbackIntent(type="correction", content="")

        # Normalize: strip whitespace and convert to lowercase
        normalized = feedback.strip().lower()

        # Check for confirm
        if normalized in self.CONFIRM_KEYWORDS:
            return FeedbackIntent(type="confirm")

        # Check for reject
        if normalized in self.REJECT_KEYWORDS:
            return FeedbackIntent(type="reject")

        # Check for more
        if normalized in self.MORE_KEYWORDS:
            return FeedbackIntent(type="more")

        # Everything else is a correction
        return FeedbackIntent(type="correction", content=feedback)
