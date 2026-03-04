"""
错误处理模块

提供统一的错误处理机制，支持智能错误分类和自适应恢复策略。
"""

from .error_handler import (
    ErrorHandler,
    ErrorType,
    RecoveryResult,
    get_error_handler,
)

__all__ = [
    "ErrorHandler",
    "ErrorType",
    "RecoveryResult",
    "get_error_handler",
]
