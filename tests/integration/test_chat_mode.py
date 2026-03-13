# tests/integration/test_chat_mode.py
"""chat 模式集成测试

验证 chat 模式完整流程：
1. 用户输入 -> IntentAgent 识别为 chat/qa
2. RetrievalAgent 检索 schema 上下文
3. KnowledgeAgent 生成流式响应
4. execution_result 包含有意义的内容
"""
import pytest
import types
from unittest.mock import MagicMock, patch

from src.agents.orchestrator import Orchestrator
from src.agents.context import AgentContext, IntentModel
from src.agents.models import AgentResult


@pytest.fixture
def orchestrator_for_chat():
    """创建用于 chat 模式测试的 Orchestrator"""
    mock_intent = MagicMock()
    mock_retrieval = MagicMock()
    mock_knowledge = MagicMock()
    mock_security = MagicMock()
    mock_preview = MagicMock()
    mock_execution = MagicMock()

    orch = Orchestrator(
        intent_agent=mock_intent,
        retrieval_agent=mock_retrieval,
        knowledge_agent=mock_knowledge,
        security_agent=mock_security,
        preview_agent=mock_preview,
        execution_agent=mock_execution
    )

    return orch, mock_intent, mock_retrieval, mock_knowledge


class TestChatModeIntegration:
    """测试 chat 模式完整流程"""

    def test_chat_returns_meaningful_response(self, orchestrator_for_chat):
        """chat 模式应返回有意义的内容，而不是 None"""
        orch, mock_intent, mock_retrieval, mock_knowledge = orchestrator_for_chat

        # Mock IntentAgent 返回 chat 类型
        def intent_side_effect(context):
            context.intent = IntentModel(
                type="chat",
                confidence=0.95,
                need_clarify=False
            )
            return AgentResult(success=True, data=context.intent)

        mock_intent.run.side_effect = intent_side_effect

        # Mock RetrievalAgent
        mock_retrieval.run.return_value = AgentResult(success=True)

        # Mock KnowledgeAgent 返回 generator
        def mock_generator():
            yield {"type": "thinking", "content": "思考中..."}
            yield {"type": "content", "content": "我是通用 MySQL 助手，可以帮助你查询数据、理解表结构并生成 SQL。"}

        mock_knowledge.run.return_value = AgentResult(
            success=True,
            data=mock_generator()
        )

        # 执行
        context = orch.process("你可以帮我做什么")

        # 验证：execution_result 不是 None
        assert context.execution_result is not None
        assert context.execution_result != "None"
        assert "intent" in context.step_history
        assert "retrieval" in context.step_history
        assert "knowledge" in context.step_history

        # 验证：execution_result 是 generator
        assert isinstance(context.execution_result, types.GeneratorType)

        # 消费 generator 验证内容
        chunks = list(context.execution_result)
        assert len(chunks) > 0

        # 验证：有 content 类型的 chunk
        content_chunks = [c for c in chunks if c.get("type") == "content"]
        assert len(content_chunks) > 0
        assert content_chunks[0]["content"] != ""
        # 能力类问法不应出现停车领域硬编码
        assert "停车" not in content_chunks[0]["content"]
        assert "智能停车" not in content_chunks[0]["content"]
        assert "parking" not in content_chunks[0]["content"].lower()

    def test_chat_handles_knowledge_agent_failure(self, orchestrator_for_chat):
        """chat 模式在 KnowledgeAgent 失败时应返回有意义的错误消息"""
        orch, mock_intent, mock_retrieval, mock_knowledge = orchestrator_for_chat

        # Mock IntentAgent 返回 chat 类型
        def intent_side_effect(context):
            context.intent = IntentModel(
                type="chat",
                confidence=0.95,
                need_clarify=False
            )
            return AgentResult(success=True, data=context.intent)

        mock_intent.run.side_effect = intent_side_effect
        mock_retrieval.run.return_value = AgentResult(success=True)

        # Mock KnowledgeAgent 失败
        mock_knowledge.run.return_value = AgentResult(
            success=False,
            message="对话服务暂时不可用",
            data=None
        )

        # 执行
        context = orch.process("你好")

        # 验证：返回有意义的错误消息
        assert context.execution_result is not None
        assert context.execution_result == "对话服务暂时不可用"
        assert "knowledge_failed" in context.step_history

    def test_chat_handles_knowledge_agent_null_data(self, orchestrator_for_chat):
        """chat 模式在 KnowledgeAgent 返回 null data 时应有降级处理"""
        orch, mock_intent, mock_retrieval, mock_knowledge = orchestrator_for_chat

        # Mock IntentAgent 返回 chat 类型
        def intent_side_effect(context):
            context.intent = IntentModel(
                type="chat",
                confidence=0.95,
                need_clarify=False
            )
            return AgentResult(success=True, data=context.intent)

        mock_intent.run.side_effect = intent_side_effect
        mock_retrieval.run.return_value = AgentResult(success=True)

        # Mock KnowledgeAgent 返回 None data
        mock_knowledge.run.return_value = AgentResult(
            success=True,
            data=None,
            message="knowledge_stream_ready"
        )

        # 执行
        context = orch.process("你好")

        # 验证：返回降级消息
        assert context.execution_result is not None
        assert context.execution_result == "对话服务暂时不可用，请稍后再试。"
        assert "knowledge_failed" in context.step_history

    def test_qa_mode_returns_streaming_response(self, orchestrator_for_chat):
        """qa 模式应返回流式响应"""
        orch, mock_intent, mock_retrieval, mock_knowledge = orchestrator_for_chat

        # Mock IntentAgent 返回 qa 类型
        def intent_side_effect(context):
            context.intent = IntentModel(
                type="qa",
                confidence=0.95,
                need_clarify=False
            )
            return AgentResult(success=True, data=context.intent)

        mock_intent.run.side_effect = intent_side_effect
        mock_retrieval.run.return_value = AgentResult(success=True)

        # Mock KnowledgeAgent 返回有内容的 generator
        def mock_generator():
            yield {"type": "content", "content": "数据库包含以下表："}
            yield {"type": "content", "content": "vehicle_info（车辆信息表）"}

        mock_knowledge.run.return_value = AgentResult(
            success=True,
            data=mock_generator()
        )

        # 执行
        context = orch.process("数据库有哪些表？")

        # 验证
        assert context.execution_result is not None
        assert isinstance(context.execution_result, types.GeneratorType)

        chunks = list(context.execution_result)
        content_chunks = [c for c in chunks if c.get("type") == "content"]
        assert len(content_chunks) >= 2

        # 验证：内容组合有意义
        full_content = "".join(c["content"] for c in content_chunks)
        assert "数据库" in full_content or "表" in full_content


