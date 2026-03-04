"""
结构化日志配置

配置系统日志，使用结构化格式记录操作和错误。
"""

import logging
import logging.config
import json
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path


class StructuredFormatter(logging.Formatter):
    """
    结构化日志格式化器

    将日志记录转换为 JSON 格式，便于日志分析和监控。
    """

    def __init__(self, service_name: str = "mysql_ai"):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        """
        格式化日志记录

        Args:
            record: 日志记录

        Returns:
            JSON 格式的日志字符串
        """
        # 基础字段
        log_data: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "service": self.service_name,
            "message": record.getMessage(),
        }

        # 添加异常信息
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # 添加堆栈信息
        if record.stack_info:
            log_data["stack"] = self.formatStack(record.stack_info)

        # 尝试解析 JSON 格式的消息
        try:
            if isinstance(record.msg, dict):
                log_data.update(record.msg)
            elif record.msg.startswith('{'):
                parsed = json.loads(record.msg)
                log_data.update(parsed)
        except (json.JSONDecodeError, AttributeError):
            pass

        # 添加自定义字段
        if hasattr(record, 'operation_id'):
            log_data['operation_id'] = record.operation_id

        if hasattr(record, 'operation_type'):
            log_data['operation_type'] = record.operation_type

        if hasattr(record, 'duration'):
            log_data['duration'] = record.duration

        return json.dumps(log_data, ensure_ascii=False)


class OperationLogger:
    """
    操作日志记录器

    专门用于记录业务操作的执行情况。
    """

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def log_operation(
        self,
        operation_id: str,
        operation_type: str,
        success: bool,
        duration: float,
        metadata: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ):
        """
        记录操作日志

        Args:
            operation_id: 操作 ID
            operation_type: 操作类型
            success: 是否成功
            duration: 执行时间（秒）
            metadata: 额外的元数据
            error: 错误信息（如果失败）
        """
        log_data = {
            "event": "operation",
            "operation_id": operation_id,
            "operation_type": operation_type,
            "success": success,
            "duration": duration,
            "timestamp": datetime.now().isoformat()
        }

        if metadata:
            log_data["metadata"] = metadata

        if error:
            log_data["error"] = error

        if success:
            self.logger.info(log_data)
        else:
            self.logger.error(log_data)

    def log_alert(self, alert_type: str, level: str, message: str, **kwargs):
        """
        记录告警日志

        Args:
            alert_type: 告警类型
            level: 告警级别（warning, error, critical）
            message: 告警消息
            **kwargs: 额外的告警数据
        """
        log_data = {
            "event": "alert",
            "alert_type": alert_type,
            "level": level,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        log_data.update(kwargs)

        if level == "critical":
            self.logger.critical(log_data)
        elif level == "error":
            self.logger.error(log_data)
        else:
            self.logger.warning(log_data)


def setup_structured_logging(
    name: str,
    log_dir: str = "logs",
    level: int = logging.INFO,
    service_name: str = "mysql_ai"
) -> logging.Logger:
    """
    设置结构化日志

    Args:
        name: 日志器名称
        log_dir: 日志目录
        level: 日志级别
        service_name: 服务名称

    Returns:
        配置好的日志器
    """
    # 确保日志目录存在
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # 创建日志器
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.handlers.clear()  # 清除现有处理器

    # 创建格式化器
    formatter = StructuredFormatter(service_name=service_name)

    # 控制台处理器（使用更易读的格式）
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # 文件处理器（使用结构化格式）
    file_handler = logging.handlers.RotatingFileHandler(
        log_path / f"{name}.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # 错误日志文件
    error_handler = logging.handlers.RotatingFileHandler(
        log_path / f"{name}_error.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    logger.addHandler(error_handler)

    return logger


def get_operation_logger(name: str = "operation") -> OperationLogger:
    """
    获取操作日志记录器

    Args:
        name: 日志器名称

    Returns:
        OperationLogger 实例
    """
    logger = setup_structured_logging(name)
    return OperationLogger(logger)


# 导入 logging.handlers
import logging.handlers
