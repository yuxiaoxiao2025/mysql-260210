"""Tests for semantic enrichment prompt building."""

from src.metadata.semantic_enricher import SemanticEnricher


def test_build_semantic_prompt_contains_template():
    """Ensure semantic prompt contains standard template sections."""
    enricher = SemanticEnricher()
    prompt = enricher._build_prompt(table_name="t", columns=[{"name": "id"}])

    assert "【业务核心语义】" in prompt
    assert "【SQL技术细节】" in prompt
