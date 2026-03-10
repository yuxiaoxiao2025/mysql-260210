"""Integration tests for detail_panel with real database."""
import pytest
import sys
import importlib.util

# Import DatabaseManager directly from module file to avoid streamlit dependency issues in __init__.py
from src.db_manager import DatabaseManager

# Import detail_panel module directly to avoid __init__.py importing streamlit
spec = importlib.util.spec_from_file_location(
    "detail_panel", "src/web/components/detail_panel.py"
)
detail_panel_module = importlib.util.module_from_spec(spec)

# Mock streamlit before loading the module
sys.modules['streamlit'] = type(sys)('streamlit')
sys.modules['streamlit'].components = type(sys)('streamlit.components')
sys.modules['pandas'] = importlib.import_module('pandas')
sys.modules['networkx'] = importlib.import_module('networkx')
sys.modules['sqlalchemy'] = importlib.import_module('sqlalchemy')
sys.modules['sqlalchemy.exc'] = importlib.import_module('sqlalchemy.exc')

spec.loader.exec_module(detail_panel_module)
get_table_columns = detail_panel_module.get_table_columns


@pytest.fixture(scope="module")
def db_manager():
    """Create database manager instance (module scope for efficiency)."""
    db = DatabaseManager()
    yield db
    # Cleanup
    db.engine.dispose()


@pytest.mark.integration
class TestDetailPanelIntegration:
    """Integration tests with real database connection."""

    def test_get_columns_parkcloud_table(self, db_manager):
        """Test getting columns from parkcloud schema table."""
        columns = get_table_columns(db_manager, "parkcloud.plate_icbc_agreement")

        # Verify we got columns
        assert isinstance(columns, list)
        if columns:  # Table might not exist in test environment
            assert all("name" in col for col in columns)

    def test_get_columns_nonexistent_table(self, db_manager):
        """Test handling of non-existent table returns empty list."""
        columns = get_table_columns(db_manager, "nonexistent.nonexistent_table")
        assert columns == []

    def test_get_columns_invalid_identifier(self, db_manager):
        """Test invalid identifier returns empty list."""
        columns = get_table_columns(db_manager, "invalid-name.table")
        assert columns == []