<<<<<<< HEAD
# tests/integration/test_dialogue_orchestrator_integration.py
"""
集成测试：对话引擎与Orchestrator集成

测试完整流程：
1. 完整对话流程（chat -> KnowledgeAgent）
2. 概念学习流程（clarify -> learn -> continue）
3. 业务操作流程（query -> retrieval -> security -> execution）
"""
import pytest
import types
from unittest.mock import MagicMock

from src.agents.orchestrator import Orchestrator
from src.agents.context import AgentContext, IntentModel
from src.agents.models import AgentResult
=======
"""对话引擎与 Orchestrator 集成测试

测试对话引擎与多智能体架构融合的完整流程：
1. 完整对话流程：普通对话 -> 知识问答 -> 业务操作
2. 概念学习流程：未知概念 -> 澄清 -> 学习 -> 继续
3. 业务操作流程：query -> retrieval -> security -> execution
"""
import pytest
import types
from unittest.mock import patch, MagicMock
from src.agents.orchestrator import Orchestrator
from src.agents.context import AgentContext, IntentModel
from src.agents.models import AgentResult
from src.llm_client import LLMClient
from src.knowledge.knowledge_loader import KnowledgeLoader
from src.memory.concept_store import ConceptStoreService
from src.dialogue.concept_recognizer import RecognizedConcept
from src.dialogue.question_generator import ClarificationQuestion
>>>>>>> af1cecf (test(integration): 添加对话引擎与Orchestrator集成的完整流程测试)


@pytest.fixture
def orchestrator_with_mocks():
<<<<<<< HEAD
    """创建带mock的Orchestrator用于集成测试"""
    mock_intent = MagicMock()
    mock_retrieval = MagicMock()
    mock_knowledge = MagicMock()
    mock_security = MagicMock()
    mock_preview = MagicMock()
    mock_execution = MagicMock()

    # 默认返回成功
    mock_intent.run.return_value = AgentResult(success=True)
    mock_retrieval.run.return_value = AgentResult(success=True)
    mock_knowledge.run.return_value = AgentResult(success=True)
    mock_security.run.return_value = AgentResult(success=True)
    mock_preview.run.return_value = AgentResult(success=True)
    mock_execution.run.return_value = AgentResult(success=True)

    orch = Orchestrator(
        intent_agent=mock_intent,
        retrieval_agent=mock_retrieval,
        knowledge_agent=mock_knowledge,
        security_agent=mock_security,
        preview_agent=mock_preview,
        execution_agent=mock_execution
    )

    return orch, mock_intent, mock_retrieval, mock_knowledge, mock_security, mock_preview, mock_execution


class TestFullConversationFlow:
    """测试完整对话流程"""

    def test_full_conversation_flow(self, orchestrator_with_mocks):
        """测试完整对话流程：普通对话 -> 知识问答"""
        orch, mock_intent, mock_retrieval, mock_knowledge, mock_security, mock_preview, mock_execution = orchestrator_with_mocks

        # Mock intent返回chat类型
        def intent_side_effect(context):
            context.intent = IntentModel(type="chat", confidence=0.95, need_clarify=False)
            return AgentResult(success=True, data=context.intent)

        mock_intent.run.side_effect = intent_side_effect

        # Mock knowledge返回generator
        def mock_generator():
            yield {"type": "content", "content": "你好！"}

        mock_knowledge.run.return_value = AgentResult(
            success=True,
            data=mock_generator()
        )

        context = orch.process("你好")

        assert "intent" in context.step_history
        assert "retrieval" in context.step_history
        assert "knowledge" in context.step_history
        assert isinstance(context.execution_result, types.GeneratorType)

        # 消费generator
        chunks = list(context.execution_result)
        assert len(chunks) > 0


class TestConceptLearningFlow:
    """测试概念学习流程"""

    def test_concept_learning_flow_trigger_clarification(self, orchestrator_with_mocks):
        """测试概念学习流程：触发澄清"""
        orch, mock_intent, mock_retrieval, mock_knowledge, mock_security, mock_preview, mock_execution = orchestrator_with_mocks

        # Mock intent返回需要澄清
        def intent_side_effect(context):
            context.intent = IntentModel(
                type="clarify",
                confidence=0.0,
                need_clarify=True,
                clarification_question="请问ROI具体指什么？",
                unrecognized_concepts=["ROI"]
            )
            return AgentResult(success=True, data=context.intent)

        mock_intent.run.side_effect = intent_side_effect

        context = orch.process("查询ROI")

        assert context.pending_clarification is True
        assert context.intent is not None
        assert "ROI" in context.intent.unrecognized_concepts

    def test_concept_learning_flow_continue_after_clarification(self, orchestrator_with_mocks):
        """测试概念学习流程：澄清后继续"""
        orch, mock_intent, mock_retrieval, mock_knowledge, mock_security, mock_preview, mock_execution = orchestrator_with_mocks

        chat_history = [
            {"role": "assistant", "content": "请问ROI具体指什么？"},
            {"role": "user", "content": "投资回报率"}
        ]

        # Mock intent返回query类型（澄清后）
        def intent_side_effect(context):
            context.intent = IntentModel(
                type="query",
                confidence=0.9,
                need_clarify=False,
                operation_id="plate_query"
            )
            return AgentResult(success=True, data=context.intent)

        mock_intent.run.side_effect = intent_side_effect

        context = orch.process("投资回报率", chat_history=chat_history)

        # 验证继续执行业务流程
        assert context.pending_clarification is False
        assert "intent" in context.step_history
        assert "retrieval" in context.step_history
        assert "security" in context.step_history
        assert "execution" in context.step_history


