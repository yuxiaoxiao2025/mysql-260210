"""MVP ReACT 编排器 - 无学习功能的简化版"""
import json
import logging
from typing import Optional
from dataclasses import dataclass, field

from src.llm_client import LLMClient
from src.react.tool_service import MVPToolService, NEED_CONFIRM_MARKER
from src.react.tools import MVP_TOOLS, SYSTEM_PROMPT

logger = logging.getLogger(__name__)


@dataclass
class ConversationState:
    """对话状态"""
    messages: list = field(default_factory=list)
    pending_confirmation: bool = False
    confirmation_type: str = ""  # "sql" or "operation"
    confirmation_data: dict = field(default_factory=dict)


class MVPReACTOrchestrator:
    """MVP ReACT 编排器

    实现简化的 ReACT 循环：
    1. 模型推理 -> 调用工具
    2. 执行 -> 返回结果
    3. 用户修正 -> 重新执行

    无学习记忆功能。
    """

    def __init__(
        self,
        llm_client: LLMClient,
        tool_service: MVPToolService,
        max_iterations: int = 5
    ):
        """初始化编排器

        Args:
            llm_client: LLM 客户端
            tool_service: 工具服务
            max_iterations: 最大迭代次数
        """
        self.llm = llm_client
        self.tools = tool_service
        self.max_iterations = max_iterations
        self.state = ConversationState()

    def process(self, user_input: str) -> str:
        """处理用户输入

        Args:
            user_input: 用户输入

        Returns:
            str: 助手回复
        """
        # 添加用户消息
        self.state.messages.append({"role": "user", "content": user_input})

        # ReACT 循环
        for iteration in range(self.max_iterations):
            logger.debug(f"ReACT iteration {iteration + 1}/{self.max_iterations}")

            # 调用模型
            response = self.llm.chat_with_tools(
                messages=self.state.messages,
                tools=MVP_TOOLS,
                system_prompt=SYSTEM_PROMPT
            )

            # 检查是否有工具调用
            if response.has_tool_calls:
                # 执行工具
                tool_results = self._execute_tools(response.tool_calls)

                # 检查是否需要确认
                if self.state.pending_confirmation:
                    return self._format_confirmation_request()

                # 添加工具结果到消息
                self._add_tool_results(response.tool_calls, tool_results)

                # 继续循环
                continue

            # 没有工具调用，返回最终答案
            final_content = response.content or ""
            if final_content:
                self.state.messages.append({"role": "assistant", "content": final_content})
            return final_content or "抱歉，我没有理解您的问题。"

        return "抱歉，我需要更多时间来处理您的请求。"

    def _execute_tools(self, tool_calls: list) -> list[str]:
        """执行工具调用

        Args:
            tool_calls: 工具调用列表

        Returns:
            list[str]: 工具结果列表
        """
        results = []

        for tc in tool_calls:
            try:
                args = json.loads(tc.arguments) if tc.arguments else {}
            except json.JSONDecodeError:
                args = {}

            result = self.tools.execute(tc.name, args)

            # 检查是否需要确认
            if result.startswith(NEED_CONFIRM_MARKER):
                self.state.pending_confirmation = True
                self.state.confirmation_type = "sql" if tc.name == "execute_sql" else "operation"
                self.state.confirmation_data = {
                    "tool_name": tc.name,
                    "args": args,
                    "preview": result.replace(f"{NEED_CONFIRM_MARKER}\n", "")
                }

            results.append(result)

        return results

    def _format_confirmation_request(self) -> str:
        """格式化确认请求

        Returns:
            str: 格式化的确认请求
        """
        preview = self.state.confirmation_data.get("preview", "")
        return f"{preview}\n\n确认执行？(输入 'y' 确认，或描述您的修改意见)"

    def confirm(self, confirmed: bool, modification: str = None) -> str:
        """处理用户确认

        Args:
            confirmed: 是否确认
            modification: 修改意见（可选）

        Returns:
            str: 执行结果
        """
        if not confirmed:
            self.state.pending_confirmation = False
            self.state.confirmation_data = {}
            return "操作已取消。"

        # 执行确认的操作
        tool_name = self.state.confirmation_data.get("tool_name")
        args = self.state.confirmation_data.get("args", {})

        if tool_name == "execute_sql":
            result = self.tools.confirm_and_execute_sql(args.get("sql", ""))
        elif tool_name == "execute_operation":
            result = self.tools.confirm_and_execute_operation(
                args.get("operation_id"),
                args.get("params", {})
            )
        else:
            result = "未知操作类型"

        # 重置状态
        self.state.pending_confirmation = False
        self.state.confirmation_data = {}

        return result

    def _add_tool_results(self, tool_calls: list, results: list[str]):
        """添加工具结果到消息

        Args:
            tool_calls: 工具调用列表
            results: 工具结果列表
        """
        # 添加助手消息（包含工具调用）
        self.state.messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": tc.arguments
                    }
                }
                for tc in tool_calls
            ]
        })

        # 添加工具结果
        for tc, result in zip(tool_calls, results):
            self.state.messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result
            })

    def reset(self):
        """重置对话状态"""
        self.state = ConversationState()