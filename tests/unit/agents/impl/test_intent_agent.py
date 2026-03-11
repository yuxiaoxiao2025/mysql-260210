"""Intent Agent 单元测试"""
from unittest.mock import MagicMock, patch
import pytest
from src.agents.impl.intent_agent import IntentAgent
from src.agents.config import IntentAgentConfig
from src.agents.context import AgentContext


@patch("src.agents.impl.intent_agent.IntentRecognizer")
def test_intent_agent_integration(mock_recognizer_cls):
    # Setup mock - 使用 RecognizedIntent 的数据结构
    mock_instance = mock_recognizer_cls.return_value
    mock_result = MagicMock()
    mock_result.operation_id = "users_query"
    mock_result.operation_name = "查询用户"
    mock_result.confidence = 0.95
    mock_result.params = {}
    mock_result.missing_params = []
    mock_result.fallback_sql = "SELECT * FROM users"
    mock_result.reasoning = "通过关键词匹配到操作: 查询用户"
    mock_result.suggestions = []
    mock_result.is_matched = True
    mock_instance.recognize.return_value = mock_result

    agent = IntentAgent(IntentAgentConfig(name="intent"), llm_client=None, knowledge_loader=None)
    context = AgentContext(user_input="show users")
    result = agent.run(context)

    assert result.success is True
    assert context.intent.type == "query"
    assert context.intent.confidence == 0.95
    assert context.intent.sql == "SELECT * FROM users"


class TestInferIntentType:
    """测试 _infer_intent_type 方法边界情况"""

    def test_operation_id_none_returns_clarify(self):
        """operation_id 为 None 时应返回 'clarify'"""
        agent = IntentAgent(IntentAgentConfig(name="intent"), llm_client=None, knowledge_loader=None)
        result = agent._infer_intent_type(None)
        assert result == "clarify"

    def test_operation_id_empty_string_returns_clarify(self):
        """operation_id 为空字符串时应返回 'clarify'"""
        agent = IntentAgent(IntentAgentConfig(name="intent"), llm_client=None, knowledge_loader=None)
        result = agent._infer_intent_type("")
        assert result == "clarify"

    def test_create_suffix_returns_mutation(self):
        """_create 后缀应返回 mutation 类型"""
        agent = IntentAgent(IntentAgentConfig(name="intent"), llm_client=None, knowledge_loader=None)
        result = agent._infer_intent_type("users_create")
        assert result == "mutation"

    def test_update_suffix_returns_mutation(self):
        """_update 后缀应返回 mutation 类型"""
        agent = IntentAgent(IntentAgentConfig(name="intent"), llm_client=None, knowledge_loader=None)
        result = agent._infer_intent_type("users_update")
        assert result == "mutation"

    def test_delete_suffix_returns_mutation(self):
        """_delete 后缀应返回 mutation 类型"""
        agent = IntentAgent(IntentAgentConfig(name="intent"), llm_client=None, knowledge_loader=None)
        result = agent._infer_intent_type("users_delete")
        assert result == "mutation"

    def test_insert_suffix_returns_mutation(self):
        """_insert 后缀应返回 mutation 类型"""
        agent = IntentAgent(IntentAgentConfig(name="intent"), llm_client=None, knowledge_loader=None)
        result = agent._infer_intent_type("users_insert")
        assert result == "mutation"

    def test_query_suffix_returns_query(self):
        """_query 后缀应返回 query 类型"""
        agent = IntentAgent(IntentAgentConfig(name="intent"), llm_client=None, knowledge_loader=None)
        result = agent._infer_intent_type("users_query")
        assert result == "query"

    def test_query_in_middle_returns_query(self):
        """_query_ 在中间应返回 query 类型"""
        agent = IntentAgent(IntentAgentConfig(name="intent"), llm_client=None, knowledge_loader=None)
        result = agent._infer_intent_type("users_query_active")
        assert result == "query"

    def test_unknown_suffix_returns_query_default(self):
        """未知后缀应返回默认 query 类型"""
        agent = IntentAgent(IntentAgentConfig(name="intent"), llm_client=None, knowledge_loader=None)
        result = agent._infer_intent_type("some_unknown_operation")
        assert result == "query"


