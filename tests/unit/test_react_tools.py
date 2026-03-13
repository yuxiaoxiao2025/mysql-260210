import pandas as pd
import pytest

from src.react.tool_service import MVPToolService


class FakeDB:
    def __init__(self) -> None:
        self.last_readonly_sql: str | None = None
        self.readonly_called: bool = False
        self.index_metadata_called: bool = False
        self.index_metadata_args: tuple | None = None

    def execute_query(self, sql: str, params: dict | None = None) -> pd.DataFrame:
        self.last_readonly_sql = sql
        self.readonly_called = True
        # 默认返回一个简单结果，便于后续扩展其他测试
        return pd.DataFrame([{"id": 1, "name": "test"}])

    def get_table_indexes(self, db_name: str | None, table_name: str) -> list[dict]:
        self.index_metadata_called = True
        self.index_metadata_args = (db_name, table_name)
        # 返回模拟的 information_schema.statistics 摘要
        return [
            {
                "table_schema": db_name or "test_db",
                "table_name": table_name,
                "index_name": "idx_users_name",
                "non_unique": 0,
                "seq_in_index": 1,
                "column_name": "name",
                "index_type": "BTREE",
            },
            {
                "table_schema": db_name or "test_db",
                "table_name": table_name,
                "index_name": "idx_users_age",
                "non_unique": 1,
                "seq_in_index": 1,
                "column_name": "age",
                "index_type": "BTREE",
            },
        ]


class FakeRetrieval:
    def search(self, query: str, top_k: int = 10):
        # 本文件暂不关心检索逻辑，返回空结果即可
        class Result:
            matches: list = []

        return Result()


class FakeExecutor:
    def execute_operation(self, *args, **kwargs):
        raise NotImplementedError


class FakeKnowledge:
    def get_all_operations(self):
        return {}

    def get_operation(self, operation_id: str):
        return None


def make_service(fake_db: FakeDB | None = None) -> MVPToolService:
    db = fake_db or FakeDB()
    retrieval = FakeRetrieval()
    executor = FakeExecutor()
    knowledge = FakeKnowledge()
    return MVPToolService(db_manager=db, retrieval_pipeline=retrieval, operation_executor=executor, knowledge_loader=knowledge)


class TestRunReadonlySql:
    def test_run_readonly_sql_rejects_mutations(self):
        """DELETE 这类变更语句必须被明确拒绝"""
        svc = make_service()

        output = svc.execute(
            "run_readonly_sql",
            {"sql": "DELETE FROM t", "purpose": "测试删除"},
        )

        assert isinstance(output, str)
        assert ("拒绝" in output) or ("不允许" in output)
        # 不应该真正去执行查询
        fake_db: FakeDB = svc.db  # type: ignore[assignment]
        assert fake_db.readonly_called is False


class TestListIndexes:
    def test_list_indexes_calls_metadata_and_returns_summary(self):
        """list_indexes 应走 information_schema 语义并返回索引摘要，而不是拼 SQL"""
        fake_db = FakeDB()
        svc = make_service(fake_db)

        output = svc.execute(
            "list_indexes",
            {"table_name": "users"},
        )

        # 元数据方法应被调用
        assert fake_db.index_metadata_called is True
        assert fake_db.index_metadata_args == (None, "users")

        # 输出为索引摘要
        assert "idx_users_name" in output
        assert "idx_users_age" in output
        # 不应该泄露任何 SQL 文本或系统库名
        lowered = output.lower()
        assert "select " not in lowered
        assert "show " not in lowered
        assert "desc " not in lowered
        assert "describe " not in lowered
        assert "information_schema" not in lowered
        assert "sql" not in lowered

