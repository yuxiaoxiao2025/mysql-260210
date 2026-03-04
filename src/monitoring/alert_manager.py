"""
告警管理器

监控系统指标，在超过阈值时发送告警。
支持多种告警方式：日志、邮件、Webhook 等。
"""

import time
import smtplib
import logging
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

from .metrics_collector import MetricsCollector
from .logging_config import OperationLogger

logger = logging.getLogger(__name__)


@dataclass
class Alert:
    """告警数据"""
    type: str  # 告警类型：error_rate, avg_duration, etc.
    level: str  # 告警级别：warning, error, critical
    message: str  # 告警消息
    value: float  # 当前值
    threshold: float  # 阈值
    timestamp: str  # 告警时间
    metadata: Dict[str, Any] = field(default_factory=dict)


class AlertNotifier(ABC):
    """告警通知器抽象基类"""

    @abstractmethod
    def send(self, alerts: List[Alert]):
        """
        发送告警

        Args:
            alerts: 告警列表
        """
        pass


class LogNotifier(AlertNotifier):
    """
    日志通知器

    将告警记录到日志文件。
    """

    def __init__(self, operation_logger: Optional[OperationLogger] = None):
        """
        初始化日志通知器

        Args:
            operation_logger: 操作日志记录器
        """
        self.operation_logger = operation_logger or OperationLogger(
            logging.getLogger("alert")
        )

    def send(self, alerts: List[Alert]):
        """
        发送告警到日志

        Args:
            alerts: 告警列表
        """
        for alert in alerts:
            self.operation_logger.log_alert(
                alert_type=alert.type,
                level=alert.level,
                message=alert.message,
                value=alert.value,
                threshold=alert.threshold,
                **alert.metadata
            )


class EmailNotifier(AlertNotifier):
    """
    邮件通知器

    通过 SMTP 发送告警邮件。
    """

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        username: str,
        password: str,
        from_addr: str,
        to_addrs: List[str],
        use_tls: bool = True
    ):
        """
        初始化邮件通知器

        Args:
            smtp_host: SMTP 服务器地址
            smtp_port: SMTP 服务器端口
            username: SMTP 用户名
            password: SMTP 密码
            from_addr: 发件人地址
            to_addrs: 收件人地址列表
            use_tls: 是否使用 TLS
        """
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_addr = from_addr
        self.to_addrs = to_addrs
        self.use_tls = use_tls
        self.enabled = bool(smtp_host and username and password and to_addrs)

    def send(self, alerts: List[Alert]):
        """
        发送告警邮件

        Args:
            alerts: 告警列表
        """
        if not self.enabled or not alerts:
            return

        try:
            # 构建邮件内容
            subject = f"[告警] MySQL AI 系统告警 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

            # HTML 格式
            html_content = self._build_html_content(alerts)

            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.from_addr
            msg['To'] = ', '.join(self.to_addrs)

            # 添加 HTML 内容
            html_part = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(html_part)

            # 发送邮件
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)

            logger.info(f"已发送 {len(alerts)} 条告警邮件")

        except Exception as e:
            logger.error(f"发送告警邮件失败: {e}")

    def _build_html_content(self, alerts: List[Alert]) -> str:
        """构建 HTML 邮件内容"""
        rows = []
        for alert in alerts:
            color = {
                'warning': '#ff9800',
                'error': '#f44336',
                'critical': '#d32f2f'
            }.get(alert.level, '#2196f3')

            rows.append(f"""
                <tr style="border-bottom: 1px solid #ddd;">
                    <td style="padding: 8px;">{alert.type}</td>
                    <td style="padding: 8px; color: {color}; font-weight: bold;">{alert.level}</td>
                    <td style="padding: 8px;">{alert.message}</td>
                    <td style="padding: 8px;">{alert.value}</td>
                    <td style="padding: 8px;">{alert.threshold}</td>
                    <td style="padding: 8px;">{alert.timestamp}</td>
                </tr>
            """)

        html = f"""
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th {{ background-color: #4CAF50; color: white; padding: 12px; text-align: left; }}
                td {{ padding: 8px; }}
            </style>
        </head>
        <body>
            <h2>MySQL AI 系统告警</h2>
            <p>检测到以下 {len(alerts)} 条告警：</p>
            <table>
                <thead>
                    <tr>
                        <th>类型</th>
                        <th>级别</th>
                        <th>消息</th>
                        <th>当前值</th>
                        <th>阈值</th>
                        <th>时间</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows)}
                </tbody>
            </table>
            <p style="margin-top: 20px; color: #666;">
                请登录系统查看详细信息。
            </p>
        </body>
        </html>
        """

        return html


