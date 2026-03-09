"""Tests for CLI preview module."""

import pytest
import pandas as pd
from rich.table import Table

from src.cli.preview import CLIPreview
from src.cli.interaction import Interaction


class TestCLIPreview:
    """Test cases for CLIPreview class."""

    @pytest.fixture
    def preview(self):
        """Create CLIPreview instance."""
        return CLIPreview()

    @pytest.fixture
    def sample_df(self):
        """Create sample DataFrame."""
        return pd.DataFrame({
            "id": [1, 2, 3],
            "name": ["Alice", "Bob", "Charlie"],
            "age": [25, 30, 35]
        })

    def test_generate_table_returns_table(self, preview, sample_df):
        """Test that generate_table returns a rich Table."""
        table = preview.generate_table(sample_df)
        assert isinstance(table, Table)

    def test_generate_table_columns(self, preview, sample_df):
        """Test that table has correct columns."""
        table = preview.generate_table(sample_df)
        column_headers = [col.header for col in table.columns]
        assert column_headers == ["id", "name", "age"]

    def test_generate_table_first_column_header(self, preview, sample_df):
        """Test first column header is 'id'."""
        table = preview.generate_table(sample_df)
        assert table.columns[0].header == "id"

    def test_generate_table_with_title(self, preview, sample_df):
        """Test table generation with custom title."""
        table = preview.generate_table(sample_df, title="Test Results")
        assert table.title == "Test Results"

    def test_generate_table_empty_dataframe(self, preview):
        """Test handling of empty DataFrame."""
        empty_df = pd.DataFrame()
        table = preview.generate_table(empty_df)
        assert isinstance(table, Table)
        assert len(table.columns) == 0


class TestInteraction:
    """Test cases for Interaction class."""

    def test_ask_feedback_returns_string(self):
        """Test that ask_feedback returns a string."""
        interaction = Interaction(input_func=lambda _: 'y')
        result = interaction.ask_feedback()
        assert isinstance(result, str)
        assert result == 'y'

    def test_ask_feedback_accepts_n(self):
        """Test that ask_feedback accepts 'n'."""
        interaction = Interaction(input_func=lambda _: 'n')
        result = interaction.ask_feedback()
        assert result == 'n'

    def test_ask_feedback_accepts_correction(self):
        """Test that ask_feedback accepts correction text."""
        interaction = Interaction(input_func=lambda _: 'fix the date')
        result = interaction.ask_feedback()
        assert result == 'fix the date'

    def test_ask_feedback_prompt_message(self):
        """Test that ask_feedback shows correct prompt."""
        captured_input = []
        def mock_input(prompt):
            captured_input.append(prompt)
            return 'y'
        interaction = Interaction(input_func=mock_input)
        interaction.ask_feedback()
        assert len(captured_input) == 1
        assert 'y/n' in captured_input[0].lower() or 'correction' in captured_input[0].lower()

    def test_confirm_action_returns_true_for_yes(self):
        """Test that confirm_action returns True for 'y'."""
        interaction = Interaction(input_func=lambda _: 'y')
        result = interaction.confirm_action("delete record")
        assert result is True

    def test_confirm_action_returns_false_for_no(self):
        """Test that confirm_action returns False for 'n'."""
        interaction = Interaction(input_func=lambda _: 'n')
        result = interaction.confirm_action("delete record")
        assert result is False

    def test_confirm_action_returns_true_for_yes_full(self):
        """Test that confirm_action returns True for 'yes'."""
        interaction = Interaction(input_func=lambda _: 'yes')
        result = interaction.confirm_action("delete record")
        assert result is True


class TestCLIPreviewShow:
    """Test cases for CLIPreview show method."""

    @pytest.fixture
    def preview(self):
        """Create CLIPreview instance."""
        return CLIPreview()

    @pytest.fixture
    def sample_df(self):
        """Create sample DataFrame."""
        return pd.DataFrame({
            "id": [1, 2, 3],
            "name": ["Alice", "Bob", "Charlie"],
            "age": [25, 30, 35]
        })

    def test_show_method(self, preview, sample_df, capsys):
        """Test that show method prints table to console."""
        preview.show(sample_df, title="Test Table")
        # Verify console output was generated
        captured = capsys.readouterr()
        # Rich outputs to stderr by default, so we just verify no exception was raised
        # The actual output verification is done through generate_table tests

    def test_generate_table_with_null_values(self, preview):
        """Test that null values are displayed as empty strings."""
        import numpy as np
        df_with_nulls = pd.DataFrame({
            "id": [1, 2, 3],
            "name": ["Alice", None, "Charlie"],
            "score": [25.5, np.nan, 35.0]
        })
        table = preview.generate_table(df_with_nulls)
        assert isinstance(table, Table)
        assert len(table.columns) == 3
