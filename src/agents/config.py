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
    """意图识别 Agent 配置

    Attributes:
        confidence_threshold: 置信度阈值，低于此值需要澄清 (默认 0.6)
    """
    confidence_threshold: float = Field(default=0.6, description="置信度阈值，低于此值需要澄清")


class SecurityAgentConfig(BaseAgentConfig):
    """安全检查 Agent 配置"""
    # 继承自 BaseAgentConfig，可添加安全检查特定配置
    pass
