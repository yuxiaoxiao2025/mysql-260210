# 漕河泾停车云数据导出工具 - API 参考文档

## 目录

1. [模块概览](#模块概览)
2. [核心模块](#核心模块)
3. [监控模块](#监控模块)
4. [执行器模块](#执行器模块)
5. [意图识别模块](#意图识别模块)
6. [知识库模块](#知识库模块)
7. [数据库管理模块](#数据库管理模块)
8. [示例代码](#示例代码)

---

## 模块概览

### 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      Main Application                   │
└─────────────────────────────────────────────────────────────┘
                          │
         ┌────────────────┼────────────────┐
         │                │                │
    ┌────▼────┐    ┌────▼────┐    ┌────▼────┐
    │ Intent  │    │Executor │    │ Monitor │
    │Recognizer│    │         │    │         │
    └────┬────┘    └────┬────┘    └────┬────┘
         │                │                │
    ┌────▼────┐    ┌────▼────┐    ┌────▼────┐
    │Knowledge│    │Database │    │ Metrics │
    │  Loader │    │ Manager │    │Collector│
    └─────────┘    └─────────┘    └─────────┘
```

---

## 核心模块

### 1. DatabaseManager (数据库管理器)

**位置**: `src/db_manager.py`

#### 类定义

```python
class DatabaseManager:
    """数据库连接和操作管理器"""

    def __init__(self):
        """初始化数据库连接池"""

    def get_connection(self):
        """获取原始数据库连接"""

    def execute_query(self, sql: str, params: Optional[Dict] = None) -> pd.DataFrame:
        """
        执行 SQL 查询并返回 DataFrame

        Args:
            sql: SQL 语句，支持命名参数 (:param_name)
            params: 参数字典，可选

        Returns:
            DataFrame 查询结果
        """

    def execute_update(self, sql: str, params: Optional[Dict] = None) -> int:
        """
        执行变更 SQL (INSERT/UPDATE/DELETE) 并返回影响行数

        Args:
            sql: SQL 语句，支持命名参数
            params: 参数字典，可选

        Returns:
            受影响的行数 (int)
        """

    def get_all_tables(self) -> List[str]:
        """获取所有表名"""

    def get_table_schema(self, table_name: str, schema: str = None) -> List[Dict]:
        """获取表结构信息"""

    def execute_in_transaction(
        self,
        mutation_sql: str,
        preview_sql: str,
        key_columns: List[str],
        commit: bool = False,
        mutation_params: Optional[Dict] = None,
        preview_params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        在事务内执行变更操作，返回 Before/After 数据和差异摘要

        Args:
            mutation_sql: 要执行的变更 SQL
            preview_sql: 用于查看变更前后状态的查询 SQL
            key_columns: 用于对齐行的主键列列表
            commit: 是否提交事务，默认 False（回滚）
            mutation_params: 变更 SQL 的参数字典，可选
            preview_params: 预览 SQL 的参数字典，可选

        Returns:
            包含 before, after, diff_summary, committed 的字典
        """

    def execute_multi_step_transaction(
        self,
        sql_steps: List[Tuple[str, Optional[Dict]]],
        commit: bool = True
    ) -> Dict[str, Any]:
        """
        执行多步骤事务 - 所有步骤在同一事务中

        Args:
            sql_steps: SQL 步骤列表，每个元素是 (sql, params) 元组
            commit: 是否提交事务

        Returns:
            包含 success, steps_executed, affected_rows, error, committed 的字典
        """
```

#### 使用示例

```python
from src.db_manager import DatabaseManager

# 初始化
db = DatabaseManager()

# 查询数据
df = db.execute_query(
    "SELECT * FROM cloud_fixed_plate WHERE plate = :plate",
    params={"plate": "沪A12345"}
)

# 更新数据
affected_rows = db.execute_update(
    "UPDATE cloud_fixed_plate SET memo = :memo WHERE plate = :plate",
    params={"memo": "VIP客户", "plate": "沪A12345"}
)

# 多步骤事务
result = db.execute_multi_step_transaction([
    ("UPDATE table1 SET col = :val WHERE id = :id", {"val": 1, "id": 1}),
    ("UPDATE table2 SET col = :val WHERE id = :id", {"val": 2, "id": 2}),
], commit=True)
```

---

### 2. OperationExecutor (操作执行器)

**位置**: `src/executor/operation_executor.py`

#### 类定义

```python
class OperationExecutor:
    """业务操作执行器"""

    def __init__(self, db_manager, knowledge_loader):
        """
        初始化操作执行器

        Args:
            db_manager: 数据库管理器
            knowledge_loader: 知识库加载器
        """

    def execute_operation(
        self,
        operation_id: str,
        params: Dict[str, Any],
        preview_only: bool = True,
        auto_commit: bool = False
    ) -> ExecutionResult:
        """
        执行业务操作

        Args:
            operation_id: 操作ID
            params: 参数字典
            preview_only: 是否仅预览（不执行）
            auto_commit: 是否自动提交（跳过确认）

        Returns:
            ExecutionResult 执行结果
        """

    def format_preview_output(self, result: ExecutionResult) -> str:
        """
        格式化预览输出

        Args:
            result: 执行结果

        Returns:
            格式化的文本
        """
```

#### 数据类

```python
@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    operation_id: str
    operation_name: str
    previews: List[StepPreview] = field(default_factory=list)
    executed: bool = False
    error: Optional[str] = None
    summary: str = ""
```

#### 使用示例

```python
from src.executor import OperationExecutor

# 初始化
executor = OperationExecutor(db_manager, knowledge_loader)

# 执行操作（预览）
result = executor.execute_operation(
    operation_id="plate_distribute",
    params={"plate": "沪A12345", "park_name": "国际商务中心"},
    preview_only=True
)

if result.success:
    print(result.summary)

    # 确认后执行
    result = executor.execute_operation(
        operation_id="plate_distribute",
        params={"plate": "沪A12345", "park_name": "国际商务中心"},
        preview_only=False,
        auto_commit=True
    )
```

---

## 监控模块

### 3. MetricsCollector (指标收集器)

**位置**: `src/monitoring/metrics_collector.py`

#### 类定义

```python
class MetricsCollector:
    """指标收集器，使用滑动窗口机制"""

    def __init__(self, window_size: int = 300):
        """
        初始化指标收集器

        Args:
            window_size: 滑动窗口大小（秒），默认 5 分钟
        """

    def record_operation(
        self,
        operation_type: str,
        success: bool,
        duration: float,
        operation_id: Optional[str] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """记录操作指标"""

    def get_stats(self) -> Dict[str, Any]:
        """获取总体统计信息"""

    def get_error_rate(self, operation_type: Optional[str] = None) -> float:
        """获取错误率"""

    def get_avg_duration(self, operation_type: Optional[str] = None) -> float:
        """获取平均执行时间"""

    def get_stats_by_type(self, operation_type: str) -> Dict[str, Any]:
        """获取指定操作类型的统计信息"""

    def get_recent_errors(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近的错误"""

    def get_metrics_summary(self) -> Dict[str, Any]:
        """获取完整的指标摘要"""

    def reset(self):
        """重置所有指标"""
```

#### 使用示例

```python
from src.monitoring import MetricsCollector

# 初始化
collector = MetricsCollector(window_size=300)

# 记录操作
collector.record_operation(
    operation_type="query",
    success=True,
    duration=1.5,
    operation_id="plate_query",
    metadata={"plate": "沪A12345"}
)

# 获取统计
stats = collector.get_stats()
print(f"错误率: {stats['error_rate']:.2%}")
print(f"平均执行时间: {stats['avg_duration']:.2f}秒")
```

---

### 4. AlertManager (告警管理器)

**位置**: `src/monitoring/alert_manager.py`

#### 类定义

```python
class AlertManager:
    """告警管理器"""

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
            cooldown_period: 告警冷却期（秒）
            dedup_window: 告警去重窗口（秒）
            notifiers: 告警通知器列表
        """

    def check_thresholds(self) -> List[Alert]:
        """检查所有指标是否超过阈值"""

    def check_and_alert(self) -> List[Alert]:
        """检查阈值并发送告警"""

    def get_alert_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取告警历史"""
```

#### 通知器类

```python
class LogNotifier(AlertNotifier):
    """日志通知器"""

class EmailNotifier(AlertNotifier):
    """邮件通知器"""

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

class WebhookNotifier(AlertNotifier):
    """Webhook 通知器"""

    def __init__(
        self,
        webhook_url: str,
        timeout: int = 10,
        headers: Optional[Dict[str, str]] = None
    ):
```

#### 使用示例

```python
from src.monitoring import AlertManager, MetricsCollector, LogNotifier, EmailNotifier

# 初始化
collector = MetricsCollector()

# 创建告警管理器
alert_manager = AlertManager(
    metrics_collector=collector,
    error_rate_threshold=0.1,
    avg_duration_threshold=5.0,
    cooldown_period=60,
    notifiers=[
        LogNotifier(),
        EmailNotifier(
            smtp_host="smtp.example.com",
            smtp_port=587,
            username="alert@example.com",
            password="password",
            from_addr="alert@example.com",
            to_addrs=["admin@example.com"]
        )
    ]
)

# 检查并告警
alerts = alert_manager.check_and_alert()
if alerts:
    print(f"检测到 {len(alerts)} 条告警")
```

---

## 执行器模块

### 5. IntentRecognizer (意图识别器)

**位置**: `src/intent/intent_recognizer.py`

#### 类定义

```python
class IntentRecognizer:
    """意图识别器"""

    def __init__(self, llm, knowledge_loader):
        """
        初始化意图识别器

        Args:
            llm: LLM 客户端
            knowledge_loader: 知识库加载器
        """

    def recognize(self, user_input: str) -> IntentResult:
        """
        识别用户意图

        Args:
            user_input: 用户输入

        Returns:
            IntentResult 意图识别结果
        """

    def get_operation_help(self, operation_name: str) -> str:
        """获取操作帮助信息"""

    def list_available_operations(self) -> str:
        """列出所有可用操作"""
```

#### 数据类

```python
@dataclass
class IntentResult:
    """意图识别结果"""
    is_matched: bool
    operation_id: Optional[str]
    operation_name: Optional[str]
    params: Dict[str, Any]
    confidence: float
    missing_params: List[str]
    suggestions: List[str]
    fallback_sql: Optional[str]
    reasoning: Optional[str]
```

#### 使用示例

```python
from src.intent import IntentRecognizer

# 初始化
recognizer = IntentRecognizer(llm, knowledge_loader)

# 识别意图
result = recognizer.recognize("查询车牌 沪A12345")

if result.is_matched:
    print(f"识别为: {result.operation_name}")
    print(f"参数: {result.params}")
    print(f"置信度: {result.confidence:.2%}")
```

---

## 知识库模块

### 6. KnowledgeLoader (知识库加载器)

**位置**: `src/knowledge/knowledge_loader.py`

#### 类定义

```python
class KnowledgeLoader:
    """业务知识库加载器"""

    def __init__(self, db_manager: DatabaseManager):
        """
        初始化知识库加载器

        Args:
            db_manager: 数据库管理器
        """

    def get_operation(self, operation_id: str) -> Optional[Operation]:
        """获取操作模板"""

    def get_all_operations(self) -> List[Operation]:
        """获取所有操作模板"""

    def get_enum_values_flat(self, enum_name: str) -> List[str]:
        """获取枚举值的扁平列表"""

    def lookup_enum_value(self, enum_name: str, value: str) -> Optional[str]:
        """查找枚举值"""
```

#### 使用示例

```python
from src.knowledge import KnowledgeLoader

# 初始化
loader = KnowledgeLoader(db_manager)

# 获取操作
operation = loader.get_operation("plate_distribute")
if operation:
    print(f"操作名称: {operation.name}")
    print(f"操作描述: {operation.description}")
    print(f"参数: {[p.name for p in operation.params]}")

# 获取枚举值
parks = loader.get_enum_values_flat("park_names")
print(f"可用场库: {', '.join(parks)}")
```

---

## 示例代码

### 示例 1: 完整的操作流程

```python
from src.db_manager import DatabaseManager
from src.knowledge import KnowledgeLoader
from src.intent import IntentRecognizer
from src.executor import OperationExecutor
from src.monitoring import MetricsCollector, AlertManager, LogNotifier
from src.llm_client import LLMClient

# 初始化组件
db = DatabaseManager()
knowledge_loader = KnowledgeLoader(db)
llm = LLMClient()
recognizer = IntentRecognizer(llm, knowledge_loader)
executor = OperationExecutor(db, knowledge_loader)

# 初始化监控
metrics_collector = MetricsCollector(window_size=300)
alert_manager = AlertManager(
    metrics_collector=metrics_collector,
    error_rate_threshold=0.1,
    avg_duration_threshold=5.0,
    notifiers=[LogNotifier()]
)

# 执行操作
user_input = "查询车牌 沪A12345"

# 识别意图
intent_result = recognizer.recognize(user_input)

if intent_result.is_matched:
    # 执行操作
    result = executor.execute_operation(
        operation_id=intent_result.operation_id,
        params=intent_result.params,
        preview_only=False,
        auto_commit=True
    )

    # 记录指标
    metrics_collector.record_operation(
        operation_type="query",
        success=result.success,
        duration=1.5,
        operation_id=intent_result.operation_id
    )

    # 检查告警
    alerts = alert_manager.check_and_alert()
```

### 示例 2: 自定义告警通知

```python
from src.monitoring import AlertManager, AlertNotifier, Alert

class CustomNotifier(AlertNotifier):
    """自定义告警通知器"""

    def send(self, alerts: List[Alert]):
        for alert in alerts:
            print(f"[自定义告警] {alert.type}: {alert.message}")

# 使用自定义通知器
alert_manager = AlertManager(
    metrics_collector=metrics_collector,
    notifiers=[CustomNotifier()]
)
```

### 示例 3: 批量操作

```python
from src.db_manager import DatabaseManager

db = DatabaseManager()

# 批量下发车牌
plates = ["沪A12345", "沪B67890", "沪C13579"]
park_name = "国际商务中心"

# 构造 SQL 步骤
sql_steps = []
for plate in plates:
    sql_steps.append((
        "INSERT INTO park_plate_binding (plate, park_name, create_time) VALUES (:plate, :park_name, NOW())",
        {"plate": plate, "park_name": park_name}
    ))

# 执行多步骤事务
result = db.execute_multi_step_transaction(sql_steps, commit=True)

if result["success"]:
    print(f"成功下发 {result['steps_executed']} 个车牌")
else:
    print(f"下发失败: {result['error']}")
```

---

**文档版本**: 1.0
**最后更新**: 2026-03-04
