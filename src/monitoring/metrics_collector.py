"""
指标收集器

收集系统运行指标，包括操作统计、错误率、执行时间等。
使用滑动窗口机制保持最近一段时间的数据。
"""

import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from collections import defaultdict
from dataclasses import dataclass, field, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class OperationMetric:
    """操作指标"""
    timestamp: float
    operation_type: str
    success: bool
    duration: float
    operation_id: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CacheMetrics:
    """缓存指标"""
    timestamp: float
    operation: str  # generate_sql, recognize_intent, etc.
    cache_hit: bool  # 是否命中缓存
    cache_creation_input_tokens: int  # 缓存创建输入 token 数
    cached_tokens: int  # 命中缓存的 token 数
    total_input_tokens: int  # 总输入 token 数
    total_output_tokens: int  # 总输出 token 数
    model: str  # 使用的模型


class MetricsCollector:
    """
    指标收集器

    使用滑动窗口收集和统计系统指标。
    支持按操作类型、时间窗口等多维度统计。

    Attributes:
        window_size: 滑动窗口大小（秒）
        metrics: 指标数据列表
        start_time: 收集器启动时间
    """

    def __init__(self, window_size: int = 300):
        """
        初始化指标收集器

        Args:
            window_size: 滑动窗口大小（秒），默认 5 分钟
        """
        self.window_size = window_size
        self.metrics: List[OperationMetric] = []
        self.cache_metrics: List[CacheMetrics] = []
        self.start_time = time.time()
        self._type_index = defaultdict(list)  # 按类型索引

    def record_cache_metrics(
        self,
        operation: str,
        cache_hit: bool,
        cache_creation_input_tokens: int = 0,
        cached_tokens: int = 0,
        total_input_tokens: int = 0,
        total_output_tokens: int = 0,
        model: str = "qwen-plus"
    ):
        """
        记录缓存指标

        Args:
            operation: 操作类型 (generate_sql, recognize_intent, etc.)
            cache_hit: 是否命中缓存
            cache_creation_input_tokens: 缓存创建输入 token 数
            cached_tokens: 命中缓存的 token 数
            total_input_tokens: 总输入 token 数
            total_output_tokens: 总输出 token 数
            model: 使用的模型
        """
        metric = CacheMetrics(
            timestamp=time.time(),
            operation=operation,
            cache_hit=cache_hit,
            cache_creation_input_tokens=cache_creation_input_tokens,
            cached_tokens=cached_tokens,
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            model=model
        )

        self.cache_metrics.append(metric)
        logger.debug(
            f"缓存指标记录: operation={operation}, cache_hit={cache_hit}, "
            f"cached_tokens={cached_tokens}"
        )

        # 定期清理过期数据
        self._cleanup_cache_metrics()

    def _cleanup_cache_metrics(self):
        """清理缓存指标中的过期数据"""
        current_time = time.time()
        cutoff_time = current_time - self.window_size
        self.cache_metrics = [m for m in self.cache_metrics if m.timestamp > cutoff_time]

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            缓存统计字典
        """
        self._cleanup_cache_metrics()

        if not self.cache_metrics:
            return {
                "total_calls": 0,
                "cache_hits": 0,
                "cache_misses": 0,
                "hit_rate": 0.0,
                "total_cached_tokens": 0,
                "total_creation_tokens": 0,
                "avg_cached_tokens": 0,
                "by_operation": {}
            }

        total = len(self.cache_metrics)
        hits = sum(1 for m in self.cache_metrics if m.cache_hit)
        misses = total - hits
        total_cached = sum(m.cached_tokens for m in self.cache_metrics)
        total_creation = sum(m.cache_creation_input_tokens for m in self.cache_metrics)

        # 按操作类型统计
        by_operation = {}
        for m in self.cache_metrics:
            op = m.operation
            if op not in by_operation:
                by_operation[op] = {"total": 0, "hits": 0, "misses": 0}
            by_operation[op]["total"] += 1
            if m.cache_hit:
                by_operation[op]["hits"] += 1
            else:
                by_operation[op]["misses"] += 1

        return {
            "total_calls": total,
            "cache_hits": hits,
            "cache_misses": misses,
            "hit_rate": hits / total if total > 0 else 0.0,
            "total_cached_tokens": total_cached,
            "total_creation_tokens": total_creation,
            "avg_cached_tokens": total_cached / hits if hits > 0 else 0.0,
            "by_operation": by_operation
        }

    def record_operation(
        self,
        operation_type: str,
        success: bool,
        duration: float,
        operation_id: Optional[str] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        记录操作指标

        Args:
            operation_type: 操作类型（query, mutation 等）
            success: 是否成功
            duration: 执行时间（秒）
            operation_id: 操作 ID
            error: 错误信息（如果失败）
            metadata: 额外的元数据
        """
        metric = OperationMetric(
            timestamp=time.time(),
            operation_type=operation_type,
            success=success,
            duration=duration,
            operation_id=operation_id,
            error=error,
            metadata=metadata or {}
        )

        self.metrics.append(metric)
        self._type_index[operation_type].append(metric)

        # 定期清理过期数据
        self._cleanup()

    def _cleanup(self):
        """清理窗口外的旧数据"""
        current_time = time.time()
        cutoff_time = current_time - self.window_size

        # 过滤掉过期的指标
        self.metrics = [m for m in self.metrics if m.timestamp > cutoff_time]

        # 重建类型索引
        self._type_index = defaultdict(list)
        for metric in self.metrics:
            self._type_index[metric.operation_type].append(metric)

    def get_stats(self) -> Dict[str, Any]:
        """
        获取总体统计信息

        Returns:
            包含统计信息的字典
        """
        self._cleanup()

        if not self.metrics:
            return {
                "total_operations": 0,
                "successful_operations": 0,
                "failed_operations": 0,
                "error_rate": 0.0,
                "avg_duration": 0.0,
                "max_duration": 0.0,
                "min_duration": 0.0,
                "uptime": time.time() - self.start_time
            }

        total = len(self.metrics)
        successful = sum(1 for m in self.metrics if m.success)
        failed = total - successful

        durations = [m.duration for m in self.metrics if m.duration > 0]

        return {
            "total_operations": total,
            "successful_operations": successful,
            "failed_operations": failed,
            "error_rate": failed / total if total > 0 else 0.0,
            "avg_duration": sum(durations) / len(durations) if durations else 0.0,
            "max_duration": max(durations) if durations else 0.0,
            "min_duration": min(durations) if durations else 0.0,
            "uptime": time.time() - self.start_time
        }

    def get_error_rate(self, operation_type: Optional[str] = None) -> float:
        """
        获取错误率

        Args:
            operation_type: 操作类型，如果为 None 则返回总体错误率

        Returns:
            错误率（0.0 - 1.0）
        """
        self._cleanup()

        if operation_type:
            metrics = self._type_index.get(operation_type, [])
        else:
            metrics = self.metrics

        if not metrics:
            return 0.0

        failed = sum(1 for m in metrics if not m.success)
        return failed / len(metrics)

    def get_avg_duration(self, operation_type: Optional[str] = None) -> float:
        """
        获取平均执行时间

        Args:
            operation_type: 操作类型，如果为 None 则返回总体平均

        Returns:
            平均执行时间（秒）
        """
        self._cleanup()

        if operation_type:
            metrics = self._type_index.get(operation_type, [])
        else:
            metrics = self.metrics

        durations = [m.duration for m in metrics if m.duration > 0]

        if not durations:
            return 0.0

        return sum(durations) / len(durations)

    def get_stats_by_type(self, operation_type: str) -> Dict[str, Any]:
        """
        获取指定操作类型的统计信息

        Args:
            operation_type: 操作类型

        Returns:
            统计信息字典
        """
        self._cleanup()

        metrics = self._type_index.get(operation_type, [])

        if not metrics:
            return {
                "type": operation_type,
                "total": 0,
                "success": 0,
                "failed": 0,
                "error_rate": 0.0,
                "avg_duration": 0.0
            }

        total = len(metrics)
        successful = sum(1 for m in metrics if m.success)
        failed = total - successful
        durations = [m.duration for m in metrics if m.duration > 0]

        return {
            "type": operation_type,
            "total": total,
            "success": successful,
            "failed": failed,
            "error_rate": failed / total if total > 0 else 0.0,
            "avg_duration": sum(durations) / len(durations) if durations else 0.0
        }

    def get_recent_errors(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取最近的错误

        Args:
            limit: 返回的最大错误数

        Returns:
            错误列表
        """
        self._cleanup()

        errors = [m for m in self.metrics if not m.success]
        errors.sort(key=lambda x: x.timestamp, reverse=True)

        return [
            {
                "timestamp": datetime.fromtimestamp(m.timestamp).isoformat(),
                "operation_type": m.operation_type,
                "operation_id": m.operation_id,
                "error": m.error,
                "duration": m.duration,
                "metadata": m.metadata
            }
            for m in errors[:limit]
        ]

    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        获取完整的指标摘要

        Returns:
            包含所有统计信息的字典
        """
        self._cleanup()

        stats = self.get_stats()
        stats["by_type"] = {
            op_type: self.get_stats_by_type(op_type)
            for op_type in self._type_index.keys()
        }
        stats["recent_errors"] = self.get_recent_errors()
        stats["window_size"] = self.window_size
        stats["metrics_count"] = len(self.metrics)

        return stats

    def reset(self):
        """重置所有指标"""
        self.metrics.clear()
        self._type_index.clear()
        self.start_time = time.time()
        logger.info("指标收集器已重置")


# 全局单例
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector(window_size: int = 300) -> MetricsCollector:
    """
    获取指标收集器单例

    Args:
        window_size: 滑动窗口大小（秒）

    Returns:
        MetricsCollector 实例
    """
    global _metrics_collector

    if _metrics_collector is None:
        _metrics_collector = MetricsCollector(window_size=window_size)

    return _metrics_collector
