import re
import os
from src.db_manager import DatabaseManager

class SchemaLoader:
    def __init__(self, doc_path="mysql.md", db_manager=None):
        self.doc_path = doc_path
        self.db_manager = db_manager if db_manager else DatabaseManager()
        self.table_descriptions = {}
        self.db_mapping = {} # table -> db_name
        self.schema = {}
        self._load_descriptions()
        self._load_schema()

    def _load_descriptions(self):
        """Parse mysql.md to get table descriptions and database mapping"""
        if not os.path.exists(self.doc_path):
            return

        current_db = None
        try:
            with open(self.doc_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    
                    # Parse DB name
                    # 数据库名称：cloudinterface
                    db_match = re.match(r'数据库名称：(\w+)', line)
                    if db_match:
                        current_db = db_match.group(1)
                        continue

                    # Parse Table info
                    # config                  新版云云接口V2.0.0版本程序url配置表
                    # cloud_operator          登录人员表
                    # Ignore lines starting with # or empty
                    if not line or line.startswith('#') or line.startswith('-'):
                        continue
                    
                    # Match table_name followed by description
                    # Assume table names are alphanumeric + underscore
                    table_match = re.match(r'^([a-zA-Z0-9_]+)\s+(.+)$', line)
                    if table_match:
                        table_name = table_match.group(1)
                        desc = table_match.group(2)
                        self.table_descriptions[table_name] = desc
                        if current_db:
                            self.db_mapping[table_name] = current_db
        except OSError:
            return

    def _load_schema(self):
        """Load table schemas from database and cache them."""
        try:
            tables = self.db_manager.get_all_tables()
        except Exception:
            return

        for table in tables:
            try:
                self.schema[table] = self.db_manager.get_table_schema(table)
            except Exception:
                continue

    def get_schema_context(self):
        """
        Get formatted schema context for LLM.
        Tries to fetch real column info from DB.
        """
        context_lines = []
        context_lines.append("Database Schema:")
        
        # We will iterate over the tables we found in the doc
        # because those are the ones the user likely cares about.
        # If the doc is empty, we fallback to all tables in current DB.
        tables_to_inspect = list(self.table_descriptions.keys())

        if not tables_to_inspect:
            tables_to_inspect = list(self.schema.keys())

        if not tables_to_inspect:
            try:
                tables_to_inspect = self.db_manager.get_all_tables()
            except Exception:
                tables_to_inspect = []

        if not tables_to_inspect:
            context_lines.append("No tables found")
            return "\n".join(context_lines)

        for table in tables_to_inspect:
            desc = self.table_descriptions.get(table, "")
            db_name = self.db_mapping.get(table, "")
            
            # Construct full table name if we know the DB and it's different from default?
            # For now, let's just try to inspect 'table'
            # If it fails, maybe try 'db.table'
            
            columns_str = "Columns: (Could not fetch)"
            try:
                columns = self.schema.get(table)
                if columns is None:
                    columns = self.db_manager.get_table_schema(
                        table, schema=db_name if db_name else None
                    )
                    self.schema[table] = columns
                # Format: name(type, comment)
                col_descs = []
                for col in columns:
                    c_str = f"{col['name']}"
                    if col.get('comment'):
                        c_str += f" ({col['comment']})"
                    col_descs.append(c_str)
                columns_str = "Columns: " + ", ".join(col_descs)
            except Exception as e:
                # If failed, try with db prefix if available
                if db_name:
                    try:
                        # This relies on get_table_schema handling 'db.table' or us modifying it
                        # For now, let's just log the failure to context
                        columns_str = f"Columns: (Access Error: {str(e)})"
                    except:
                        pass
            
            context_lines.append(f"- Table: {table}")
            if db_name:
                context_lines.append(f"  Database: {db_name}")
            if desc:
                context_lines.append(f"  Description: {desc}")
            context_lines.append(f"  {columns_str}")
            context_lines.append("")

        return "\n".join(context_lines)

if __name__ == "__main__":
    loader = SchemaLoader()
    print(loader.get_schema_context())
