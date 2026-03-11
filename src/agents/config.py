"""Agent 配置定义"""
from pydantic import BaseModel, Field


class BaseAgentConfig(BaseModel):
    """基础 Agent 配置

    Attributes:
        name: Agent 名称
        enabled: 是否启用 (默认 True)
        timeout: 超时时间 (默认 30秒)
    """
    name: str = Field(..., description="Agent 名称")
    enabled: bool = Field(default=True, description="是否启用")
    timeout: int = Field(default=30, description="超时时间")


class IntentAgentConfig(BaseAgentConfig):
    """意图识别 Agent 配置"""
    # 继承自 BaseAgentConfig，可添加意图识别特定配置
    pass


class SecurityAgentConfig(BaseAgentConfig):
    """安全检查 Agent 配置"""
    # 继承自 BaseAgentConfig，可添加安全检查特定配置
    pass
