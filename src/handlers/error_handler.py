"""
智能错误处理器

统一的错误处理机制，支持 31 种错误分类和自适应恢复策略。
"""

import logging
import re
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


# ==================== 错误类型枚举 ====================

class ErrorType(Enum):
    """错误类型枚举（31 种）"""

    # 意图识别相关错误 (1-5)
    UNKNOWN_INTENT = "unknown_intent"
    LOW_CONFIDENCE = "low_confidence"
    INTENT_AMBIGUOUS = "intent_ambiguous"
    INTENT_RECOGNITION_FAILED = "intent_recognition_failed"
    NO_MATCHED_OPERATION = "no_matched_operation"

    # 参数相关错误 (6-12)
    MISSING_PARAM = "missing_param"
    INVALID_PARAM_TYPE = "invalid_param_type"
    PARAM_OUT_OF_RANGE = "param_out_of_range"
    INVALID_PARAM_FORMAT = "invalid_param_format"
    INVALID_ENUM_VALUE = "invalid_enum_value"
    PARAM_VALIDATION_FAILED = "param_validation_failed"
    MISSING_REQUIRED_PARAMS = "missing_required_params"

    # 数据库相关错误 (13-18)
    SQL_SYNTAX_ERROR = "sql_syntax_error"
    CONNECTION_ERROR = "connection_error"
    QUERY_TIMEOUT = "query_timeout"
    DEADLOCK_ERROR = "deadlock_error"
    CONSTRAINT_VIOLATION = "constraint_violation"
    DATABASE_ERROR = "database_error"

    # 执行相关错误 (19-24)
    METHOD_MISSING = "method_missing"
    OPERATION_NOT_FOUND = "operation_not_found"
    OPERATION_STEPS_MISSING = "operation_steps_missing"
    SQL_DEFINITION_MISSING = "sql_definition_missing"
    EXECUTION_FAILED = "execution_failed"
    TRANSACTION_FAILED = "transaction_failed"

    # 系统相关错误 (25-31)
    LLM_API_ERROR = "llm_api_error"
    CONFIGURATION_ERROR = "configuration_error"
    PERMISSION_ERROR = "permission_error"
    RESOURCE_ERROR = "resource_error"
    NETWORK_ERROR = "network_error"
    UNKNOWN_ERROR = "unknown_error"
    INTERNAL_ERROR = "internal_error"


# ==================== 错误处理结果 ====================

@dataclass
class RecoveryResult:
    """错误恢复结果"""
    error_type: str
    success: bool
    message: str
    suggestions: List[str] = field(default_factory=list)
    can_retry: bool = False
    retry_params: Optional[Dict[str, Any]] = None
    fallback_operation: Optional[str] = None
    fallback_params: Optional[Dict[str, Any]] = None


# ==================== 错误处理器类 ====================