class WebhookNotifier(AlertNotifier):
    """
    Webhook 通知器

    通过 HTTP POST 发送告警到 Webhook URL。
    """

    def __init__(self, webhook_url: str, timeout: int = 10, headers: Optional[Dict[str, str]] = None):
        """
        初始化 Webhook 通知器

        Args:
            webhook_url: Webhook URL
            timeout: 请求超时时间（秒）
            headers: 自定义 HTTP 头
        """
        self.webhook_url = webhook_url
        self.timeout = timeout
        self.headers = headers or {}
        self.enabled = bool(webhook_url)

    def send(self, alerts: List[Alert]):
        """
        发送告警到 Webhook

        Args:
            alerts: 告警列表
        """
        if not self.enabled or not alerts:
            return

        try:
            import requests

            payload = {
                "service": "mysql_ai",
                "timestamp": datetime.now().isoformat(),
                "alert_count": len(alerts),
                "alerts": [
                    {
                        "type": alert.type,
                        "level": alert.level,
                        "message": alert.message,
                        "value": alert.value,
                        "threshold": alert.threshold,
                        "timestamp": alert.timestamp,
                        **alert.metadata
                    }
                    for alert in alerts
                ]
            }

            response = requests.post(
                self.webhook_url,
                json=payload,
                headers=self.headers,
                timeout=self.timeout
            )

            if response.status_code >= 200 and response.status_code < 300:
                logger.info(f"已发送 {len(alerts)} 条告警到 Webhook")
            else:
                logger.warning(f"Webhook 返回错误状态码: {response.status_code}")

        except ImportError:
            logger.warning("requests 库未安装，无法发送 Webhook 告警")
        except Exception as e:
            logger.error(f"发送 Webhook 告警失败: {e}")


