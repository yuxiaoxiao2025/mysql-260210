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
            id=getattr(tool_call, "id", None),
            name=getattr(getattr(tool_call, "function", None), "name", None),
            arguments=getattr(getattr(tool_call, "function", None), "arguments", "{}")
        )

    @classmethod
    def from_dict(cls, tool_call: dict) -> "ToolCall":
        """从 DashScope/OpenAI 字典格式创建 ToolCall"""
        # 支持两种常见结构：
        # 1) {"id": "...", "type": "function", "function": {"name": "...", "arguments": "{...}"}}
        # 2) {"function": {"name": "...", "arguments": "{...}"}}  // 无 id
        func = tool_call.get("function", {}) if isinstance(tool_call, dict) else {}
        return cls(
            id=tool_call.get("id") or "",
            name=func.get("name") or "",
            arguments=func.get("arguments") or "{}"
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