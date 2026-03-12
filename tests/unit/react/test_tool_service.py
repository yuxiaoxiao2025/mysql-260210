"""测试工具服务"""
import pytest
from unittest.mock import Mock, MagicMock
import pandas as pd

from src.react.tool_service import MVPToolService, NEED_CONFIRM_MARKER


@pytest.fixture
def tool_service():
    """创建工具服务实例"""
    db = Mock()
    retrieval = Mock()
    executor = Mock()
    knowledge = Mock()

    return MVPToolService(db, retrieval, executor, knowledge)


class TestExecuteMethod:
    """测试 execute 方法"""

    def test_execute_unknown_tool(self, tool_service):
        """测试未知工具"""
        result = tool_service.execute("unknown_tool", {})

        assert "未知工具" in result

    def test_execute_with_exception(self, tool_service):
        """测试工具执行异常"""
        tool_service.retrieval.search.side_effect = Exception("搜索失败")

        result = tool_service.execute("search_schema", {"query": "测试"})

        assert "工具执行失败" in result


class TestSearchSchema:
    """测试 search_schema 工具"""

    def test_search_no_results(self, tool_service):
        """测试搜索无结果"""
        # 创建一个模拟的空结果
        mock_result = Mock()
        mock_result.matches = []
        tool_service.retrieval.search.return_value = mock_result

        result = tool_service._tool_search_schema("不存在")

        assert "未找到" in result

    def test_search_with_results(self, tool_service):
        """测试搜索有结果"""
        # 创建模拟的匹配结果
        mock_match = Mock()
        mock_match.table_name = "cloud_fixed_plate"
        mock_match.description = "车牌表"

        mock_result = Mock()
        mock_result.matches = [mock_match]
        tool_service.retrieval.search.return_value = mock_result

        result = tool_service._tool_search_schema("车牌")

        assert "cloud_fixed_plate" in result
        assert "车牌表" in result

    def test_search_without_description(self, tool_service):
        """测试搜索结果无描述"""
        mock_match = Mock()
        mock_match.table_name = "users"
        mock_match.description = None

        mock_result = Mock()
        mock_result.matches = [mock_match]
        tool_service.retrieval.search.return_value = mock_result

        result = tool_service._tool_search_schema("用户")

        assert "users" in result


class TestExecuteSql:
    """测试 execute_sql 工具"""

    def test_execute_select_query(self, tool_service):
        """测试SELECT查询"""
        tool_service.db.execute_query.return_value = pd.DataFrame({
            "name": ["张三", "李四"],
            "age": [25, 30]
        })

        result = tool_service._tool_execute_sql("SELECT * FROM users")

        assert "2 行数据" in result
        assert "张三" in result

    def test_execute_select_empty(self, tool_service):
        """测试SELECT查询无结果"""
        tool_service.db.execute_query.return_value = pd.DataFrame()

        result = tool_service._tool_execute_sql("SELECT * FROM users WHERE id = -1")

        assert "查询结果为空" in result

    def test_execute_select_error(self, tool_service):
        """测试SELECT查询失败"""
        tool_service.db.execute_query.side_effect = Exception("表不存在")

        result = tool_service._tool_execute_sql("SELECT * FROM nonexistent")

        assert "查询失败" in result
        assert "表不存在" in result

    def test_execute_select_large_result(self, tool_service):
        """测试SELECT查询大量数据"""
        # 创建 100 行数据
        tool_service.db.execute_query.return_value = pd.DataFrame({
            "id": range(100),
            "name": [f"用户{i}" for i in range(100)]
        })

        result = tool_service._tool_execute_sql("SELECT * FROM users")

        assert "100 行数据" in result
        assert "省略" in result

    def test_execute_show_query(self, tool_service):
        """测试SHOW查询直接执行"""
        tool_service.db.execute_query.return_value = pd.DataFrame({
            "Database": ["db1", "db2"]
        })

        result = tool_service._tool_execute_sql("SHOW DATABASES")

        assert "2 行数据" in result

    def test_execute_desc_query(self, tool_service):
        """测试DESC查询直接执行"""
        tool_service.db.execute_query.return_value = pd.DataFrame({
            "Field": ["id", "name"],
            "Type": ["int", "varchar"]
        })

        result = tool_service._tool_execute_sql("DESC users")

        assert "2 行数据" in result

    def test_execute_update_needs_confirm(self, tool_service):
        """测试UPDATE需要确认"""
        result = tool_service._tool_execute_sql("UPDATE users SET age=20", "更新年龄")

        assert NEED_CONFIRM_MARKER in result
        assert "更新年龄" in result
        assert "UPDATE users" in result

    def test_execute_insert_needs_confirm(self, tool_service):
        """测试INSERT需要确认"""
        result = tool_service._tool_execute_sql("INSERT INTO users VALUES (1, 'test')")

        assert NEED_CONFIRM_MARKER in result

    def test_execute_delete_needs_confirm(self, tool_service):
        """测试DELETE需要确认"""
        result = tool_service._tool_execute_sql("DELETE FROM users WHERE id=1", "删除用户")

        assert NEED_CONFIRM_MARKER in result

    def test_execute_sql_with_description(self, tool_service):
        """测试带描述的修改操作"""
        result = tool_service._tool_execute_sql(
            "UPDATE users SET status='active'",
            "激活用户状态"
        )

        assert NEED_CONFIRM_MARKER in result
        assert "激活用户状态" in result


