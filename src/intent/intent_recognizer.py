"""
智能意图识别器

利用 LLM 理解用户意图，匹配操作模板并提取参数。
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RecognizedIntent:
    """识别结果"""
    operation_id: Optional[str]
    operation_name: str
    confidence: float
    params: Dict[str, Any]
    missing_params: List[str]
    fallback_sql: Optional[str]
    reasoning: str
    suggestions: List[str]
    is_matched: bool

    def is_ready_to_execute(self) -> bool:
        """检查是否可以执行（已匹配操作且无缺失参数）"""
        return self.is_matched and not self.missing_params


class IntentRecognizer:
    """智能意图识别器"""

    # 置信度阈值
    HIGH_CONFIDENCE_THRESHOLD = 0.85  # 高置信度：自动执行
    MEDIUM_CONFIDENCE_THRESHOLD = 0.60  # 中置信度：需要确认
    LOW_CONFIDENCE_THRESHOLD = 0.30  # 低置信度：需要用户选择

    def __init__(self, llm_client, knowledge_loader):
        """
        初始化意图识别器

        Args:
            llm_client: LLM 客户端
            knowledge_loader: 知识库加载器
        """
        self.llm_client = llm_client
        self.knowledge_loader = knowledge_loader

    def recognize(self, user_input: str, load_enums: bool = True) -> RecognizedIntent:
        """
        识别用户意图

        Args:
            user_input: 用户输入
            load_enums: 是否加载枚举值（用于参数验证和自动补全）

        Returns:
            RecognizedIntent 识别结果
        """
        # 1. 先尝试关键词匹配（快速路径）
        keyword_result = self._match_by_keywords(user_input)
        if keyword_result and keyword_result.get("confidence", 0) >= self.HIGH_CONFIDENCE_THRESHOLD:
            logger.info(f"关键词匹配成功: {keyword_result['operation_id']}")
            return self._build_result(keyword_result, user_input)

        # 2. 调用 LLM 进行深度识别
        try:
            # 获取操作上下文
            operations_context = self.knowledge_loader.get_operation_context_for_llm()

            # 获取枚举值
            enum_values = {}
            if load_enums:
                enum_values = self._get_relevant_enums(user_input)

            # 调用 LLM
            llm_result = self.llm_client.recognize_intent(
                user_query=user_input,
                operations_context=operations_context,
                enum_values=enum_values
            )

            # 如果 LLM 置信度低，但关键词匹配有结果，使用关键词结果
            if (llm_result.get("confidence", 0) < self.MEDIUM_CONFIDENCE_THRESHOLD
                    and keyword_result):
                logger.info("LLM 置信度低，使用关键词匹配结果")
                return self._build_result(keyword_result, user_input)

            return self._build_result(llm_result, user_input)

        except Exception as e:
            logger.error(f"LLM 意图识别失败: {e}")

            # 回退到关键词匹配
            if keyword_result:
                logger.info("回退到关键词匹配")
                return self._build_result(keyword_result, user_input)

            # 完全失败，返回空结果
            return RecognizedIntent(
                operation_id=None,
                operation_name="",
                confidence=0.0,
                params={},
                missing_params=[],
                fallback_sql=None,
                reasoning=f"意图识别失败: {str(e)}",
                suggestions=["请重新描述您的需求，或使用 'help' 查看可用操作"],
                is_matched=False
            )

    def _match_by_keywords(self, user_input: str) -> Optional[Dict]:
        """
        通过关键词匹配操作

        Args:
            user_input: 用户输入

        Returns:
            匹配结果字典，未匹配返回 None
        """
        matched_ops = self.knowledge_loader.find_operations_by_keywords(user_input)

        if not matched_ops:
            return None

        # 取第一个匹配（分数最高的）
        best_op = matched_ops[0]

        # 计算置信度（基于匹配关键词数量和长度）
        total_keyword_length = sum(len(kw) for kw in best_op.keywords)
        matched_length = 0
        user_lower = user_input.lower()
        for kw in best_op.keywords:
            if kw.lower() in user_lower:
                matched_length += len(kw)

        confidence = min(0.95, matched_length / max(total_keyword_length, 1) * 2)

        # 提取参数
        params = self._extract_params_from_text(user_input, best_op)

        return {
            "operation_id": best_op.id,
            "confidence": confidence,
            "params": params,
            "reasoning": f"通过关键词匹配到操作: {best_op.name}",
            "missing_params": self._get_missing_params(best_op, params),
            "suggestions": []
        }

    def _extract_params_from_text(self, text: str, operation) -> Dict[str, Any]:
        """
        从文本中提取参数

        Args:
            text: 用户输入
            operation: 操作模板

        Returns:
            提取的参数字典
        """
        import re

        params = {}

        for param in operation.params:
            if param.type == "string":
                # 车牌号提取
                if param.pattern and "京津沪" in (param.pattern or ""):
                    match = re.search(
                        r"[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼][A-Z][A-Z0-9]{5,6}",
                        text.upper()
                    )
                    if match:
                        params[param.name] = match.group()

                # 尝试从枚举中匹配
                elif param.enum_from:
                    enum_values = self.knowledge_loader.get_enum_values_flat(param.enum_from)
                    for val in enum_values:
                        if val.lower() in text.lower():
                            params[param.name] = val
                            break

            elif param.type == "int":
                # 提取数字
                match = re.search(r"(\d+)", text)
                if match:
                    params[param.name] = int(match.group(1))

            elif param.type == "date":
                # 提取日期相关
                if "天内" in text or "日内" in text:
                    match = re.search(r"(\d+)\s*[天日]", text)
                    if match:
                        params[param.name] = int(match.group(1))

        return params

    def _get_missing_params(self, operation, params: Dict) -> List[str]:
        """获取缺失的必需参数"""
        missing = []
        for param in operation.params:
            if param.required and param.name not in params:
                missing.append(param.name)
        return missing

    def _get_relevant_enums(self, user_input: str) -> Dict[str, list]:
        """
        获取与用户输入相关的枚举值

        Args:
            user_input: 用户输入

        Returns:
            枚举值字典
        """
        enums = {}

        # 始终加载场库和操作员（常用）
        for enum_name in ["park_names", "operator_names"]:
            values = self.knowledge_loader.get_enum_values_flat(enum_name)
            if values:
                enums[enum_name] = values

        # 如果输入中可能有车牌，加载车牌列表
        import re
        if re.search(r"[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼][A-Z]",
                     user_input.upper()):
            plates = self.knowledge_loader.get_enum_values_flat("plate_list")
            if plates:
                enums["plate_list"] = plates[:50]  # 限制数量

        return enums

    def _build_result(self, result: Dict, user_input: str) -> RecognizedIntent:
        """
        构建识别结果对象

        Args:
            result: 识别结果字典
            user_input: 用户输入

        Returns:
            RecognizedIntent 对象
        """
        operation_id = result.get("operation_id")
        operation_name = ""
        is_matched = False

        if operation_id:
            operation = self.knowledge_loader.get_operation(operation_id)
            if operation:
                operation_name = operation.name
                is_matched = True

        # 验证和补全参数
        params = result.get("params", {})
        missing_params = result.get("missing_params", [])

        if operation_id and is_matched:
            operation = self.knowledge_loader.get_operation(operation_id)
            if operation:
                # 验证枚举参数
                for param in operation.params:
                    if param.enum_from and param.name in params:
                        # 验证值是否在枚举中
                        validated = self.knowledge_loader.lookup_enum_value(
                            param.enum_from, params[param.name]
                        )
                        if validated:
                            params[param.name] = validated
                        else:
                            # 值不在枚举中，添加建议
                            if param.name not in missing_params:
                                suggestions = result.get("suggestions", [])
                                available = self.knowledge_loader.get_enum_values_flat(param.enum_from)
                                if available:
                                    suggestions.append(
                                        f"'{params[param.name]}' 不是有效的 {param.description}，"
                                        f"可选值包括: {', '.join(available[:5])}..."
                                    )
                                result["suggestions"] = suggestions

        return RecognizedIntent(
            operation_id=operation_id,
            operation_name=operation_name,
            confidence=result.get("confidence", 0.0),
            params=params,
            missing_params=missing_params,
            fallback_sql=result.get("fallback_sql"),
            reasoning=result.get("reasoning", ""),
            suggestions=result.get("suggestions", []),
            is_matched=is_matched
        )

    def get_operation_help(self, operation_id: str) -> str:
        """
        获取操作帮助信息

        Args:
            operation_id: 操作ID

        Returns:
            帮助文本
        """
        operation = self.knowledge_loader.get_operation(operation_id)
        if not operation:
            return f"未找到操作: {operation_id}"

        lines = [
            f"# {operation.name}",
            f"",
            f"**描述**: {operation.description}",
            f"**类别**: {operation.category}",
            f"**关键词**: {', '.join(operation.keywords)}",
            f"",
        ]

        if operation.params:
            lines.append("## 参数")
            for param in operation.params:
                required = "必需" if param.required else "可选"
                enum_info = ""
                if param.enum_from:
                    values = self.knowledge_loader.get_enum_values_flat(param.enum_from)
                    if values:
                        enum_info = f" (可选值: {', '.join(values[:5])}...)"

                lines.append(f"- **{param.name}** ({param.type}, {required}): "
                            f"{param.description}{enum_info}")
            lines.append("")

        if operation.steps:
            lines.append("## 执行步骤")
            for i, step in enumerate(operation.steps, 1):
                lines.append(f"{i}. {step.name}: {step.description or ''}")
            lines.append("")

        lines.append("## 示例")
        if operation_id == "plate_distribute":
            lines.append("下发车牌 沪ABC1234 到 国际商务中心 操作员张三")
        elif operation_id == "plate_query":
            lines.append("查询车牌 沪ABC1234")
            lines.append("查看所有车牌")
        elif operation_id == "plate_expire_soon":
            lines.append("查看30天内到期的车牌")
        else:
            lines.append(f"参考关键词: {', '.join(operation.keywords)}")

        return "\n".join(lines)

    def list_available_operations(self, category: str = None) -> str:
        """
        列出可用操作

        Args:
            category: 操作类别过滤 (query, mutation)

        Returns:
            操作列表文本
        """
        if category == "query":
            operations = self.knowledge_loader.get_query_operations()
            title = "查询操作"
        elif category == "mutation":
            operations = self.knowledge_loader.get_mutation_operations()
            title = "变更操作"
        else:
            operations = self.knowledge_loader.get_all_operations()
            title = "所有操作"

        lines = [f"# {title}", ""]

        for op_id, op in operations.items():
            emoji = "🔍" if op.is_query() else "✏️"
            lines.append(f"- {emoji} **{op_id}**: {op.name} - {op.description}")
            lines.append(f"  关键词: {', '.join(op.keywords)}")

        return "\n".join(lines)


# 全局单例
_intent_recognizer: Optional[IntentRecognizer] = None


def get_intent_recognizer(llm_client=None, knowledge_loader=None) -> IntentRecognizer:
    """
    获取意图识别器单例

    Args:
        llm_client: LLM 客户端
        knowledge_loader: 知识库加载器

    Returns:
        IntentRecognizer 实例
    """
    global _intent_recognizer

    if _intent_recognizer is None:
        if llm_client is None or knowledge_loader is None:
            raise ValueError("首次调用需要提供 llm_client 和 knowledge_loader")
        _intent_recognizer = IntentRecognizer(llm_client, knowledge_loader)

    return _intent_recognizer