class AlertManager:
    """
    告警管理器

    监控指标并在超过阈值时触发告警。
    支持告警去重、聚合和冷却期。
    """

    def __init__(
        self,
        metrics_collector: MetricsCollector,
        error_rate_threshold: float = 0.1,
        avg_duration_threshold: float = 10.0,
        cooldown_period: int = 60,
        dedup_window: int = 300,
        notifiers: Optional[List[AlertNotifier]] = None
    ):
        """
        初始化告警管理器

        Args:
            metrics_collector: 指标收集器
            error_rate_threshold: 错误率阈值（0.0 - 1.0）
            avg_duration_threshold: 平均执行时间阈值（秒）
            cooldown_period: 告警冷却期（秒），同一类型告警在此期间不重复发送
            dedup_window: 告警去重窗口（秒）
            notifiers: 告警通知器列表
        """
        self.metrics_collector = metrics_collector
        self.error_rate_threshold = error_rate_threshold
        self.avg_duration_threshold = avg_duration_threshold
        self.cooldown_period = cooldown_period
        self.dedup_window = dedup_window

        # 告警历史
        self.alert_history: List[Alert] = []
        self.last_alert_time: Dict[str, float] = {}  # 记录每种类型最后告警时间

        # 通知器
        self.notifiers = notifiers or [LogNotifier()]

        logger.info(f"告警管理器初始化完成，阈值: 错误率={error_rate_threshold}, "
                   f"执行时间={avg_duration_threshold}s")

    def check_thresholds(self) -> List[Alert]:
        """
        检查所有指标是否超过阈值

        Returns:
            超过阈值的告警列表
        """
        alerts = []

        # 检查错误率
        error_rate = self.metrics_collector.get_error_rate()
        if error_rate > self.error_rate_threshold:
            level = self._get_error_rate_level(error_rate)
            alert = Alert(
                type="error_rate",
                level=level,
                message=f"系统错误率过高 ({error_rate:.2%})",
                value=error_rate,
                threshold=self.error_rate_threshold,
                timestamp=datetime.now().isoformat(),
                metadata={"total_operations": self.metrics_collector.get_stats()["total_operations"]}
            )
            alerts.append(alert)

        # 检查平均执行时间
        avg_duration = self.metrics_collector.get_avg_duration()
        if avg_duration > self.avg_duration_threshold:
            level = self._get_duration_level(avg_duration)
            alert = Alert(
                type="avg_duration",
                level=level,
                message=f"平均执行时间过长 ({avg_duration:.2f}s)",
                value=avg_duration,
                threshold=self.avg_duration_threshold,
                timestamp=datetime.now().isoformat(),
                metadata={}
            )
            alerts.append(alert)

        # 检查各操作类型的错误率
        for op_type in self.metrics_collector._type_index.keys():
            type_stats = self.metrics_collector.get_stats_by_type(op_type)
            if type_stats["error_rate"] > self.error_rate_threshold:
                alert = Alert(
                    type="error_rate",
                    level="warning",
                    message=f"{op_type} 操作错误率过高 ({type_stats['error_rate']:.2%})",
                    value=type_stats["error_rate"],
                    threshold=self.error_rate_threshold,
                    timestamp=datetime.now().isoformat(),
                    metadata={"operation_type": op_type, "total": type_stats["total"]}
                )
                alerts.append(alert)

        # 去重和过滤
        filtered_alerts = self._filter_alerts(alerts)

        # 记录告警历史
        self.alert_history.extend(filtered_alerts)

        return filtered_alerts

    def _filter_alerts(self, alerts: List[Alert]) -> List[Alert]:
        """
        过滤告警（去重和冷却期）

        Args:
            alerts: 原始告警列表

        Returns:
            过滤后的告警列表
        """
        current_time = time.time()
        filtered = []

        for alert in alerts:
            alert_key = f"{alert.type}_{alert.level}"

            # 检查冷却期
            last_time = self.last_alert_time.get(alert_key, 0)
            if current_time - last_time < self.cooldown_period:
                continue

            # 检查去重窗口
            duplicate = False
            for old_alert in reversed(self.alert_history):
                if time.time() - datetime.fromisoformat(old_alert.timestamp).timestamp() > self.dedup_window:
                    break

                if (old_alert.type == alert.type and
                    old_alert.level == alert.level and
                    old_alert.message == alert.message):
                    duplicate = True
                    break

            if not duplicate:
                filtered.append(alert)
                self.last_alert_time[alert_key] = current_time

        return filtered

    def _get_error_rate_level(self, error_rate: float) -> str:
        """
        根据错误率确定告警级别

        Args:
            error_rate: 错误率

        Returns:
            告警级别
        """
        if error_rate >= 0.5:
            return "critical"
        elif error_rate >= 0.3:
            return "error"
        else:
            return "warning"

    def _get_duration_level(self, duration: float) -> str:
        """
        根据执行时间确定告警级别

        Args:
            duration: 执行时间

        Returns:
            告警级别
        """
        if duration >= self.avg_duration_threshold * 3:
            return "critical"
        elif duration >= self.avg_duration_threshold * 2:
            return "error"
        else:
            return "warning"

    def aggregate_alerts(self, alerts: List[Alert]) -> List[Alert]:
        """
        聚合同类型的告警

        Args:
            alerts: 告警列表

        Returns:
            聚合后的告警列表
        """
        aggregated = {}

        for alert in alerts:
            key = f"{alert.type}_{alert.level}"

            if key not in aggregated:
                aggregated[key] = alert
            else:
                # 更新数量和最新时间
                aggregated[key].metadata.setdefault("count", 1)
                aggregated[key].metadata["count"] += 1
                aggregated[key].timestamp = alert.timestamp

        return list(aggregated.values())

    def send_alerts(self, alerts: List[Alert]) -> List[Alert]:
        """
        发送告警

        Args:
            alerts: 告警列表

        Returns:
            实际发送的告警列表
        """
        if not alerts:
            return []

        # 聚合告警
        aggregated_alerts = self.aggregate_alerts(alerts)

        # 发送到所有通知器
        for notifier in self.notifiers:
            try:
                notifier.send(aggregated_alerts)
            except Exception as e:
                logger.error(f"告警发送失败: {e}")

        return aggregated_alerts

    def check_and_alert(self) -> List[Alert]:
        """
        检查阈值并发送告警

        Returns:
            发送的告警列表
        """
        alerts = self.check_thresholds()
        return self.send_alerts(alerts)

    def get_alert_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取告警历史

        Args:
            limit: 返回的最大告警数

        Returns:
            告警历史列表
        """
        return [
            {
                "type": alert.type,
                "level": alert.level,
                "message": alert.message,
                "value": alert.value,
                "threshold": alert.threshold,
                "timestamp": alert.timestamp,
                **alert.metadata
            }
            for alert in reversed(self.alert_history[-limit:])
        ]