class TestListOperations:
    """测试 list_operations 工具"""

    def test_list_no_operations(self, tool_service):
        """测试无操作"""
        tool_service.knowledge.get_all_operations.return_value = {}

        result = tool_service._tool_list_operations()

        assert "暂无预定义操作" in result

    def test_list_with_operations(self, tool_service):
        """测试有操作"""
        from src.knowledge.knowledge_loader import Operation

        op1 = Operation(
            id="plate_query",
            name="车牌查询",
            description="根据车牌号查询车辆信息",
            keywords=["车牌", "查询"],
            category="query"
        )
        op2 = Operation(
            id="plate_distribute",
            name="车牌下发",
            description="下发车牌到指定园区",
            keywords=["车牌", "下发"],
            category="mutation"
        )

        tool_service.knowledge.get_all_operations.return_value = {
            "plate_query": op1,
            "plate_distribute": op2
        }

        result = tool_service._tool_list_operations()

        assert "plate_query" in result
        assert "车牌查询" in result
        assert "plate_distribute" in result

    def test_list_operations_limit(self, tool_service):
        """测试操作列表限制"""
        from src.knowledge.knowledge_loader import Operation

        # 创建 30 个操作
        operations = {}
        for i in range(30):
            op = Operation(
                id=f"op_{i}",
                name=f"操作{i}",
                description=f"这是操作{i}的描述",
                keywords=[],
                category="query"
            )
            operations[f"op_{i}"] = op

        tool_service.knowledge.get_all_operations.return_value = operations

        result = tool_service._tool_list_operations()

        assert "共 30 个操作" in result

    def test_list_operations_without_description(self, tool_service):
        """测试无描述的操作"""
        from src.knowledge.knowledge_loader import Operation

        op = Operation(
            id="test_op",
            name="测试操作",
            description="",
            keywords=[],
            category="query"
        )

        tool_service.knowledge.get_all_operations.return_value = {"test_op": op}

        result = tool_service._tool_list_operations()

        assert "test_op" in result
        assert "测试操作" in result


