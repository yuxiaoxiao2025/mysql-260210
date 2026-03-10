from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.web.services.sql_generator import SQLGenerator


@pytest.fixture
def generator():
    llm = MagicMock()
    db = MagicMock()
    graph = MagicMock()
    return SQLGenerator(llm_client=llm, db_manager=db, graph_service=graph)


def test_build_table_context_contains_schema(generator):
    generator.db_manager.get_table_schema.return_value = [
        {"name": "id", "type": "INT", "comment": "主键"},
        {"name": "name", "type": "VARCHAR"},
    ]
    context = generator._build_table_context(["users"], include_join_paths=False)
    assert "表名: users" in context
    assert "id (INT)" in context
    assert "name (VARCHAR)" in context


def test_build_table_context_skips_failed_schema(generator):
    generator.db_manager.get_table_schema.side_effect = RuntimeError("boom")
    context = generator._build_table_context(["users"], include_join_paths=False)
    assert context == ""


def test_build_table_context_adds_join_path(generator):
    generator.db_manager.get_table_schema.return_value = [{"name": "id", "type": "INT", "comment": ""}]
    generator._find_join_path = MagicMock(return_value=["orders", "users"])
    context = generator._build_table_context(["orders", "users"], include_join_paths=True)
    assert "表之间的关系" in context
    assert "orders -> users: orders -> users" in context


def test_find_join_path_returns_none_without_graph():
    sql_generator = SQLGenerator(llm_client=MagicMock(), db_manager=MagicMock(), graph_service=None)
    assert sql_generator._find_join_path("a", "b") is None


def test_find_join_path_returns_shortest_path(generator):
    import networkx as nx

    graph = nx.MultiDiGraph()
    graph.add_edge("a", "b")
    graph.add_edge("b", "c")
    generator.graph_service.graph = graph
    assert generator._find_join_path("a", "c") == ["a", "b", "c"]


def test_extract_sql_from_sql_code_block(generator):
    result = generator._extract_sql("```sql\nSELECT 1;\n```")
    assert result == "SELECT 1;"


def test_extract_sql_from_generic_code_block(generator):
    result = generator._extract_sql("```\nSELECT * FROM t\n```")
    assert result == "SELECT * FROM t"


def test_extract_sql_plain_text(generator):
    assert generator._extract_sql(" SELECT id FROM users ") == "SELECT id FROM users"


def test_generate_sql_success_and_record_history(generator):
    generator.db_manager.get_table_schema.return_value = [{"name": "id", "type": "INT", "comment": ""}]
    generator.llm_client.generate_sql.return_value = {"sql": "```sql\nSELECT id FROM users\n```"}
    sql = generator.generate_sql("查用户", ["users"])
    assert sql == "SELECT id FROM users"
    assert len(generator.history) == 1
    assert generator.history[0]["query"] == "查用户"


def test_generate_sql_returns_error_message_on_exception(generator):
    generator.db_manager.get_table_schema.return_value = [{"name": "id", "type": "INT", "comment": ""}]
    generator.llm_client.generate_sql.side_effect = RuntimeError("llm down")
    sql = generator.generate_sql("查用户", ["users"])
    assert sql.startswith("-- Error generating SQL:")


def test_refine_sql_returns_current_sql_on_exception(generator):
    generator.db_manager.get_table_schema.return_value = [{"name": "id", "type": "INT", "comment": ""}]
    generator.llm_client.generate_sql.side_effect = RuntimeError("llm down")
    current = "SELECT 1"
    assert generator.refine_sql("q", current, ["users"], "加条件") == current


@pytest.mark.parametrize("bad_sql", ["INSERT INTO t VALUES (1)", "UPDATE t SET a=1", "DELETE FROM t", "DROP TABLE t", "TRUNCATE TABLE t", "ALTER TABLE t ADD c INT"])
def test_execute_sql_blocks_mutations(generator, bad_sql):
    ok, df, msg = generator.execute_sql(bad_sql)
    assert ok is False
    assert isinstance(df, pd.DataFrame)
    assert "只允许执行 SELECT 查询" in msg


def test_execute_sql_success(generator):
    expected = pd.DataFrame([{"id": 1}])
    generator.db_manager.execute_query.return_value = expected
    ok, df, msg = generator.execute_sql("SELECT id FROM users")
    assert ok is True
    assert msg == ""
    assert df.equals(expected)


def test_execute_sql_handles_db_errors(generator):
    generator.db_manager.execute_query.side_effect = RuntimeError("db error")
    ok, df, msg = generator.execute_sql("SELECT id FROM users")
    assert ok is False
    assert isinstance(df, pd.DataFrame)
    assert "db error" in msg
