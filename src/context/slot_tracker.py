"""Slot Tracker for extracting entities from queries."""
import re


class SlotTracker:
    """Extracts slot values (like plate numbers) from natural language queries."""

    # Chinese license plate pattern:
    # - Province/city prefix: Chinese character (e.g., 沪, 京)
    # - Followed by: letter + 5-6 alphanumeric chars (6 or 7 total after prefix)
    # Chinese license plate pattern:
    # - Province/city prefix: Chinese character (e.g., 沪, 京)
    # - Followed by: letter + 5-6 alphanumeric chars (6 or 7 total after prefix)
    # - Total length: 7-8 characters (e.g., 沪A12345 or 沪AD12345)
    # - Uses lookahead for boundary since \b doesn't work well with Chinese chars
    PLATE_PATTERN = re.compile(r"[沪京津渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼][A-Za-z][A-Za-z0-9]{4,6}(?![A-Za-z0-9])")

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