class TestExecuteOperation:
    """测试 execute_operation 工具"""

    def test_execute_operation_preview_fail(self, tool_service):
        """测试操作预览失败"""
        from src.executor.operation_executor import ExecutionResult

        tool_service.executor.execute_operation.return_value = ExecutionResult(
            success=False,
            operation_id="test_op",
            operation_name="测试操作",
            error="操作不存在"
        )

        result = tool_service._tool_execute_operation("test_op")

        assert "操作预览失败" in result
        assert "操作不存在" in result

    def test_execute_query_operation_directly(self, tool_service):
        """测试查询操作直接执行"""
        from src.executor.operation_executor import ExecutionResult
        from src.knowledge.knowledge_loader import Operation

        # 模拟查询操作
        op = Operation(
            id="plate_query",
            name="车牌查询",
            description="查询车牌",
            keywords=[],
            category="query"
        )
        tool_service.knowledge.get_operation.return_value = op

        # 预览成功
        tool_service.executor.execute_operation.return_value = ExecutionResult(
            success=True,
            operation_id="plate_query",
            operation_name="车牌查询",
            summary="找到车牌 沪A12345"
        )

        result = tool_service._tool_execute_operation("plate_query", {"plate_no": "沪A12345"})

        assert "操作成功" in result
        assert "找到车牌" in result

    def test_execute_mutation_operation_needs_confirm(self, tool_service):
        """测试变更操作需要确认"""
        from src.executor.operation_executor import ExecutionResult
        from src.knowledge.knowledge_loader import Operation

        # 模拟变更操作
        op = Operation(
            id="plate_distribute",
            name="车牌下发",
            description="下发车牌",
            keywords=[],
            category="mutation"
        )
        tool_service.knowledge.get_operation.return_value = op

        # 预览成功
        tool_service.executor.execute_operation.return_value = ExecutionResult(
            success=True,
            operation_id="plate_distribute",
            operation_name="车牌下发",
            summary="将下发车牌到园区"
        )

        result = tool_service._tool_execute_operation("plate_distribute", {"plate_no": "沪A12345"})

        assert NEED_CONFIRM_MARKER in result
        assert "车牌下发" in result

    def test_execute_operation_with_params(self, tool_service):
        """测试带参数的操作"""
        from src.executor.operation_executor import ExecutionResult
        from src.knowledge.knowledge_loader import Operation

        op = Operation(
            id="test_op",
            name="测试操作",
            description="",
            keywords=[],
            category="query"
        )
        tool_service.knowledge.get_operation.return_value = op

        tool_service.executor.execute_operation.return_value = ExecutionResult(
            success=True,
            operation_id="test_op",
            operation_name="测试操作"
        )

        result = tool_service._tool_execute_operation("test_op", {"param1": "value1"})

        assert "操作成功" in result


class TestConfirmMethods:
    """测试确认方法"""

    def test_confirm_and_execute_sql_success(self, tool_service):
        """测试确认执行SQL成功"""
        tool_service.db.execute_update.return_value = 5

        result = tool_service.confirm_and_execute_sql("UPDATE users SET status='active'")

        assert "执行成功" in result
        assert "5 行" in result

    def test_confirm_and_execute_sql_error(self, tool_service):
        """测试确认执行SQL失败"""
        tool_service.db.execute_update.side_effect = Exception("约束违反")

        result = tool_service.confirm_and_execute_sql("DELETE FROM users")

        assert "执行失败" in result
        assert "约束违反" in result

    def test_confirm_and_execute_operation_success(self, tool_service):
        """测试确认执行操作成功"""
        from src.executor.operation_executor import ExecutionResult

        tool_service.executor.execute_operation.return_value = ExecutionResult(
            success=True,
            operation_id="plate_distribute",
            operation_name="车牌下发",
            summary="已下发车牌到园区"
        )

        result = tool_service.confirm_and_execute_operation("plate_distribute", {"plate_no": "沪A12345"})

        assert "操作成功" in result
        assert "已下发车牌" in result

    def test_confirm_and_execute_operation_fail(self, tool_service):
        """测试确认执行操作失败"""
        from src.executor.operation_executor import ExecutionResult

        tool_service.executor.execute_operation.return_value = ExecutionResult(
            success=False,
            operation_id="plate_distribute",
            operation_name="车牌下发",
            error="车牌不存在"
        )

        result = tool_service.confirm_and_execute_operation("plate_distribute", {"plate_no": "不存在"})

        assert "操作失败" in result
        assert "车牌不存在" in result