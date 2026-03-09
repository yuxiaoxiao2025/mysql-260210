"""CLI preview module for displaying DataFrames with rich formatting."""

from typing import Optional

import pandas as pd
from rich.table import Table
from rich.console import Console


class CLIPreview:
    """CLI preview handler for displaying query results."""

    def __init__(self, console: Optional[Console] = None):
        """Initialize CLIPreview with optional custom console.

        Args:
            console: Optional rich Console instance. If not provided,
                    a default Console will be created.
        """
        self.console = console or Console()

    def generate_table(
        self,
        df: pd.DataFrame,
        title: Optional[str] = None
    ) -> Table:
        """Generate a rich Table from a DataFrame.

        Args:
            df: The DataFrame to display.
            title: Optional title for the table.

        Returns:
            A rich Table instance.
        """
        table = Table(title=title)

        # Add columns with styling
        for column in df.columns:
            table.add_column(str(column), overflow="fold")

        # Add rows
        for _, row in df.iterrows():
            row_values = [str(value) for value in row]
            table.add_row(*row_values)

        return table

    def show(
        self,
        df: pd.DataFrame,
        title: Optional[str] = None
    ) -> None:
        """Display a DataFrame in the console.

        Args:
            df: The DataFrame to display.
            title: Optional title for the table.
        """
        table = self.generate_table(df, title=title)
        self.console.print(table)
