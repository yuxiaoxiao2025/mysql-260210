import pytest
from src.agents.models import AgentResult
from src.agents.context import AgentContext, IntentModel
from src.agents.config import BaseAgentConfig, IntentAgentConfig, SecurityAgentConfig
from src.agents.base import BaseAgent


class TestAgentResult:
    """测试 AgentResult 模型"""

    def test_agent_result_all_fields(self):
        """测试 AgentResult 所有字段"""
        result = AgentResult(
            success=True,
            data={"key": "value"},
            message="操作成功",
            next_action="continue"
        )
        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.message == "操作成功"
        assert result.next_action == "continue"

    def test_agent_result_optional_none(self):
        """测试 AgentResult 可选字段为 None"""
        result = AgentResult(success=False)
        assert result.success is False
        assert result.data is None
        assert result.message is None
        assert result.next_action is None

    def test_agent_result_serialization(self):
        """测试 AgentResult 序列化"""
        result = AgentResult(success=True, data={"test": "data"})
        json_str = result.model_dump_json()
        assert "success" in json_str
        assert "test" in json_str


class TestIntentModel:
    """测试 IntentModel 模型"""

    def test_intent_model_all_fields(self):
        """测试 IntentModel 所有字段"""
        intent = IntentModel(
            type="query",
            confidence=0.95,
            params={"table": "users"},
            operation_id="op_123",
            reasoning="用户查询数据",
            sql="SELECT * FROM users",
            need_clarify=False
        )
        assert intent.type == "query"
        assert intent.confidence == 0.95
        assert intent.params == {"table": "users"}
        assert intent.operation_id == "op_123"
        assert intent.reasoning == "用户查询数据"
        assert intent.sql == "SELECT * FROM users"
        assert intent.need_clarify is False

    def test_intent_model_confidence_boundary(self):
        """测试 confidence 边界值"""
        # 边界值 0
        intent_min = IntentModel(type="query", confidence=0.0)
        assert intent_min.confidence == 0.0

        # 边界值 1
        intent_max = IntentModel(type="query", confidence=1.0)
        assert intent_max.confidence == 1.0

        # 中间值 0.5
        intent_mid = IntentModel(type="query", confidence=0.5)
        assert intent_mid.confidence == 0.5

    def test_intent_model_default_values(self):
        """测试 IntentModel 默认值"""
        intent = IntentModel(type="query")
        assert intent.confidence == 0.0
        assert intent.params == {}
        assert intent.operation_id is None
        assert intent.reasoning == ""
        assert intent.sql is None
        assert intent.need_clarify is False


class TestAgentContext:
    """测试 AgentContext 模型"""

    def test_agent_context_defaults(self):
        """测试 AgentContext 默认值"""
        ctx = AgentContext(user_input="hello")
        assert ctx.user_input == "hello"
        assert ctx.trace_id is not None
        assert ctx.step_history == []
        assert ctx.intent is None
        assert ctx.schema_context is None
        assert ctx.is_safe is None
        assert ctx.preview_data is None
        assert ctx.execution_result is None

    def test_agent_context_with_intent(self):
        """测试 AgentContext 包含意图"""
        intent = IntentModel(type="query", confidence=0.9)
        ctx = AgentContext(user_input="查询数据", intent=intent)
        assert ctx.intent is not None
        assert ctx.intent.type == "query"
        assert ctx.intent.confidence == 0.9


class TestBaseAgentConfig:
    """测试 BaseAgentConfig 及其子类"""

    def test_base_agent_config_defaults(self):
        """测试 BaseAgentConfig 默认值"""
        config = BaseAgentConfig(name="test_agent")
        assert config.name == "test_agent"
        assert config.enabled is True
        assert config.timeout == 30

    def test_intent_agent_config_inheritance(self):
        """测试 IntentAgentConfig 继承 BaseAgentConfig"""
        config = IntentAgentConfig(name="intent_agent")
        assert config.name == "intent_agent"
        assert config.enabled is True
        assert config.timeout == 30
        assert isinstance(config, BaseAgentConfig)

    def test_security_agent_config_inheritance(self):
        """测试 SecurityAgentConfig 继承 BaseAgentConfig"""
        config = SecurityAgentConfig(name="security_agent")
        assert config.name == "security_agent"
        assert config.enabled is True
        assert config.timeout == 30
        assert isinstance(config, BaseAgentConfig)


class TestBaseAgent:
    """测试 BaseAgent 基类"""

    def test_base_agent_implementation(self):
        """测试 BaseAgent 可子类化并实现 _run_impl"""
        class TestAgent(BaseAgent):
            def _run_impl(self, context):
                return AgentResult(success=True)

        agent = TestAgent(BaseAgentConfig(name="test"))
        assert agent.run(AgentContext(user_input="")).success is True

    def test_base_agent_config_access(self):
        """测试 BaseAgent 可以访问配置"""
        class TestAgent(BaseAgent):
            def _run_impl(self, context):
                return AgentResult(success=True)

        config = BaseAgentConfig(name="test_agent", enabled=False, timeout=60)
        agent = TestAgent(config)
        assert agent.config.name == "test_agent"
        assert agent.config.enabled is False
        assert agent.config.timeout == 60