class TestBusinessOperationFlow:
    """测试业务操作流程"""

    def test_business_operation_query_flow(self, orchestrator_with_mocks):
        """测试业务操作流程：query -> retrieval -> security -> execution"""
        orch, mock_intent, mock_retrieval, mock_knowledge, mock_security, mock_preview, mock_execution = orchestrator_with_mocks

        # Mock intent返回query类型
        def intent_side_effect(context):
            context.intent = IntentModel(
                type="query",
                confidence=0.95,
                need_clarify=False,
                operation_id="plate_query",
                params={"plate": "沪A12345"}
            )
            return AgentResult(success=True, data=context.intent)

        mock_intent.run.side_effect = intent_side_effect

        context = orch.process("查询车牌沪A12345")

        # 验证完整业务流程
        assert "intent" in context.step_history
        assert "retrieval" in context.step_history
        assert "security" in context.step_history
        assert "execution" in context.step_history

    def test_business_operation_mutation_flow(self, orchestrator_with_mocks):
        """测试业务操作流程：mutation包含preview"""
        orch, mock_intent, mock_retrieval, mock_knowledge, mock_security, mock_preview, mock_execution = orchestrator_with_mocks

        # Mock intent返回mutation类型
        def intent_side_effect(context):
            context.intent = IntentModel(
                type="mutation",
                confidence=0.95,
                need_clarify=False,
                operation_id="plate_update",
                params={"plate": "沪A12345", "status": "已年检"}
            )
            return AgentResult(success=True, data=context.intent)

        mock_intent.run.side_effect = intent_side_effect

        context = orch.process("更新车牌沪A12345状态为已年检")

        # 验证mutation流程（包含preview）
        assert "intent" in context.step_history
        assert "retrieval" in context.step_history
        assert "security" in context.step_history
        assert "preview" in context.step_history
        assert "execution" in context.step_history


class TestKnowledgeQAFlow:
    """测试知识问答流程"""

    def test_knowledge_qa_flow(self, orchestrator_with_mocks):
        """测试知识问答流程：qa -> retrieval -> knowledge"""
        orch, mock_intent, mock_retrieval, mock_knowledge, mock_security, mock_preview, mock_execution = orchestrator_with_mocks

        # Mock intent返回qa类型
        def intent_side_effect(context):
            context.intent = IntentModel(type="qa", confidence=0.95, need_clarify=False)
            return AgentResult(success=True, data=context.intent)

        mock_intent.run.side_effect = intent_side_effect

        # Mock KnowledgeAgent返回generator
        def mock_generator():
            yield {"type": "thinking", "content": "思考中..."}
            yield {"type": "content", "content": "根据数据库结构..."}

        mock_knowledge.run.return_value = AgentResult(
            success=True,
            data=mock_generator()
        )

        context = orch.process("数据库有哪些表？")

        # 验证知识问答流程
        assert "intent" in context.step_history
        assert "retrieval" in context.step_history
        assert "knowledge" in context.step_history
        assert isinstance(context.execution_result, types.GeneratorType)
=======
    """创建带 mock 的 Orchestrator 用于集成测试"""
    from src.dialogue.concept_recognizer import ConceptRecognizer
    from src.dialogue.question_generator import QuestionGenerator
    
    mock_llm = MagicMock(spec=LLMClient)
    mock_knowledge = MagicMock(spec=KnowledgeLoader)
    mock_concept_store = MagicMock(spec=ConceptStoreService)
    
    orch = Orchestrator(
        llm_client=mock_llm,
        knowledge_loader=mock_knowledge
    )
    
    # 注入 concept_store 和初始化概念学习组件
    orch.intent_agent.concept_store = mock_concept_store
    orch.intent_agent.concept_recognizer = ConceptRecognizer(mock_concept_store)
    orch.intent_agent.question_generator = QuestionGenerator()
    
    return orch, mock_llm, mock_knowledge, mock_concept_store