class TestNeedClarifyLogic:
    """测试 need_clarify 逻辑"""

    @patch("src.agents.impl.intent_agent.IntentRecognizer")
    def test_low_confidence_sets_need_clarify_true(self, mock_recognizer_cls):
        """低置信度（< 0.6）时应设置 need_clarify=True"""
        mock_instance = mock_recognizer_cls.return_value
        mock_result = MagicMock()
        mock_result.operation_id = "users_query"
        mock_result.operation_name = "查询用户"
        mock_result.confidence = 0.5  # 低于默认阈值 0.6
        mock_result.params = {}
        mock_result.missing_params = []
        mock_result.fallback_sql = "SELECT * FROM users"
        mock_result.reasoning = "匹配但置信度低"
        mock_result.suggestions = []
        mock_result.is_matched = True
        mock_instance.recognize.return_value = mock_result

        agent = IntentAgent(IntentAgentConfig(name="intent"), llm_client=None, knowledge_loader=None)
        context = AgentContext(user_input="show users")
        agent.run(context)

        assert context.intent.need_clarify is True

    @patch("src.agents.impl.intent_agent.IntentRecognizer")
    def test_high_confidence_sets_need_clarify_false(self, mock_recognizer_cls):
        """高置信度（>= 0.6）时不应设置 need_clarify"""
        mock_instance = mock_recognizer_cls.return_value
        mock_result = MagicMock()
        mock_result.operation_id = "users_query"
        mock_result.operation_name = "查询用户"
        mock_result.confidence = 0.6  # 等于阈值
        mock_result.params = {}
        mock_result.missing_params = []
        mock_result.fallback_sql = "SELECT * FROM users"
        mock_result.reasoning = "匹配成功"
        mock_result.suggestions = []
        mock_result.is_matched = True
        mock_instance.recognize.return_value = mock_result

        agent = IntentAgent(IntentAgentConfig(name="intent"), llm_client=None, knowledge_loader=None)
        context = AgentContext(user_input="show users")
        agent.run(context)

        assert context.intent.need_clarify is False

    @patch("src.agents.impl.intent_agent.IntentRecognizer")
    def test_missing_params_sets_need_clarify_true(self, mock_recognizer_cls):
        """有缺失参数时应设置 need_clarify=True"""
        mock_instance = mock_recognizer_cls.return_value
        mock_result = MagicMock()
        mock_result.operation_id = "users_query"
        mock_result.operation_name = "查询用户"
        mock_result.confidence = 0.95
        mock_result.params = {}
        mock_result.missing_params = ["user_id"]  # 有缺失参数
        mock_result.fallback_sql = "SELECT * FROM users"
        mock_result.reasoning = "匹配但需要参数"
        mock_result.suggestions = []
        mock_result.is_matched = True
        mock_instance.recognize.return_value = mock_result

        agent = IntentAgent(IntentAgentConfig(name="intent"), llm_client=None, knowledge_loader=None)
        context = AgentContext(user_input="show user")
        agent.run(context)

        assert context.intent.need_clarify is True

    @patch("src.agents.impl.intent_agent.IntentRecognizer")
    def test_not_matched_sets_need_clarify_true(self, mock_recognizer_cls):
        """未匹配时应设置 need_clarify=True"""
        mock_instance = mock_recognizer_cls.return_value
        mock_result = MagicMock()
        mock_result.operation_id = ""
        mock_result.operation_name = ""
        mock_result.confidence = 0.0
        mock_result.params = {}
        mock_result.missing_params = []
        mock_result.fallback_sql = ""
        mock_result.reasoning = "未匹配到任何操作"
        mock_result.suggestions = []
        mock_result.is_matched = False  # 未匹配
        mock_instance.recognize.return_value = mock_result

        agent = IntentAgent(IntentAgentConfig(name="intent"), llm_client=None, knowledge_loader=None)
        context = AgentContext(user_input="random input")
        agent.run(context)

        assert context.intent.need_clarify is True

    @patch("src.agents.impl.intent_agent.IntentRecognizer")
    def test_custom_confidence_threshold(self, mock_recognizer_cls):
        """测试自定义置信度阈值"""
        mock_instance = mock_recognizer_cls.return_value
        mock_result = MagicMock()
        mock_result.operation_id = "users_query"
        mock_result.operation_name = "查询用户"
        mock_result.confidence = 0.7  # 低于自定义阈值 0.8
        mock_result.params = {}
        mock_result.missing_params = []
        mock_result.fallback_sql = "SELECT * FROM users"
        mock_result.reasoning = "匹配"
        mock_result.suggestions = []
        mock_result.is_matched = True
        mock_instance.recognize.return_value = mock_result

        # 使用自定义阈值 0.8
        agent = IntentAgent(
            IntentAgentConfig(name="intent", confidence_threshold=0.8),
            llm_client=None,
            knowledge_loader=None
        )
        context = AgentContext(user_input="show users")
        agent.run(context)

        assert context.intent.need_clarify is True
