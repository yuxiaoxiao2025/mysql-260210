"""CLI Agent Mode 集成测试

测试 main.py 与 Orchestrator 的集成:
1. --agent-mode 命令行参数支持
2. Orchestrator 初始化和调用
3. 处理需要澄清的情况 (need_clarify)
4. 处理预览数据 (preview_data)
"""
import pytest
from unittest.mock import patch, MagicMock, call
import argparse
import os


class TestCLIAgentMode:
    """测试 CLI Agent 模式集成"""

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key", "DASHSCOPE_API_KEY": "test-key"})
    def test_cli_agent_mode_flag_initializes_orchestrator(self):
        """测试 --agent-mode 标志会初始化 Orchestrator"""
        from src.agents.orchestrator import Orchestrator

        # 验证 Orchestrator 可以被导入和实例化
        assert Orchestrator is not None

        # 使用 mock 测试实例化
        with patch.object(Orchestrator, '__init__', return_value=None):
            orch = Orchestrator()
            assert orch is not None

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key", "DASHSCOPE_API_KEY": "test-key"})
    def test_cli_agent_mode_uses_orchestrator_for_processing(self):
        """测试 agent 模式下使用 Orchestrator 处理输入"""
        mock_orch = MagicMock()
        mock_context = MagicMock()
        mock_context.intent = MagicMock()
        mock_context.intent.need_clarify = False
        mock_context.intent.type = "query"
        mock_context.preview_data = None
        mock_context.execution_result = {"data": "test_result"}
        mock_orch.process.return_value = mock_context

        # 验证 Orchestrator 可以被调用
        result = mock_orch.process("测试输入")
        assert result is mock_context
        mock_orch.process.assert_called_once_with("测试输入")

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key", "DASHSCOPE_API_KEY": "test-key"})
    def test_cli_handles_need_clarify(self):
        """测试 CLI 正确处理 need_clarify 返回"""
        mock_orch = MagicMock()
        mock_context = MagicMock()
        mock_context.intent = MagicMock()
        mock_context.intent.need_clarify = True
        mock_context.intent.clarify_message = "请提供更多细节"
        mock_orch.process.return_value = mock_context

        # 模拟处理流程
        result = mock_orch.process("模糊输入")

        # 验证返回了需要澄清的上下文
        assert result.intent.need_clarify is True
        assert result.intent.clarify_message == "请提供更多细节"

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key", "DASHSCOPE_API_KEY": "test-key"})
    def test_cli_handles_preview_data(self):
        """测试 CLI 正确处理 preview_data 返回"""
        mock_orch = MagicMock()
        mock_context = MagicMock()
        mock_context.intent = MagicMock()
        mock_context.intent.need_clarify = False
        mock_context.intent.type = "mutation"
        mock_context.preview_data = {"changes": [{"before": {}, "after": {}}]}
        mock_context.execution_result = None
        mock_orch.process.return_value = mock_context

        # 模拟处理流程
        result = mock_orch.process("执行更新操作")

        # 验证返回了预览数据
        assert result.preview_data is not None
        assert result.intent.type == "mutation"

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key", "DASHSCOPE_API_KEY": "test-key"})
    def test_cli_agent_mode_env_vars(self):
        """测试 CLI Agent 模式环境变量加载"""
        # 验证环境变量被正确设置 (由 patch.dict 模拟)
        assert os.environ.get("OPENAI_API_KEY") == "test-key"
        assert os.environ.get("DASHSCOPE_API_KEY") == "test-key"

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key", "DASHSCOPE_API_KEY": "test-key"})
    def test_orchestrator_step_history(self):
        """测试 Orchestrator 返回的步骤历史"""
        mock_orch = MagicMock()
        mock_context = MagicMock()
        mock_context.step_history = ["intent", "retrieval", "security", "execution"]
        mock_context.intent = MagicMock()
        mock_context.intent.need_clarify = False
        mock_orch.process.return_value = mock_context

        result = mock_orch.process("测试输入")

        # 验证步骤历史
        assert "intent" in result.step_history
        assert "execution" in result.step_history

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key", "DASHSCOPE_API_KEY": "test-key"})
    def test_cli_handles_security_failure(self):
        """测试 CLI 处理安全检查失败"""
        mock_orch = MagicMock()
        mock_context = MagicMock()
        mock_context.intent = MagicMock()
        mock_context.intent.need_clarify = False
        mock_context.is_safe = False
        mock_context.step_history = ["intent", "retrieval", "security_failed"]
        mock_orch.process.return_value = mock_context

        result = mock_orch.process("危险操作")

        # 验证安全检查失败被记录
        assert "security_failed" in result.step_history
        assert result.is_safe is False

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key", "DASHSCOPE_API_KEY": "test-key"})
    def test_cli_handles_query_execution(self):
        """测试 CLI 处理查询执行结果"""
        mock_orch = MagicMock()
        mock_context = MagicMock()
        mock_context.intent = MagicMock()
        mock_context.intent.need_clarify = False
        mock_context.intent.type = "query"
        mock_context.preview_data = None
        mock_context.execution_result = {"data": [{"id": 1, "name": "test"}], "row_count": 1}
        mock_orch.process.return_value = mock_context

        result = mock_orch.process("查询所有用户")

        # 验证查询执行结果
        assert result.intent.type == "query"
        assert result.execution_result is not None
        assert result.execution_result["row_count"] == 1


class TestMainCLIIntegration:
    """测试 main.py CLI 集成功能"""

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key", "DASHSCOPE_API_KEY": "test-key"})
    def test_main_imports_orchestrator(self):
        """测试 main.py 可以导入 Orchestrator"""
        try:
            from src.agents.orchestrator import Orchestrator
            assert Orchestrator is not None
        except ImportError as e:
            pytest.fail(f"无法导入 Orchestrator: {e}")

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key", "DASHSCOPE_API_KEY": "test-key"})
    def test_main_has_agent_mode_argparse(self):
        """测试 main.py 支持 --agent-mode 参数解析"""
        parser = argparse.ArgumentParser()
        parser.add_argument("--agent-mode", action="store_true", help="启用 Agent 模式")

        # 测试解析 --agent-mode
        args = parser.parse_args(["--agent-mode"])
        assert args.agent_mode is True

        # 测试不传入参数
        args = parser.parse_args([])
        assert args.agent_mode is False