class ErrorHandler:
    """智能错误处理器"""

    def __init__(self):
        """初始化错误处理器"""
        self.ERROR_HANDLERS: Dict[str, Callable] = {
            # 意图识别相关
            ErrorType.UNKNOWN_INTENT.value: self._handle_unknown_intent,
            ErrorType.LOW_CONFIDENCE.value: self._handle_low_confidence,
            ErrorType.INTENT_AMBIGUOUS.value: self._handle_intent_ambiguous,
            ErrorType.INTENT_RECOGNITION_FAILED.value: self._handle_intent_recognition_failed,
            ErrorType.NO_MATCHED_OPERATION.value: self._handle_no_matched_operation,

            # 参数相关
            ErrorType.MISSING_PARAM.value: self._handle_missing_param,
            ErrorType.INVALID_PARAM_TYPE.value: self._handle_invalid_param_type,
            ErrorType.PARAM_OUT_OF_RANGE.value: self._handle_param_out_of_range,
            ErrorType.INVALID_PARAM_FORMAT.value: self._handle_invalid_param_format,
            ErrorType.INVALID_ENUM_VALUE.value: self._handle_invalid_enum_value,
            ErrorType.PARAM_VALIDATION_FAILED.value: self._handle_param_validation_failed,
            ErrorType.MISSING_REQUIRED_PARAMS.value: self._handle_missing_required_params,

            # 数据库相关
            ErrorType.SQL_SYNTAX_ERROR.value: self._handle_sql_syntax_error,
            ErrorType.CONNECTION_ERROR.value: self._handle_connection_error,
            ErrorType.QUERY_TIMEOUT.value: self._handle_query_timeout,
            ErrorType.DEADLOCK_ERROR.value: self._handle_deadlock_error,
            ErrorType.CONSTRAINT_VIOLATION.value: self._handle_constraint_violation,
            ErrorType.DATABASE_ERROR.value: self._handle_database_error,

            # 执行相关
            ErrorType.METHOD_MISSING.value: self._handle_method_missing,
            ErrorType.OPERATION_NOT_FOUND.value: self._handle_operation_not_found,
            ErrorType.OPERATION_STEPS_MISSING.value: self._handle_operation_steps_missing,
            ErrorType.SQL_DEFINITION_MISSING.value: self._handle_sql_definition_missing,
            ErrorType.EXECUTION_FAILED.value: self._handle_execution_failed,
            ErrorType.TRANSACTION_FAILED.value: self._handle_transaction_failed,

            # 系统相关
            ErrorType.LLM_API_ERROR.value: self._handle_llm_api_error,
            ErrorType.CONFIGURATION_ERROR.value: self._handle_configuration_error,
            ErrorType.PERMISSION_ERROR.value: self._handle_permission_error,
            ErrorType.RESOURCE_ERROR.value: self._handle_resource_error,
            ErrorType.NETWORK_ERROR.value: self._handle_network_error,
            ErrorType.UNKNOWN_ERROR.value: self._handle_unknown,
            ErrorType.INTERNAL_ERROR.value: self._handle_internal_error,
        }

    def handle(self, error: Exception, context: Dict[str, Any]) -> RecoveryResult:
        """
        统一错误处理入口

        Args:
            error: 异常对象
            context: 上下文信息字典

        Returns:
            RecoveryResult 恢复结果
        """
        try:
            # 分类错误
            error_type = self._classify_error(error, context)
            logger.info(f"错误分类: {error_type}, 错误信息: {str(error)[:100]}")

            # 获取对应的处理器
            handler = self.ERROR_HANDLERS.get(
                error_type,
                self._handle_unknown
            )

            # 执行处理
            result = handler(error, context)
            result.error_type = error_type

            logger.info(f"错误处理完成: success={result.success}, "
                       f"can_retry={result.can_retry}")

            return result

        except Exception as e:
            logger.error(f"错误处理器自身出错: {e}")
            return RecoveryResult(
                error_type=ErrorType.INTERNAL_ERROR.value,
                success=False,
                message=f"错误处理失败: {str(e)}",
                suggestions=["请联系系统管理员"]
            )

    def _classify_error(self, error: Exception, context: Dict[str, Any]) -> str:
        """
        分类错误类型

        Args:
            error: 异常对象
            context: 上下文信息

        Returns:
            错误类型字符串
        """
        error_msg = str(error).lower()
        error_type_name = type(error).__name__.lower()

        # 1. 检查上下文中的明确错误类型
        if "error_type" in context:
            return context["error_type"]

        # 2. 意图识别相关错误
        if "unknown" in error_msg and "intent" in error_msg:
            return ErrorType.UNKNOWN_INTENT.value
        if "confidence" in error_msg and "low" in error_msg:
            return ErrorType.LOW_CONFIDENCE.value
        if "ambiguous" in error_msg:
            return ErrorType.INTENT_AMBIGUOUS.value
        if "intent" in error_type_name or "recognition" in error_msg:
            return ErrorType.INTENT_RECOGNITION_FAILED.value
        if "no matched operation" in error_msg or ("未找到操作" in error_msg and "模板" not in error_msg):
            return ErrorType.NO_MATCHED_OPERATION.value

        # 3. 参数相关错误
        if "missing" in error_msg and "param" in error_msg:
            if "required" in error_msg:
                return ErrorType.MISSING_REQUIRED_PARAMS.value
            return ErrorType.MISSING_PARAM.value
        if "type" in error_msg and "param" in error_msg:
            return ErrorType.INVALID_PARAM_TYPE.value
        if "out of range" in error_msg or "不能小于" in error_msg or "不能大于" in error_msg:
            return ErrorType.PARAM_OUT_OF_RANGE.value
        if "format" in error_msg and "incorrect" in error_msg:
            return ErrorType.INVALID_PARAM_FORMAT.value
        if "无效" in error_msg and "枚举" in error_msg or "可选值" in error_msg:
            return ErrorType.INVALID_ENUM_VALUE.value
        if "validation" in error_type_name or "validation" in error_msg:
            return ErrorType.PARAM_VALIDATION_FAILED.value

        # 4. 数据库相关错误
        if "syntax" in error_msg or "sql" in error_type_name:
            return ErrorType.SQL_SYNTAX_ERROR.value
        if "connection" in error_type_name or "connect" in error_msg:
            return ErrorType.CONNECTION_ERROR.value
        # 超时错误需要排除 API 超时
        if "timeout" in error_msg and "api" not in error_msg.lower():
            return ErrorType.QUERY_TIMEOUT.value
        if "deadlock" in error_msg or "deadlock" in error_type_name:
            return ErrorType.DEADLOCK_ERROR.value
        if "constraint" in error_msg or "foreign key" in error_msg or "duplicate" in error_msg:
            return ErrorType.CONSTRAINT_VIOLATION.value
        if "database" in error_type_name or "db" in error_type_name or "mysql" in error_type_name:
            return ErrorType.DATABASE_ERROR.value

        # 5. 执行相关错误
        if "method" in error_msg and "missing" in error_msg:
            return ErrorType.METHOD_MISSING.value
        if ("operation" in error_msg and "not found" in error_msg) or "未找到操作模板" in error_msg:
            return ErrorType.OPERATION_NOT_FOUND.value
        if "step" in error_msg and "missing" in error_msg:
            return ErrorType.OPERATION_STEPS_MISSING.value
        if "sql" in error_msg and "missing" in error_msg:
            return ErrorType.SQL_DEFINITION_MISSING.value
        if "execution" in error_type_name or "执行失败" in error_msg:
            return ErrorType.EXECUTION_FAILED.value
        if "transaction" in error_type_name or "transaction" in error_msg:
            return ErrorType.TRANSACTION_FAILED.value

        # 6. 系统相关错误
        if "api" in error_type_name or "api" in error_msg:
            return ErrorType.LLM_API_ERROR.value
        if "config" in error_type_name or "configuration" in error_msg:
            return ErrorType.CONFIGURATION_ERROR.value
        if "permission" in error_msg or "access denied" in error_msg or "denied" in error_msg:
            return ErrorType.PERMISSION_ERROR.value
        if "resource" in error_msg or "memory" in error_msg or "disk" in error_msg:
            return ErrorType.RESOURCE_ERROR.value
        if "network" in error_msg or "connection refused" in error_msg:
            return ErrorType.NETWORK_ERROR.value
        if "internal" in error_msg or "internal" in error_type_name:
            return ErrorType.INTERNAL_ERROR.value

        # 默认未知错误
        return ErrorType.UNKNOWN_ERROR.value

    # ==================== 意图识别错误处理器 ====================

    def _handle_unknown_intent(self, error: Exception, context: Dict) -> RecoveryResult:
        """处理未知意图"""
        user_input = context.get("user_input", "")

        suggestions = [
            "请尝试使用更具体的描述",
            "您可以说 '查询车牌 沪ABC1234' 或 '下发车牌 沪ABC1234 到 国际商务中心'",
            "使用 'help' 查看所有可用操作",
        ]

        # 尝试从用户输入中提取关键词
        if user_input:
            suggestions.insert(0, f"我没有理解您的需求：'{user_input}'")

        return RecoveryResult(
            error_type=ErrorType.UNKNOWN_INTENT.value,
            success=False,
            message="抱歉，我无法理解您的需求",
            suggestions=suggestions,
            can_retry=True
        )

    def _handle_low_confidence(self, error: Exception, context: Dict) -> RecoveryResult:
        """处理低置信度"""
        suggestions = [
            "请提供更详细的信息",
            "例如：'下发车牌 沪ABC1234 到 国际商务中心 操作员张三'",
        ]

        # 如果有关键词匹配结果，提供选择
        matched_ops = context.get("matched_operations", [])
        if matched_ops:
            op_names = [op.name for op in matched_ops[:3]]
            suggestions.insert(0, f"您是否想要：{', '.join(op_names)}？")
            suggestions.append("请选择一个操作并重新描述")

        return RecoveryResult(
            error_type=ErrorType.LOW_CONFIDENCE.value,
            success=False,
            message="我需要更多信息来确定您的意图",
            suggestions=suggestions,
            can_retry=True
        )

    def _handle_intent_ambiguous(self, error: Exception, context: Dict) -> RecoveryResult:
        """处理意图歧义"""
        matched_ops = context.get("matched_operations", [])

        if matched_ops:
            op_names = [f"{op.id} - {op.name}" for op in matched_ops]
            suggestions = [
                "您的需求可以匹配多个操作，请选择：",
                *op_names,
                "请重新描述您的需求或选择操作ID"
            ]
        else:
            suggestions = ["请使用更具体的描述来明确您的需求"]

        return RecoveryResult(
            error_type=ErrorType.INTENT_AMBIGUOUS.value,
            success=False,
            message="您的需求存在歧义，可以匹配多个操作",
            suggestions=suggestions,
            can_retry=True
        )

    def _handle_intent_recognition_failed(self, error: Exception, context: Dict) -> RecoveryResult:
        """处理意图识别失败"""
        return RecoveryResult(
            error_type=ErrorType.INTENT_RECOGNITION_FAILED.value,
            success=False,
            message="意图识别失败",
            suggestions=[
                "请重新描述您的需求",
                "使用 'help' 查看可用操作",
                "如果问题持续，请联系技术支持"
            ],
            can_retry=True
        )

    def _handle_no_matched_operation(self, error: Exception, context: Dict) -> RecoveryResult:
        """处理无匹配操作"""
        user_input = context.get("user_input", "")

        return RecoveryResult(
            error_type=ErrorType.NO_MATCHED_OPERATION.value,
            success=False,
            message="没有找到匹配的操作",
            suggestions=[
                f"'{user_input}' 不是支持的命令",
                "使用 'help' 查看所有可用操作",
                "您可以尝试：查询车牌、下发车牌、查看场库列表等"
            ],
            can_retry=True
        )

    # ==================== 参数错误处理器 ====================

    def _handle_missing_param(self, error: Exception, context: Dict) -> RecoveryResult:
        """处理缺失参数"""
        param_name = context.get("param_name", "未知参数")
        operation_id = context.get("operation_id", "")

        suggestions = [
            f"操作 '{operation_id}' 需要参数：{param_name}",
            "请提供该参数的值后重试"
        ]

        return RecoveryResult(
            error_type=ErrorType.MISSING_PARAM.value,
            success=False,
            message=f"缺少必需参数: {param_name}",
            suggestions=suggestions,
            can_retry=True
        )

    def _handle_invalid_param_type(self, error: Exception, context: Dict) -> RecoveryResult:
        """处理参数类型错误"""
        param_name = context.get("param_name", "未知参数")
        expected_type = context.get("expected_type", "未知类型")

        return RecoveryResult(
            error_type=ErrorType.INVALID_PARAM_TYPE.value,
            success=False,
            message=f"参数 '{param_name}' 的类型不正确",
            suggestions=[
                f"参数类型应该是: {expected_type}",
                "请检查并重新输入"
            ],
            can_retry=True
        )

    def _handle_param_out_of_range(self, error: Exception, context: Dict) -> RecoveryResult:
        """处理参数超出范围"""
        param_name = context.get("param_name", "未知参数")
        min_val = context.get("min_value")
        max_val = context.get("max_value")

        range_text = ""
        if min_val is not None and max_val is not None:
            range_text = f"范围: {min_val} - {max_val}"
        elif min_val is not None:
            range_text = f"最小值: {min_val}"
        elif max_val is not None:
            range_text = f"最大值: {max_val}"

        return RecoveryResult(
            error_type=ErrorType.PARAM_OUT_OF_RANGE.value,
            success=False,
            message=f"参数 '{param_name}' 的值超出范围",
            suggestions=[
                range_text,
                "请调整参数值后重试"
            ],
            can_retry=True
        )

    def _handle_invalid_param_format(self, error: Exception, context: Dict) -> RecoveryResult:
        """处理参数格式错误"""
        param_name = context.get("param_name", "未知参数")
        error_msg = str(error)

        suggestions = [
            f"参数 '{param_name}' 的格式不正确",
        ]

        # 特殊处理车牌号
        if "车牌" in error_msg or "plate" in param_name.lower():
            suggestions.extend([
                "车牌号格式应为: 省份简称+字母+5-6位字符",
                "例如: 沪ABC1234, 京A123456",
                "支持的省份: 京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼"
            ])

        return RecoveryResult(
            error_type=ErrorType.INVALID_PARAM_FORMAT.value,
            success=False,
            message=f"参数 '{param_name}' 格式不正确",
            suggestions=suggestions,
            can_retry=True
        )

    def _handle_invalid_enum_value(self, error: Exception, context: Dict) -> RecoveryResult:
        """处理无效枚举值"""
        param_name = context.get("param_name", "未知参数")
        param_value = context.get("param_value", "")
        available_values = context.get("available_values", [])

        suggestions = [
            f"参数 '{param_name}' 的值 '{param_value}' 无效",
        ]

        if available_values:
            display_values = available_values[:10]  # 限制显示数量
            suggestions.append(f"可选值包括: {', '.join(str(v) for v in display_values)}")
            if len(available_values) > 10:
                suggestions.append(f"... 还有 {len(available_values) - 10} 个选项")

        # 特殊处理场库名称
        if "park" in param_name.lower():
            suggestions.append("您也可以使用 '全部' 批量操作所有场库")

        return RecoveryResult(
            error_type=ErrorType.INVALID_ENUM_VALUE.value,
            success=False,
            message=f"无效的参数值: {param_value}",
            suggestions=suggestions,
            can_retry=True
        )

    def _handle_param_validation_failed(self, error: Exception, context: Dict) -> RecoveryResult:
        """处理参数验证失败"""
        return RecoveryResult(
            error_type=ErrorType.PARAM_VALIDATION_FAILED.value,
            success=False,
            message="参数验证失败",
            suggestions=[
                "请检查所有参数是否正确",
                "确保必需参数都已提供",
                "参数值应符合要求"
            ],
            can_retry=True
        )

    def _handle_missing_required_params(self, error: Exception, context: Dict) -> RecoveryResult:
        """处理缺失必需参数（多个）"""
        missing_params = context.get("missing_params", [])
        operation_id = context.get("operation_id", "")

        suggestions = [
            f"操作 '{operation_id}' 缺少以下必需参数:",
            *missing_params,
            "请提供所有必需参数后重试"
        ]

        return RecoveryResult(
            error_type=ErrorType.MISSING_REQUIRED_PARAMS.value,
            success=False,
            message=f"缺少必需参数: {', '.join(missing_params)}",
            suggestions=suggestions,
            can_retry=True
        )

    # ==================== 数据库错误处理器 ====================

    def _handle_sql_syntax_error(self, error: Exception, context: Dict) -> RecoveryResult:
        """处理 SQL 语法错误"""
        error_msg = str(error)

        # 尝试提取更有用的信息
        suggestions = [
            "SQL 语法错误",
        ]

        # 提取 MySQL 错误位置
        match = re.search(r"near '([^']+)' at line (\d+)", error_msg)
        if match:
            near_text = match.group(1)
            line_num = match.group(2)
            suggestions.append(f"错误位置: 第 {line_num} 行，在 '{near_text}' 附近")

        suggestions.extend([
            "请检查 SQL 语句语法",
            "建议使用 help 命令查看操作模板"
        ])

        return RecoveryResult(
            error_type=ErrorType.SQL_SYNTAX_ERROR.value,
            success=False,
            message="SQL 语法错误",
            suggestions=suggestions,
            can_retry=False
        )

    def _handle_connection_error(self, error: Exception, context: Dict) -> RecoveryResult:
        """处理数据库连接错误"""
        return RecoveryResult(
            error_type=ErrorType.CONNECTION_ERROR.value,
            success=False,
            message="数据库连接失败",
            suggestions=[
                "请检查数据库服务是否正常运行",
                "请检查网络连接",
                "请检查数据库连接配置",
                "稍后重试"
            ],
            can_retry=True,
            retry_params={"delay": 5}  # 建议5秒后重试
        )

    def _handle_query_timeout(self, error: Exception, context: Dict) -> RecoveryResult:
        """处理查询超时"""
        return RecoveryResult(
            error_type=ErrorType.QUERY_TIMEOUT.value,
            success=False,
            message="查询执行超时",
            suggestions=[
                "查询可能返回大量数据，请添加更多筛选条件",
                "联系管理员优化查询",
                "稍后重试"
            ],
            can_retry=True
        )

    def _handle_deadlock_error(self, error: Exception, context: Dict) -> RecoveryResult:
        """处理死锁错误"""
        return RecoveryResult(
            error_type=ErrorType.DEADLOCK_ERROR.value,
            success=False,
            message="操作遇到数据库死锁",
            suggestions=[
                "该操作与其他操作冲突",
                "系统已自动回滚事务",
                "请稍后重试"
            ],
            can_retry=True,
            retry_params={"delay": 2, "max_retries": 3}
        )

    def _handle_constraint_violation(self, error: Exception, context: Dict) -> RecoveryResult:
        """处理约束违反错误"""
        error_msg = str(error).lower()

        suggestions = ["数据约束违反"]

        if "duplicate" in error_msg or "primary key" in error_msg:
            suggestions.append("记录已存在，不能重复添加")
            suggestions.append("请检查数据是否已存在")
        elif "foreign key" in error_msg:
            suggestions.append("引用的关联数据不存在")
            suggestions.append("请确保引用的数据有效")
        elif "not null" in error_msg:
            suggestions.append("必填字段不能为空")
            suggestions.append("请提供所有必需字段的值")

        return RecoveryResult(
            error_type=ErrorType.CONSTRAINT_VIOLATION.value,
            success=False,
            message="数据约束违反",
            suggestions=suggestions,
            can_retry=False
        )

    def _handle_database_error(self, error: Exception, context: Dict) -> RecoveryResult:
        """处理通用数据库错误"""
        error_msg = str(error)

        return RecoveryResult(
            error_type=ErrorType.DATABASE_ERROR.value,
            success=False,
            message=f"数据库错误: {error_msg[:100]}",
            suggestions=[
                "数据库操作失败",
                "请联系技术支持",
                "稍后重试"
            ],
            can_retry=True
        )

    # ==================== 执行错误处理器 ====================

    def _handle_method_missing(self, error: Exception, context: Dict) -> RecoveryResult:
        """处理方法缺失"""
        method_name = context.get("method_name", "未知方法")

        return RecoveryResult(
            error_type=ErrorType.METHOD_MISSING.value,
            success=False,
            message=f"缺少实现方法: {method_name}",
            suggestions=[
                "该功能尚未实现",
                "请联系技术支持",
                "使用其他可用功能"
            ],
            can_retry=False
        )

    def _handle_operation_not_found(self, error: Exception, context: Dict) -> RecoveryResult:
        """处理操作未找到"""
        operation_id = context.get("operation_id", "")

        return RecoveryResult(
            error_type=ErrorType.OPERATION_NOT_FOUND.value,
            success=False,
            message=f"未找到操作模板: {operation_id}",
            suggestions=[
                "该操作不存在",
                "使用 'help' 查看所有可用操作",
                "检查操作ID是否正确"
            ],
            can_retry=True
        )

    def _handle_operation_steps_missing(self, error: Exception, context: Dict) -> RecoveryResult:
        """处理操作步骤缺失"""
        operation_id = context.get("operation_id", "")

        return RecoveryResult(
            error_type=ErrorType.OPERATION_STEPS_MISSING.value,
            success=False,
            message=f"操作 '{operation_id}' 缺少执行步骤",
            suggestions=[
                "该操作的配置不完整",
                "请联系技术支持",
                "使用其他可用功能"
            ],
            can_retry=False
        )

    def _handle_sql_definition_missing(self, error: Exception, context: Dict) -> RecoveryResult:
        """处理 SQL 定义缺失"""
        operation_id = context.get("operation_id", "")
        step_name = context.get("step_name", "")

        return RecoveryResult(
            error_type=ErrorType.SQL_DEFINITION_MISSING.value,
            success=False,
            message=f"缺少 SQL 定义: {step_name}",
            suggestions=[
                f"操作 '{operation_id}' 的 SQL 定义不完整",
                "请联系技术支持"
            ],
            can_retry=False
        )

    def _handle_execution_failed(self, error: Exception, context: Dict) -> RecoveryResult:
        """处理执行失败"""
        operation_id = context.get("operation_id", "")
        error_msg = str(error)

        return RecoveryResult(
            error_type=ErrorType.EXECUTION_FAILED.value,
            success=False,
            message=f"操作执行失败: {error_msg[:100]}",
            suggestions=[
                "操作执行过程中出错",
                "请检查参数是否正确",
                "稍后重试",
                "如果问题持续，请联系技术支持"
            ],
            can_retry=True
        )

    def _handle_transaction_failed(self, error: Exception, context: Dict) -> RecoveryResult:
        """处理事务失败"""
        operation_id = context.get("operation_id", "")
        error_msg = str(error)

        return RecoveryResult(
            error_type=ErrorType.TRANSACTION_FAILED.value,
            success=False,
            message=f"事务执行失败: {error_msg[:100]}",
            suggestions=[
                "事务已自动回滚",
                "数据未被修改",
                "请稍后重试",
                "如果问题持续，请联系技术支持"
            ],
            can_retry=True
        )

    # ==================== 系统错误处理器 ====================

    def _handle_llm_api_error(self, error: Exception, context: Dict) -> RecoveryResult:
        """处理 LLM API 错误"""
        error_msg = str(error).lower()

        suggestions = ["LLM 服务调用失败"]

        if "timeout" in error_msg:
            suggestions.append("请求超时，请稍后重试")
        elif "key" in error_msg or "token" in error_msg:
            suggestions.append("API 密钥配置错误")
            suggestions.append("请联系管理员检查配置")
        elif "rate" in error_msg or "limit" in error_msg:
            suggestions.append("API 调用频率超限")
            suggestions.append("请稍后重试")

        # 尝试使用关键词匹配作为回退
        return RecoveryResult(
            error_type=ErrorType.LLM_API_ERROR.value,
            success=False,
            message="智能识别服务暂时不可用",
            suggestions=suggestions + ["系统将使用关键词匹配"],
            can_retry=True,
            retry_params={"use_keyword_matching": True}
        )

    def _handle_configuration_error(self, error: Exception, context: Dict) -> RecoveryResult:
        """处理配置错误"""
        config_path = context.get("config_path", "")
        error_msg = str(error)

        return RecoveryResult(
            error_type=ErrorType.CONFIGURATION_ERROR.value,
            success=False,
            message=f"配置错误: {error_msg[:100]}",
            suggestions=[
                f"配置文件错误: {config_path}" if config_path else "配置文件错误",
                "请检查配置文件语法",
                "联系管理员修复配置"
            ],
            can_retry=False
        )

    def _handle_permission_error(self, error: Exception, context: Dict) -> RecoveryResult:
        """处理权限错误"""
        return RecoveryResult(
            error_type=ErrorType.PERMISSION_ERROR.value,
            success=False,
            message="权限不足",
            suggestions=[
                "您没有执行此操作的权限",
                "请联系管理员获取相应权限",
                "或者执行其他允许的操作"
            ],
            can_retry=False
        )

    def _handle_resource_error(self, error: Exception, context: Dict) -> RecoveryResult:
        """处理资源错误"""
        error_msg = str(error).lower()

        if "memory" in error_msg:
            suggestions = [
                "系统内存不足",
                "请联系系统管理员"
            ]
        elif "disk" in error_msg:
            suggestions = [
                "磁盘空间不足",
                "请联系系统管理员"
            ]
        else:
            suggestions = [
                "系统资源不足",
                "请联系系统管理员"
            ]

        return RecoveryResult(
            error_type=ErrorType.RESOURCE_ERROR.value,
            success=False,
            message="系统资源不足",
            suggestions=suggestions,
            can_retry=False
        )

    def _handle_network_error(self, error: Exception, context: Dict) -> RecoveryResult:
        """处理网络错误"""
        return RecoveryResult(
            error_type=ErrorType.NETWORK_ERROR.value,
            success=False,
            message="网络连接失败",
            suggestions=[
                "请检查网络连接",
                "稍后重试",
                "如果问题持续，请联系技术支持"
            ],
            can_retry=True,
            retry_params={"delay": 5, "max_retries": 3}
        )

    def _handle_unknown(self, error: Exception, context: Dict) -> RecoveryResult:
        """处理未知错误"""
        error_msg = str(error)
        error_type = type(error).__name__

        return RecoveryResult(
            error_type=ErrorType.UNKNOWN_ERROR.value,
            success=False,
            message=f"未知错误: {error_type}: {error_msg[:100]}",
            suggestions=[
                "遇到未知错误",
                "请记录错误信息并联系技术支持",
                "您可以尝试重新描述您的需求"
            ],
            can_retry=True
        )

    def _handle_internal_error(self, error: Exception, context: Dict) -> RecoveryResult:
        """处理内部错误"""
        error_msg = str(error)

        return RecoveryResult(
            error_type=ErrorType.INTERNAL_ERROR.value,
            success=False,
            message=f"系统内部错误: {error_msg[:100]}",
            suggestions=[
                "系统发生内部错误",
                "请联系技术支持",
                "提供错误信息以便排查问题"
            ],
            can_retry=False
        )


# ==================== 全局单例 ====================

_error_handler: Optional[ErrorHandler] = None


def get_error_handler() -> ErrorHandler:
    """
    获取错误处理器单例

    Returns:
        ErrorHandler 实例
    """
    global _error_handler

    if _error_handler is None:
        _error_handler = ErrorHandler()

    return _error_handler
