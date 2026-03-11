"""Agent 基类定义"""
from abc import ABC, abstractmethod
from typing import Any

from src.agents.models import AgentResult
from src.agents.context import AgentContext
from src.agents.config import BaseAgentConfig


class BaseAgent(ABC):
    """Agent 基类

    所有具体 Agent 的抽象基类，定义统一的执行接口。

    Attributes:
        config: Agent 配置
    """

    def __init__(self, config: BaseAgentConfig):
        """初始化 Agent

        Args:
            config: Agent 配置对象
        """
        self.config = config

    def run(self, context: AgentContext) -> AgentResult:
        """执行 Agent

        Args:
            context: 执行上下文

        Returns:
            AgentResult: 执行结果
        """
        # 公共执行逻辑 (如超时处理、日志记录等)
        # 目前直接调用子类实现
        return self._run_impl(context)

    @abstractmethod
    def _run_impl(self, context: AgentContext) -> AgentResult:
        """子类实现的具体执行逻辑

        Args:
            context: 执行上下文

        Returns:
            AgentResult: 执行结果
        """
        pass
