"""
Semantic enrichment utilities for metadata.

Provides a standard prompt template for table and field semantic enrichment.
"""

import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


class SemanticEnricher:
    """Build semantic enrichment prompts for table metadata."""

    def _build_prompt(self, table_name: str, columns: List[Dict]) -> str:
        """
        Build a semantic enrichment prompt for a table and its columns.

        Args:
            table_name: Name of the table to enrich.
            columns: List of column metadata dictionaries.

        Returns:
            Prompt string following the standard template.
        """
        logger.debug(
            "Building semantic prompt for table=%s with %d columns",
            table_name,
            len(columns),
        )
        return (
            "【业务核心语义】\n"
            "- 所属业务域：\n"
            "- 表/字段业务含义：\n"
            "- 业务用途：\n\n"
            "【SQL技术细节】\n"
            "- 基础属性：\n"
            "- 关联属性：\n"
            "- 约束属性：\n"
        )
