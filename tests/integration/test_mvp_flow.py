"""MVP 流程端到端测试

测试场景：
1. 查询车牌信息
2. 列出所有园区
3. 修改操作需要确认
4. 用户修正
5. 用户取消操作
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
import pandas as pd

from src.react.orchestrator import MVPReACTOrchestrator
from src.react.tool_service import MVPToolService, NEED_CONFIRM_MARKER
from src.llm_tool_models import ChatResponse, ToolCall


@pytest.fixture
def mock_components():
    """创建模拟组件"""
    llm = Mock()
    db = Mock()
    retrieval = Mock()
    executor = Mock()
    knowledge = Mock()

    return {
        "llm": llm,
        "db": db,
        "retrieval": retrieval,
        "executor": executor,
        "knowledge": knowledge
    }


@pytest.fixture
def tool_service(mock_components):
    """创建工具服务实例"""
    return MVPToolService(
        mock_components["db"],
        mock_components["retrieval"],
        mock_components["executor"],
        mock_components["knowledge"]
    )


@pytest.fixture
def orchestrator(mock_components, tool_service):
    """创建编排器实例"""
    return MVPReACTOrchestrator(
        mock_components["llm"],
        tool_service
    )


class TestMVPFlow:
    """MVP 流程端到端测试"""

    def test_query_plate_info(self, orchestrator, mock_components):
        """测试用例1：查询车牌信息

        场景：用户查询车牌 沪A12345 的信息
        预期：返回车牌状态和绑定园区
        """
        # 设置模拟数据
        mock_components["db"].execute_query.return_value = pd.DataFrame({
            "plate_no": ["沪A12345"],
            "status": ["已下发"],
            "park_name": ["国际商务中心"]
        })

        # 模拟 LLM 先调用工具，然后返回结果
        tc = ToolCall(
            id="call_1",
            name="execute_sql",
            arguments='{"sql": "SELECT * FROM cloud_fixed_plate WHERE plate_no=\\"沪A12345\\"", "description": "查询车牌信息"}'
        )

        mock_components["llm"].chat_with_tools.side_effect = [
            ChatResponse(content=None, tool_calls=[tc]),
            ChatResponse(
                content="车牌 沪A12345，状态=已下发，绑定园区=国际商务中心",
                tool_calls=[]
            )
        ]

        # 执行查询
        result = orchestrator.process("查询车牌 沪A12345")

        # 验证结果
        assert result != "None"
        assert "沪A12345" in result or "车牌" in result
        assert len(orchestrator.state.messages) >= 2

    def test_list_parks(self, orchestrator, mock_components):
        """测试用例5：列出所有园区

        场景：用户想查看所有园区
        预期：返回园区列表
        """
        # 设置模拟数据
        mock_components["db"].execute_query.return_value = pd.DataFrame({
            "id": [1, 2, 3],
            "name": ["国际商务中心", "科技园", "金融中心"],
            "address": ["浦东新区", "徐汇区", "静安区"]
        })

        # 模拟 LLM 调用工具并返回结果
        tc = ToolCall(
            id="call_1",
            name="execute_sql",
            arguments='{"sql": "SELECT id, name, address FROM park_info", "description": "列出所有园区"}'
        )

        mock_components["llm"].chat_with_tools.side_effect = [
            ChatResponse(content=None, tool_calls=[tc]),
            ChatResponse(
                content="当前系统有3个园区：国际商务中心（浦东新区）、科技园（徐汇区）、金融中心（静安区）",
                tool_calls=[]
            )
        ]

        # 执行查询
        result = orchestrator.process("列出所有园区")

        # 验证结果
        assert result != "None"
        assert "园区" in result

    def test_update_needs_confirmation(self, orchestrator, mock_components):
        """测试修改操作需要确认

        场景：用户执行修改操作（如更新车牌状态）
        预期：系统要求确认后再执行
        """
        # 模拟 LLM 生成 UPDATE SQL
        tc = ToolCall(
            id="call_1",
            name="execute_sql",
            arguments='{"sql": "UPDATE cloud_fixed_plate SET status=\\"已激活\\" WHERE plate_no=\\"沪A12345\\"", "description": "激活车牌状态"}'
        )

        mock_components["llm"].chat_with_tools.return_value = ChatResponse(
            content=None,
            tool_calls=[tc]
        )

        # 执行操作
        result = orchestrator.process("激活车牌 沪A12345")

        # 验证需要确认
        assert "确认执行" in result
        assert orchestrator.state.pending_confirmation
        assert orchestrator.state.confirmation_type == "sql"

        # 用户确认
        mock_components["db"].execute_update.return_value = 1
        confirm_result = orchestrator.confirm(True)

        # 验证执行成功
        assert "执行成功" in confirm_result
        assert not orchestrator.state.pending_confirmation

    def test_user_correction(self, orchestrator, mock_components):
        """测试用例9：用户修正

        场景：用户要求修正查询条件
        预期：系统根据修正重新执行
        """
        # 第一次查询结果
        mock_components["db"].execute_query.return_value = pd.DataFrame({
            "plate_no": ["沪A54321"],
            "status": ["已下发"],
            "park_name": ["科技园"]
        })

        # 第一次 LLM 调用 - 错误的车牌
        tc1 = ToolCall(
            id="call_1",
            name="execute_sql",
            arguments='{"sql": "SELECT * FROM cloud_fixed_plate WHERE plate_no=\\"沪A54321\\"", "description": "查询车牌"}'
        )

        # 第二次 LLM 调用 - 正确的车牌
        mock_components["db"].execute_query.return_value = pd.DataFrame({
            "plate_no": ["沪A12345"],
            "status": ["已激活"],
            "park_name": ["国际商务中心"]
        })

        tc2 = ToolCall(
            id="call_2",
            name="execute_sql",
            arguments='{"sql": "SELECT * FROM cloud_fixed_plate WHERE plate_no=\\"沪A12345\\"", "description": "查询正确车牌"}'
        )

        # 设置对话历史
        orchestrator.state.messages = [
            {"role": "user", "content": "查询车牌"},
            {"role": "assistant", "content": "车牌 沪A54321，状态=已下发，绑定园区=科技园"},
        ]

        # 模拟 LLM 响应修正后的查询
        mock_components["llm"].chat_with_tools.side_effect = [
            ChatResponse(content=None, tool_calls=[tc2]),
            ChatResponse(
                content="车牌 沪A12345，状态=已激活，绑定园区=国际商务中心",
                tool_calls=[]
            )
        ]

        # 用户修正
        result = orchestrator.process("不对，我要查的是沪A12345")

        # 验证结果
        assert result != "None"
        assert "沪A12345" in result or "车牌" in result

    def test_user_cancel(self, orchestrator, mock_components):
        """测试用例10：用户取消操作

        场景：用户取消待确认的操作
        预期：操作被取消，数据库未被修改
        """
        # 模拟 LLM 生成修改操作
        tc = ToolCall(
            id="call_1",
            name="execute_sql",
            arguments='{"sql": "DELETE FROM cloud_fixed_plate WHERE plate_no=\\"沪A12345\\"", "description": "删除车牌"}'
        )

        mock_components["llm"].chat_with_tools.return_value = ChatResponse(
            content=None,
            tool_calls=[tc]
        )

        # 执行操作，触发确认
        orchestrator.process("删除车牌 沪A12345")

        # 验证进入待确认状态
        assert orchestrator.state.pending_confirmation

        # 用户取消
        result = orchestrator.confirm(False)

        # 验证取消成功
        assert "取消" in result
        assert not orchestrator.state.pending_confirmation
        assert orchestrator.state.confirmation_data == {}

        # 验证数据库未被修改
        mock_components["db"].execute_update.assert_not_called()

    def test_execute_operation_flow(self, orchestrator, mock_components):
        """测试预定义操作流程

        场景：用户通过预定义操作查询车牌
        预期：正确执行操作并返回结果
        """
        from src.executor.operation_executor import ExecutionResult
        from src.knowledge.knowledge_loader import Operation

        # 模拟操作定义
        op = Operation(
            id="plate_query",
            name="车牌查询",
            description="根据车牌号查询车辆信息",
            keywords=["车牌", "查询"],
            category="query"
        )
        mock_components["knowledge"].get_operation.return_value = op

        # 模拟操作执行结果
        mock_components["executor"].execute_operation.return_value = ExecutionResult(
            success=True,
            operation_id="plate_query",
            operation_name="车牌查询",
            summary="车牌 沪A12345，状态=已下发，绑定园区=国际商务中心"
        )

        # 模拟 LLM 调用操作
        tc = ToolCall(
            id="call_1",
            name="execute_operation",
            arguments='{"operation_id": "plate_query", "params": {"plate_no": "沪A12345"}}'
        )

        mock_components["llm"].chat_with_tools.side_effect = [
            ChatResponse(content=None, tool_calls=[tc]),
            ChatResponse(
                content="查询结果：车牌 沪A12345，状态=已下发，绑定园区=国际商务中心",
                tool_calls=[]
            )
        ]

        # 执行操作
        result = orchestrator.process("查询车牌 沪A12345")

        # 验证结果
        assert result != "None"
        assert "沪A12345" in result

    def test_mutation_operation_needs_confirm(self, orchestrator, mock_components):
        """测试变更操作需要确认

        场景：用户执行变更类型的预定义操作
        预期：系统要求确认
        """
        from src.executor.operation_executor import ExecutionResult
        from src.knowledge.knowledge_loader import Operation

        # 模拟变更操作
        op = Operation(
            id="plate_distribute",
            name="车牌下发",
            description="下发车牌到指定园区",
            keywords=["车牌", "下发"],
            category="mutation"
        )
        mock_components["knowledge"].get_operation.return_value = op

        # 模拟预览结果
        mock_components["executor"].execute_operation.return_value = ExecutionResult(
            success=True,
            operation_id="plate_distribute",
            operation_name="车牌下发",
            summary="将车牌 沪A12345 下发到 国际商务中心"
        )

        # 模拟 LLM 调用操作
        tc = ToolCall(
            id="call_1",
            name="execute_operation",
            arguments='{"operation_id": "plate_distribute", "params": {"plate_no": "沪A12345", "park_name": "国际商务中心"}}'
        )

        mock_components["llm"].chat_with_tools.return_value = ChatResponse(
            content=None,
            tool_calls=[tc]
        )

        # 执行操作
        result = orchestrator.process("把车牌 沪A12345 下发到 国际商务中心")

        # 验证需要确认
        assert "确认执行" in result
        assert orchestrator.state.pending_confirmation
        assert orchestrator.state.confirmation_type == "operation"

        # 用户确认执行
        mock_components["executor"].execute_operation.return_value = ExecutionResult(
            success=True,
            operation_id="plate_distribute",
            operation_name="车牌下发",
            summary="车牌已成功下发"
        )

        confirm_result = orchestrator.confirm(True)

        assert "操作成功" in confirm_result
        assert not orchestrator.state.pending_confirmation

    def test_conversation_history_preserved(self, orchestrator, mock_components):
        """测试对话历史保存

        场景：多轮对话
        预期：历史消息被正确保存
        """
        # 第一轮对话
        mock_components["llm"].chat_with_tools.return_value = ChatResponse(
            content="你好，我是停车数据库助手",
            tool_calls=[]
        )
        orchestrator.process("你好")
        assert len(orchestrator.state.messages) == 2

        # 第二轮对话
        mock_components["llm"].chat_with_tools.return_value = ChatResponse(
            content="我可以帮你查询车牌、园区等信息",
            tool_calls=[]
        )
        orchestrator.process("你能做什么")
        assert len(orchestrator.state.messages) == 4

        # 验证消息角色
        roles = [msg["role"] for msg in orchestrator.state.messages]
        assert roles == ["user", "assistant", "user", "assistant"]

    def test_error_handling(self, orchestrator, mock_components):
        """测试错误处理

        场景：查询发生错误
        预期：返回友好的错误信息
        """
        # 模拟数据库错误
        mock_components["db"].execute_query.side_effect = Exception("表不存在")

        tc = ToolCall(
            id="call_1",
            name="execute_sql",
            arguments='{"sql": "SELECT * FROM nonexistent_table", "description": "查询不存在的表"}'
        )

        mock_components["llm"].chat_with_tools.side_effect = [
            ChatResponse(content=None, tool_calls=[tc]),
            ChatResponse(
                content="抱歉，查询时发生错误：表不存在。请检查表名是否正确。",
                tool_calls=[]
            )
        ]

        # 执行查询
        result = orchestrator.process("查询不存在的表")

        # 验证错误处理
        assert result != "None"
        assert "错误" in result or "抱歉" in result

    def test_search_schema_tool(self, orchestrator, mock_components):
        """测试搜索表结构工具

        场景：用户询问数据结构
        预期：返回相关表的信息
        """
        # 模拟检索结果
        mock_match = Mock()
        mock_match.table_name = "cloud_fixed_plate"
        mock_match.description = "车牌信息表"

        mock_result = Mock()
        mock_result.matches = [mock_match]
        mock_components["retrieval"].search.return_value = mock_result

        # 模拟 LLM 调用工具
        tc = ToolCall(
            id="call_1",
            name="search_schema",
            arguments='{"query": "车牌"}'
        )

        mock_components["llm"].chat_with_tools.side_effect = [
            ChatResponse(content=None, tool_calls=[tc]),
            ChatResponse(
                content="找到了车牌信息表 cloud_fixed_plate，包含车牌号、状态等字段。",
                tool_calls=[]
            )
        ]

        # 执行查询
        result = orchestrator.process("有哪些车牌相关的表")

        # 验证结果
        assert result != "None"
        assert "cloud_fixed_plate" in result or "车牌" in result

    def test_list_operations_tool(self, orchestrator, mock_components):
        """测试列出操作工具

        场景：用户询问支持的操作
        预期：返回可用操作列表
        """
        from src.knowledge.knowledge_loader import Operation

        # 模拟操作列表
        operations = {
            "plate_query": Operation(
                id="plate_query",
                name="车牌查询",
                description="查询车牌信息",
                keywords=["车牌"],
                category="query"
            ),
            "plate_distribute": Operation(
                id="plate_distribute",
                name="车牌下发",
                description="下发车牌到园区",
                keywords=["车牌", "下发"],
                category="mutation"
            )
        }
        mock_components["knowledge"].get_all_operations.return_value = operations

        # 模拟 LLM 调用工具
        tc = ToolCall(
            id="call_1",
            name="list_operations",
            arguments='{}'
        )

        mock_components["llm"].chat_with_tools.side_effect = [
            ChatResponse(content=None, tool_calls=[tc]),
            ChatResponse(
                content="当前支持以下操作：\n1. 车牌查询 - 查询车牌信息\n2. 车牌下发 - 下发车牌到园区",
                tool_calls=[]
            )
        ]

        # 执行查询
        result = orchestrator.process("你能执行哪些操作")

        # 验证结果
        assert result != "None"
        assert "操作" in result or "车牌" in result