class TestChatModeWithRealAgents:
    """使用真实 Agent 进行更深入的集成测试"""

    @patch('src.llm_client.Generation.call')
    def test_intent_agent_recognizes_chat_intent(self, mock_call):
        """IntentAgent 应正确识别 chat 意图"""
        from src.agents.impl.intent_agent import IntentAgent
        from src.agents.config import IntentAgentConfig
        from src.llm_client import LLMClient

        # Mock LLM 响应
        mock_chunk = MagicMock()
        mock_chunk.output.choices = [MagicMock()]
        mock_chunk.output.choices[0].message.content = '{"operation_id": "general_chat", "params": {}, "confidence": 0.95}'
        mock_call.return_value = iter([mock_chunk])

        llm = LLMClient.__new__(LLMClient)
        llm.api_key = "test-key"
        llm.client = None
        llm._metrics_collector = MagicMock()

        intent_agent = IntentAgent(
            IntentAgentConfig(name="intent"),
            llm_client=llm
        )

        context = AgentContext(user_input="你好")
        result = intent_agent.run(context)

        assert result.success
        assert context.intent is not None
        assert context.intent.type in ["chat", "clarify"]

    def test_knowledge_agent_generates_stream(self):
        """KnowledgeAgent 应生成流式响应"""
        from src.agents.impl.knowledge_agent import KnowledgeAgent
        from src.agents.config import BaseAgentConfig

        # 创建带有 mock LLM 的 KnowledgeAgent
        mock_llm = MagicMock()

        def mock_stream(*args, **kwargs):
            yield {"type": "content", "content": "测试响应"}

        mock_llm.chat_stream.return_value = mock_stream()

        knowledge_agent = KnowledgeAgent(
            BaseAgentConfig(name="knowledge"),
            llm_client=mock_llm
        )

        context = AgentContext(user_input="测试问题")
        context.intent = IntentModel(type="chat", confidence=0.95)

        result = knowledge_agent.run(context)

        assert result.success
        assert result.data is not None

        # 验证是 generator
        chunks = list(result.data)
        assert len(chunks) > 0
        assert chunks[0]["type"] == "content"