def test_full_conversation_flow(orchestrator_with_mocks):
    """测试完整对话流程：普通对话 -> 知识问答 -> 业务操作"""
    orch, mock_llm, mock_knowledge, mock_concept_store = orchestrator_with_mocks
    
    # 场景1：普通对话
    # Mock IntentRecognizer 识别为 chat
    with patch.object(orch.intent_agent.recognizer, 'recognize') as mock_recognize:
        mock_result = MagicMock()
        mock_result.operation_id = "general_chat"
        mock_result.is_matched = True
        mock_result.confidence = 0.95
        mock_result.params = {}
        mock_result.missing_params = []
        mock_result.reasoning = ""
        mock_result.fallback_sql = None
        mock_recognize.return_value = mock_result
        
        # Mock KnowledgeAgent 返回 generator
        def mock_generator():
            yield {"type": "content", "content": "你好！"}
            yield {"type": "content", "content": "我是你的助手。"}
        
        with patch.object(orch.knowledge_agent, '_run_impl') as mock_knowledge_run:
            mock_knowledge_run.return_value = AgentResult(
                success=True,
                data=mock_generator()
            )
            
            context = orch.process("你好")
            
            # 验证路由到 knowledge agent
            assert "knowledge" in context.step_history
            assert isinstance(context.execution_result, types.GeneratorType)
            
            # 消费 generator
            chunks = list(context.execution_result)
            assert len(chunks) == 2
            assert chunks[0]["content"] == "你好！"


def test_concept_learning_flow(orchestrator_with_mocks):
    """测试概念学习流程：未知概念 -> 澄清 -> 学习 -> 继续"""
    orch, mock_llm, mock_knowledge, mock_concept_store = orchestrator_with_mocks
    
    # 第一次：触发澄清
    unknown_concept = RecognizedConcept(
        term="ROI",
        position=(0, 3),
        context="查询ROI",
        matched_concept_id=None,
        needs_clarification=True
    )
    
    with patch.object(orch.intent_agent.concept_recognizer, 'recognize') as mock_recog:
        mock_recog.return_value = [unknown_concept]
        
        question = ClarificationQuestion(
            concept_term="ROI",
            question="请问ROI具体指什么？",
            options=["投资回报率", "其他"],
            question_type="clarification"
        )
        
        with patch.object(orch.intent_agent.question_generator, 'generate_clarification_question') as mock_gen:
            mock_gen.return_value = question
            
            context = orch.process("查询ROI")
            
            # 验证澄清状态
            assert context.pending_clarification is True
            assert context.intent.clarification_question == "请问ROI具体指什么？"
            assert "ROI" in context.intent.unrecognized_concepts
            assert context.intent.type == "clarify"
    
    # 第二次：学习并继续
    chat_history = [
        {"role": "assistant", "content": "请问ROI具体指什么？"},
        {"role": "user", "content": "投资回报率"}
    ]
    
    # Mock concept_recognizer 不再返回未识别概念
    with patch.object(orch.intent_agent.concept_recognizer, 'recognize') as mock_recog:
        mock_recog.return_value = []
        
        with patch.object(orch.intent_agent.recognizer, 'recognize') as mock_recognize:
            mock_result = MagicMock()
            mock_result.operation_id = "plate_query"
            mock_result.is_matched = True
            mock_result.confidence = 0.9
            mock_result.params = {}
            mock_result.missing_params = []
            mock_result.reasoning = ""
            mock_result.fallback_sql = "SELECT * FROM plates"
            mock_recognize.return_value = mock_result
            
            # Mock security agent
            with patch.object(orch.security_agent, 'run') as mock_security:
                mock_security.return_value = AgentResult(success=True)
                
                # Mock execution agent
                with patch.object(orch.execution_agent, 'run') as mock_execution:
                    mock_execution.return_value = AgentResult(success=True)
                    
                    context = orch.process("投资回报率", chat_history=chat_history)
                    
                    # 验证概念已学习
                    mock_concept_store.add_concept.assert_called()
                    
                    # 验证继续执行业务流程
                    assert context.pending_clarification is False
                    assert "execution" in context.step_history


def test_business_operation_flow(orchestrator_with_mocks):
    """测试业务操作流程：query -> retrieval -> security -> execution"""
    orch, mock_llm, mock_knowledge, mock_concept_store = orchestrator_with_mocks
    
    with patch.object(orch.intent_agent.recognizer, 'recognize') as mock_recognize:
        mock_result = MagicMock()
        mock_result.operation_id = "plate_query"
        mock_result.is_matched = True
        mock_result.confidence = 0.95
        mock_result.params = {"plate": "沪A12345"}
        mock_result.missing_params = []
        mock_result.reasoning = ""
        mock_result.fallback_sql = "SELECT * FROM plates WHERE plate='沪A12345'"
        mock_recognize.return_value = mock_result
        
        # Mock security agent
        with patch.object(orch.security_agent, 'run') as mock_security:
            mock_security.return_value = AgentResult(success=True)
            
            # Mock execution agent
            with patch.object(orch.execution_agent, 'run') as mock_execution:
                mock_execution.return_value = AgentResult(success=True)
                
                context = orch.process("查询车牌沪A12345")
                
                # 验证完整业务流程
                assert "intent" in context.step_history
                assert "retrieval" in context.step_history
                assert "security" in context.step_history
                assert "execution" in context.step_history
                
                # 验证意图类型
                assert context.intent.type == "query"
                assert context.intent.operation_id == "plate_query"
>>>>>>> af1cecf (test(integration): 添加对话引擎与Orchestrator集成的完整流程测试)
