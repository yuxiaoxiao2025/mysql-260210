"""Agent 基础模型定义"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Any, Optional, List


class AgentResult(BaseModel):
    """Agent 执行结果标准格式

    Attributes:
        success: 执行是否成功
        data: 执行返回的数据 (可选)
        message: 人类可读的消息 (可选)
        next_action: 建议的下一步操作 (可选)
    """
    model_config = ConfigDict(json_encoders={})

    success: bool = Field(..., description="执行是否成功")
    data: Optional[Any] = Field(default=None, description="执行返回的数据")
    message: Optional[str] = Field(default=None, description="人类可读的消息")
    next_action: Optional[str] = Field(default=None, description="建议的下一步操作")
