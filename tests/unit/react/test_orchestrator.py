"""测试 MVP Orchestrator"""
import pytest
from unittest.mock import Mock, MagicMock
from src.react.orchestrator import MVPReACTOrchestrator, ConversationState
from src.llm_tool_models import ChatResponse, ToolCall


@pytest.fixture
def orchestrator():
    """创建编排器实例"""
    llm = Mock()
    tools = Mock()
    return MVPReACTOrchestrator(llm, tools)


class TestConversationState:
    """测试 ConversationState 数据类"""

    def test_default_values(self):
        """测试默认值"""
        state = ConversationState()
        assert state.messages == []
        assert state.pending_confirmation is False
        assert state.confirmation_type == ""
        assert state.confirmation_data == {}

    def test_custom_values(self):
        """测试自定义值"""
        state = ConversationState(
            messages=[{"role": "user", "content": "test"}],
            pending_confirmation=True,
            confirmation_type="sql",
            confirmation_data={"sql": "UPDATE ..."}
        )
        assert len(state.messages) == 1
        assert state.pending_confirmation is True
        assert state.confirmation_type == "sql"


class TestMVPReACTOrchestrator:
    """测试 MVPReACTOrchestrator 类"""

    def test_init(self, orchestrator):
        """测试初始化"""
        assert orchestrator.llm is not None
        assert orchestrator.tools is not None
        assert orchestrator.max_iterations == 5
        assert isinstance(orchestrator.state, ConversationState)

    def test_init_custom_iterations(self):
        """测试自定义最大迭代次数"""
        llm = Mock()
        tools = Mock()
        orchestrator = MVPReACTOrchestrator(llm, tools, max_iterations=10)
        assert orchestrator.max_iterations == 10

    def test_process_without_tools(self, orchestrator):
        """测试无工具调用的处理"""
        orchestrator.llm.chat_with_tools.return_value = ChatResponse(
            content="你好，我是助手",
            tool_calls=[]
        )

        result = orchestrator.process("你好")

        assert result == "你好，我是助手"
        assert len(orchestrator.state.messages) == 2  # user + assistant

    def test_process_with_tools(self, orchestrator):
        """测试有工具调用的处理"""
        # 第一次返回工具调用
        tc = ToolCall(id="1", name="search_schema", arguments='{"query": "车牌"}')
        orchestrator.llm.chat_with_tools.side_effect = [
            ChatResponse(content=None, tool_calls=[tc]),
            ChatResponse(content="找到车牌表", tool_calls=[])
        ]
        orchestrator.tools.execute.return_value = "找到 cloud_fixed_plate 表"

        result = orchestrator.process("查找车牌表")

        assert "车牌表" in result
        assert orchestrator.tools.execute.called

    def test_process_empty_response(self, orchestrator):
        """测试空响应"""
        orchestrator.llm.chat_with_tools.return_value = ChatResponse(
            content=None,
            tool_calls=[]
        )

        result = orchestrator.process("测试")

        assert result == "抱歉，我没有理解您的问题。"

    def test_confirmation_flow_sql(self, orchestrator):
        """测试 SQL 确认流程"""
        tc = ToolCall(id="1", name="execute_sql", arguments='{"sql": "UPDATE users SET age=20"}')
        orchestrator.llm.chat_with_tools.return_value = ChatResponse(
            content=None,
            tool_calls=[tc]
        )
        orchestrator.tools.execute.return_value = "__NEED_CONFIRM__\n操作：更新数据\nSQL：UPDATE users SET age=20"

        result = orchestrator.process("更新数据")

        assert "确认执行" in result
        assert orchestrator.state.pending_confirmation
        assert orchestrator.state.confirmation_type == "sql"

        # 用户确认
        orchestrator.tools.confirm_and_execute_sql.return_value = "执行成功，影响 1 行。"
        confirm_result = orchestrator.confirm(True)

        assert "执行成功" in confirm_result
        assert orchestrator.tools.confirm_and_execute_sql.called
        assert not orchestrator.state.pending_confirmation

    def test_confirmation_flow_operation(self, orchestrator):
        """测试操作确认流程"""
        tc = ToolCall(id="1", name="execute_operation", arguments='{"operation_id": "plate_distribute"}')
        orchestrator.llm.chat_with_tools.return_value = ChatResponse(
            content=None,
            tool_calls=[tc]
        )
        orchestrator.tools.execute.return_value = "__NEED_CONFIRM__\n操作：下发车牌\n预览：即将执行"

        result = orchestrator.process("下发车牌")

        assert "确认执行" in result
        assert orchestrator.state.pending_confirmation
        assert orchestrator.state.confirmation_type == "operation"

        # 用户确认
        orchestrator.tools.confirm_and_execute_operation.return_value = "操作成功"
        confirm_result = orchestrator.confirm(True)

        assert "操作成功" in confirm_result
        assert not orchestrator.state.pending_confirmation

    def test_user_cancel_confirmation(self, orchestrator):
        """测试用户取消确认"""
        tc = ToolCall(id="1", name="execute_sql", arguments='{"sql": "UPDATE ..."}')
        orchestrator.llm.chat_with_tools.return_value = ChatResponse(
            content=None,
            tool_calls=[tc]
        )
        orchestrator.tools.execute.return_value = "__NEED_CONFIRM__\n操作：更新"

        orchestrator.process("更新数据")
        result = orchestrator.confirm(False)

        assert "取消" in result
        assert not orchestrator.state.pending_confirmation
        assert orchestrator.state.confirmation_data == {}

    def test_add_tool_results(self, orchestrator):
        """测试添加工具结果到消息"""
        tc = ToolCall(id="call_123", name="search_schema", arguments='{"query": "test"}')
        results = ["找到相关表"]

        orchestrator._add_tool_results([tc], results)

        # 应该添加两条消息：assistant (tool_calls) + tool result
        assert len(orchestrator.state.messages) == 2

        # 验证 assistant 消息
        assistant_msg = orchestrator.state.messages[0]
        assert assistant_msg["role"] == "assistant"
        assert assistant_msg["content"] is None
        assert "tool_calls" in assistant_msg

        # 验证 tool 消息
        tool_msg = orchestrator.state.messages[1]
        assert tool_msg["role"] == "tool"
        assert tool_msg["tool_call_id"] == "call_123"
        assert tool_msg["content"] == "找到相关表"

    def test_execute_tools_with_json_parse_error(self, orchestrator):
        """测试工具参数 JSON 解析错误"""
        tc = ToolCall(id="1", name="search_schema", arguments='invalid json')
        orchestrator.tools.execute.return_value = "结果"

        results = orchestrator._execute_tools([tc])

        # 应该使用空参数调用
        assert len(results) == 1
        orchestrator.tools.execute.assert_called_once_with("search_schema", {})

    def test_execute_tools_unknown_tool(self, orchestrator):
        """测试未知工具"""
        tc = ToolCall(id="1", name="unknown_tool", arguments='{}')
        orchestrator.tools.execute.return_value = "错误：未知工具 unknown_tool"

        results = orchestrator._execute_tools([tc])

        assert "未知工具" in results[0]

    def test_max_iterations_reached(self, orchestrator):
        """测试达到最大迭代次数"""
        # 总是返回工具调用
        tc = ToolCall(id="1", name="search_schema", arguments='{"query": "test"}')
        orchestrator.llm.chat_with_tools.return_value = ChatResponse(
            content=None,
            tool_calls=[tc]
        )
        orchestrator.tools.execute.return_value = "结果"

        result = orchestrator.process("测试")

        assert "更多时间" in result

    def test_reset(self, orchestrator):
        """测试重置对话状态"""
        orchestrator.state.messages = [{"role": "user", "content": "test"}]
        orchestrator.state.pending_confirmation = True
        orchestrator.state.confirmation_data = {"key": "value"}

        orchestrator.reset()

        assert orchestrator.state.messages == []
        assert not orchestrator.state.pending_confirmation
        assert orchestrator.state.confirmation_data == {}

    def test_process_preserves_conversation_history(self, orchestrator):
        """测试对话历史保存"""
        orchestrator.llm.chat_with_tools.return_value = ChatResponse(
            content="回复1",
            tool_calls=[]
        )

        orchestrator.process("消息1")
        orchestrator.process("消息2")

        # 应该有 4 条消息：user1 + assistant1 + user2 + assistant2
        assert len(orchestrator.state.messages) == 4

    def test_format_confirmation_request(self, orchestrator):
        """测试格式化确认请求"""
        orchestrator.state.confirmation_data = {
            "preview": "操作：更新数据\nSQL：UPDATE ..."
        }
        orchestrator.state.pending_confirmation = True

        result = orchestrator._format_confirmation_request()

        assert "操作：更新数据" in result
        assert "确认执行" in result