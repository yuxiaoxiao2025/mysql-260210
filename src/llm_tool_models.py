"""LLM 工具调用相关模型"""
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ToolCall:
    """工具调用"""
    id: str
    name: str
    arguments: str  # JSON string

    @classmethod
    def from_openai(cls, tool_call) -> "ToolCall":
        """从 OpenAI 格式创建 ToolCall"""
        return cls(
            id=tool_call.id,
            name=tool_call.function.name,
            arguments=tool_call.function.arguments
        )


@dataclass
class ChatResponse:
    """对话响应"""
    content: Optional[str] = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"

    @property
    def has_tool_calls(self) -> bool:
        """检查是否有工具调用"""
        return bool(self.tool_calls)