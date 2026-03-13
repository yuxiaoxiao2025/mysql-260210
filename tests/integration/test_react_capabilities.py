from unittest.mock import Mock

from src.llm_tool_models import ChatResponse, ToolCall
from src.react.orchestrator import MVPReACTOrchestrator
from src.react.tool_service import MVPToolService


def test_what_can_you_do_lists_tools_not_domain():
    llm = Mock()
    db = Mock()
    retrieval = Mock()
    executor = Mock()
    knowledge = Mock()
    knowledge.get_all_operations.return_value = {}
    tool_service = MVPToolService(db, retrieval, executor, knowledge)

    orchestrator = MVPReACTOrchestrator(llm, tool_service)

    tc = ToolCall(id="1", name="list_capabilities", arguments="{}")
    llm.chat_with_tools.side_effect = [
        ChatResponse(content=None, tool_calls=[tc]),
        ChatResponse(content="我可以通过工具查看表结构、索引、执行只读查询并分析 EXPLAIN。", tool_calls=[]),
    ]

    out = orchestrator.process("你可以干什么？")

    assert "停车" not in out
    assert "parking" not in out.lower()
    assert "工具" in out or "EXPLAIN" in out

