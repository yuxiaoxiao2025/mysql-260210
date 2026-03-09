"""Query Rewriter for enhancing queries with context."""
import re


class QueryRewriter:
    """Rewrites queries by substituting pronouns with context values."""

    # Pronouns that refer to previously mentioned entities
    PRONOUN_PATTERNS = [
        (re.compile(r"这辆车"), "plate"),
        (re.compile(r"这台车"), "plate"),
        (re.compile(r"那辆车"), "plate"),
        (re.compile(r"那台车"), "plate"),
        (re.compile(r"它"), "plate"),
        (re.compile(r"该车"), "plate"),
    ]

    def rewrite(self, query: str, context: dict[str, str]) -> str:
        """Rewrite a query using context to replace pronouns.

        Args:
            query: The original natural language query.
            context: Dictionary containing context values (e.g., {"plate": "沪A12345"}).

        Returns:
            The rewritten query with pronouns replaced by context values.
        """
        if not context:
            return query

        result = query

        for pattern, slot_key in self.PRONOUN_PATTERNS:
            if slot_key in context:
                value = context[slot_key]
                result = pattern.sub(value, result)

        return result
