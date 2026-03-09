"""Slot Tracker for extracting entities from queries."""
import re


class SlotTracker:
    """Extracts slot values (like plate numbers) from natural language queries."""

    # Chinese license plate pattern:
    # - Province/city prefix: Chinese character (e.g., 沪, 京)
    # - Followed by: letter + 5-6 alphanumeric chars (6 or 7 total after prefix)
    PLATE_PATTERN = re.compile(r"[沪京津渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼][A-Z][A-Z0-9]{5,6}")

    def extract(self, query: str) -> dict[str, str]:
        """Extract slot values from a query.

        Args:
            query: The natural language query string.

        Returns:
            Dictionary mapping slot names to extracted values.
            Currently supports "plate" for license plate numbers.
        """
        slots: dict[str, str] = {}

        # Extract plate number
        match = self.PLATE_PATTERN.search(query)
        if match:
            slots["plate"] = match.group(0)

        return slots
