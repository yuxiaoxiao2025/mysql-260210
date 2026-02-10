服务器名称：漕河泾停车云
主机IP：101.231.132.10
端口：33306
用户名：haplink
密码：ER#$R353e4Aba3
数据库名称：cloudinterface
下属的表名称：
config                  新版云云接口V2.0.0版本程序url配置表

数据库名称：parkcloud
下属表名称：
role_address_interface  云云对接-接口地址设置表
cloud_fixed_plate       固定车牌表
cloud_fixed_plate_park  固定车-场库关联表
cloud_operator          登录人员表

---

# Python 连接 MySQL 最佳实践指南

## 一、PyMySQL vs SQLAlchemy 对比

### 1.1 PyMySQL 简介

**PyMySQL** 是一个纯 Python 实现的 MySQL 客户端库，基于 PEP 249 标准（Python Database API Specification v2.0）。

**优点：**
- ✅ 纯 Python 实现，无需额外编译依赖
- ✅ 轻量级，安装简单 (`pip install pymysql`)
- ✅ 与 MySQLdb API 兼容，易于迁移
- ✅ 支持 Python 3.x
- ✅ 活跃的社区维护

**缺点：**
- ❌ 无内置连接池支持
- ❌ 需要手动管理连接生命周期
- ❌ 缺乏 ORM 功能
- ❌ 复杂查询需要手写 SQL

**适用场景：**
- 简单的数据库操作脚本
- 不需要 ORM 的数据处理任务
- 对性能要求不高的应用

### 1.2 SQLAlchemy 简介

**SQLAlchemy** 是 Python 最强大的数据库工具包，提供 ORM 和 Core 两种使用方式。

**优点：**
- ✅ 内置连接池管理（QueuePool）
- ✅ 支持 ORM 和原生 SQL
- ✅ 数据库无关的抽象层
- ✅ 强大的查询构建器
- ✅ 自动连接回收和心跳检测
- ✅ 事务管理完善

**缺点：**
- ❌ 学习曲线较陡峭
- ❌ 相对重量级
- ❌ 需要额外安装驱动（如 pymysql）

**适用场景：**
- Web 应用后端
- 需要连接池的生产环境
- 复杂的数据模型和查询
- 企业级应用

### 1.3 选择建议

| 场景 | 推荐方案 |
|------|----------|
| 简单脚本/数据导出 | PyMySQL |
| Web 应用/生产环境 | SQLAlchemy + PyMySQL |
| 需要 ORM | SQLAlchemy |
| 高并发应用 | SQLAlchemy（连接池） |
| 快速原型开发 | PyMySQL |

**结论：** 对于需要连接远程 MySQL 并导出数据到 Excel 的场景，推荐使用 **SQLAlchemy + PyMySQL**，因为它提供更好的连接管理和错误处理机制。

---

## 二、数据库连接池最佳实践

### 2.1 为什么需要连接池？

- 避免频繁创建/销毁连接的开销
- 限制并发连接数，防止数据库过载
- 自动管理连接生命周期
- 支持连接复用

### 2.2 SQLAlchemy 连接池配置

```python
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    "mysql+pymysql://user:password@host:port/database",
    # 连接池配置
    poolclass=QueuePool,           # 连接池类型
    pool_size=10,                  # 保持的连接数（默认5）
    max_overflow=20,               # 超出pool_size的最大连接数
    pool_recycle=3600,             # 连接回收时间（秒）
    pool_pre_ping=True,            # 连接前ping检测
    pool_timeout=30,               # 获取连接超时时间（秒）
    pool_use_lifo=True,            # LIFO模式，减少连接使用
    # 其他配置
    echo=False,                    # 是否打印SQL
    connect_args={
        'connect_timeout': 10,     # 连接超时
        'read_timeout': 30,        # 读取超时
        'write_timeout': 30,       # 写入超时
    }
)
```

### 2.3 连接池参数详解

| 参数 | 说明 | 推荐值 |
|------|------|--------|
| pool_size | 保持的空闲连接数 | 5-20 |
| max_overflow | 临时额外连接数 | 10-30 |
| pool_recycle | 连接最大存活时间 | 3600（1小时） |
| pool_pre_ping | 使用前检测连接有效性 | True |
| pool_timeout | 获取连接等待时间 | 30秒 |

---

## 三、连接配置和安全实践

### 3.1 安全配置清单

```python
# ✅ 推荐：使用环境变量存储敏感信息
import os

DB_CONFIG = {
    'host': os.getenv('DB_HOST', '101.231.132.10'),
    'port': int(os.getenv('DB_PORT', '33306')),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME'),
    'charset': 'utf8mb4',  # 支持完整UTF-8（包括emoji）
}
```

### 3.2 连接参数最佳实践

```python
connect_args = {
    # 超时配置
    'connect_timeout': 10,      # 连接超时（秒）
    'read_timeout': 30,         # 读取超时（秒）
    'write_timeout': 30,        # 写入超时（秒）
    
    # SSL配置（生产环境必需）
    'ssl': {
        'ca': '/path/to/ca.pem',
        'cert': '/path/to/client-cert.pem',
        'key': '/path/to/client-key.pem',
    },
    'ssl_verify_cert': True,
    'ssl_verify_identity': True,
    
    # 字符集
    'charset': 'utf8mb4',
}
```

### 3.3 安全注意事项

- ✅ 永远不要硬编码密码
- ✅ 使用环境变量或密钥管理服务
- ✅ 生产环境启用 SSL/TLS
- ✅ 限制数据库用户权限（最小权限原则）
- ✅ 使用只读用户进行数据导出
- ✅ 定期轮换密码

---

## 四、完整代码示例

### 4.1 SQLAlchemy 方案（推荐）

```python
"""
MySQL 数据导出工具 - SQLAlchemy 方案
适用于：生产环境、需要连接池、复杂查询
"""

import os
import logging
from contextlib import contextmanager
from typing import List, Dict, Any, Generator

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import QueuePool
import pandas as pd

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MySQLExporter:
    """MySQL 数据导出器"""
    
    def __init__(self):
        # 从环境变量读取配置
        self.db_config = {
            'host': os.getenv('DB_HOST', '101.231.132.10'),
            'port': int(os.getenv('DB_PORT', '33306')),
            'user': os.getenv('DB_USER'),
            'password': os.getenv('DB_PASSWORD'),
            'database': os.getenv('DB_NAME'),
        }
        
        # 验证配置
        if not all([self.db_config['user'], self.db_config['password']]):
            raise ValueError("数据库用户名和密码必须设置")
        
        # 创建引擎
        self.engine = self._create_engine()
    
    def _create_engine(self):
        """创建 SQLAlchemy 引擎（带连接池）"""
        connection_string = (
            f"mysql+pymysql://{self.db_config['user']}:{self.db_config['password']}"
            f"@{self.db_config['host']}:{self.db_config['port']}"
            f"/{self.db_config['database']}"
        )
        
        return create_engine(
            connection_string,
            # 连接池配置
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_recycle=3600,
            pool_pre_ping=True,
            pool_timeout=30,
            pool_use_lifo=True,
            # 连接参数
            connect_args={
                'connect_timeout': 10,
                'read_timeout': 30,
                'write_timeout': 30,
                'charset': 'utf8mb4',
            },
            echo=False,
        )
    
    @contextmanager
    def get_connection(self):
        """获取数据库连接的上下文管理器"""
        conn = None
        try:
            conn = self.engine.connect()
            yield conn
        except SQLAlchemyError as e:
            logger.error(f"数据库连接错误: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def execute_query(self, sql: str, params: Dict = None) -> List[Dict]:
        """
        执行查询并返回结果
        
        Args:
            sql: SQL 查询语句
            params: 查询参数（防止SQL注入）
        
        Returns:
            查询结果列表
        """
        with self.get_connection() as conn:
            try:
                result = conn.execute(text(sql), params or {})
                # 转换为字典列表
                columns = result.keys()
                return [dict(zip(columns, row)) for row in result.fetchall()]
            except SQLAlchemyError as e:
                logger.error(f"查询执行错误: {e}")
                raise
    
    def execute_query_stream(self, sql: str, params: Dict = None, 
                            batch_size: int = 1000) -> Generator[Dict, None, None]:
        """
        流式执行查询（适合大数据量）
        
        Args:
            sql: SQL 查询语句
            params: 查询参数
            batch_size: 每批处理数量
        
        Yields:
            单行数据字典
        """
        with self.get_connection() as conn:
            try:
                result = conn.execution_options(stream_results=True).execute(
                    text(sql), params or {}
                )
                columns = result.keys()
                
                for row in result:
                    yield dict(zip(columns, row))
                    
            except SQLAlchemyError as e:
                logger.error(f"流式查询错误: {e}")
                raise
    
    def export_to_excel(self, sql: str, output_file: str, 
                       sheet_name: str = 'Sheet1') -> None:
        """
        导出查询结果到 Excel
        
        Args:
            sql: SQL 查询语句
            output_file: 输出文件路径
            sheet_name: Excel 工作表名称
        """
        logger.info(f"开始导出数据到 {output_file}")
        
        # 使用 pandas 读取数据
        with self.get_connection() as conn:
            df = pd.read_sql(sql, conn)
        
        # 导出到 Excel
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
            
            # 获取工作表并调整列宽
            worksheet = writer.sheets[sheet_name]
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        logger.info(f"导出完成，共 {len(df)} 行数据")
    
    def close(self):
        """关闭连接池"""
        self.engine.dispose()
        logger.info("数据库连接池已关闭")


# 使用示例
if __name__ == '__main__':
    # 设置环境变量（实际使用时应从配置文件或密钥管理获取）
    os.environ['DB_USER'] = 'your_username'
    os.environ['DB_PASSWORD'] = 'your_password'
    os.environ['DB_NAME'] = 'your_database'
    
    exporter = MySQLExporter()
    
    try:
        # 示例1：简单查询
        results = exporter.execute_query(
            "SELECT * FROM users WHERE status = :status",
            {'status': 'active'}
        )
        print(f"查询到 {len(results)} 条记录")
        
        # 示例2：流式查询（大数据量）
        for row in exporter.execute_query_stream("SELECT * FROM large_table"):
            # 处理每一行数据
            pass
        
        # 示例3：导出到 Excel
        exporter.export_to_excel(
            "SELECT * FROM sales_data WHERE date >= '2024-01-01'",
            "sales_report.xlsx",
            sheet_name="销售数据"
        )
        
    finally:
        exporter.close()
```

### 4.2 PyMySQL 方案（简单场景）

```python
"""
MySQL 数据导出工具 - PyMySQL 方案
适用于：简单脚本、一次性任务、无需连接池
"""

import os
import logging
from contextlib import contextmanager
from typing import List, Dict, Any, Optional

import pymysql
from pymysql.cursors import DictCursor
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MySQLClient:
    """PyMySQL 客户端封装"""
    
    def __init__(self):
        self.config = {
            'host': os.getenv('DB_HOST', '101.231.132.10'),
            'port': int(os.getenv('DB_PORT', '33306')),
            'user': os.getenv('DB_USER'),
            'password': os.getenv('DB_PASSWORD'),
            'database': os.getenv('DB_NAME'),
            'charset': 'utf8mb4',
            'cursorclass': DictCursor,
            'connect_timeout': 10,
            'read_timeout': 30,
            'write_timeout': 30,
            'autocommit': True,
        }
        
        if not all([self.config['user'], self.config['password']]):
            raise ValueError("数据库用户名和密码必须设置")
    
    @contextmanager
    def get_connection(self):
        """获取连接的上下文管理器"""
        conn = None
        try:
            conn = pymysql.connect(**self.config)
            # 检查连接是否有效
            conn.ping(reconnect=True)
            yield conn
        except pymysql.Error as e:
            logger.error(f"数据库错误: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def execute_query(self, sql: str, params: tuple = None) -> List[Dict]:
        """执行查询"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                try:
                    cursor.execute(sql, params)
                    return cursor.fetchall()
                except pymysql.Error as e:
                    logger.error(f"查询错误: {e}")
                    raise
    
    def execute_many(self, sql: str, params_list: List[tuple]) -> int:
        """批量执行"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                try:
                    affected = cursor.executemany(sql, params_list)
                    conn.commit()
                    return affected
                except pymysql.Error as e:
                    conn.rollback()
                    logger.error(f"批量执行错误: {e}")
                    raise
    
    def export_to_excel(self, sql: str, output_file: str,
                       sheet_name: str = 'Sheet1') -> None:
        """导出到 Excel"""
        with self.get_connection() as conn:
            df = pd.read_sql(sql, conn)
        
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        logger.info(f"导出完成: {len(df)} 行")


# 使用示例
if __name__ == '__main__':
    os.environ['DB_USER'] = 'your_username'
    os.environ['DB_PASSWORD'] = 'your_password'
    os.environ['DB_NAME'] = 'your_database'
    
    client = MySQLClient()
    
    try:
        # 查询示例
        results = client.execute_query(
            "SELECT * FROM users WHERE age > %s",
            (18,)
        )
        print(f"找到 {len(results)} 个用户")
        
        # 导出示例
        client.export_to_excel(
            "SELECT * FROM orders",
            "orders.xlsx"
        )
    except Exception as e:
        logger.error(f"操作失败: {e}")
```

---

## 五、错误处理机制

### 5.1 PyMySQL 异常处理

```python
import pymysql
from pymysql import (
    Error, InterfaceError, DatabaseError, DataError,
    OperationalError, IntegrityError, InternalError,
    ProgrammingError, NotSupportedError
)

def handle_mysql_error(func):
    """MySQL 错误处理装饰器"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except IntegrityError as e:
            # 主键冲突、外键约束
            error_code, error_msg = e.args
            if error_code == 1062:
                logger.error(f"记录已存在: {error_msg}")
            elif error_code == 1452:
                logger.error(f"外键约束失败: {error_msg}")
            raise
        except ProgrammingError as e:
            # SQL语法错误
            logger.error(f"SQL语法错误: {e}")
            raise
        except OperationalError as e:
            # 连接问题
            logger.error(f"数据库连接错误: {e}")
            raise
        except DataError as e:
            # 数据类型错误
            logger.error(f"数据错误: {e}")
            raise
        except DatabaseError as e:
            logger.error(f"数据库错误: {e}")
            raise
    return wrapper
```

### 5.2 SQLAlchemy 异常处理

```python
from sqlalchemy.exc import (
    SQLAlchemyError, IntegrityError, OperationalError,
    ProgrammingError, DatabaseError, TimeoutError
)

def handle_sqlalchemy_error(func):
    """SQLAlchemy 错误处理装饰器"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except IntegrityError as e:
            logger.error(f"数据完整性错误: {e}")
            raise
        except OperationalError as e:
            logger.error(f"操作错误（连接问题）: {e}")
            raise
        except ProgrammingError as e:
            logger.error(f"编程错误（SQL语法）: {e}")
            raise
        except TimeoutError as e:
            logger.error(f"连接超时: {e}")
            raise
        except SQLAlchemyError as e:
            logger.error(f"SQLAlchemy错误: {e}")
            raise
    return wrapper
```

---

## 六、最佳实践清单

### 6.1 连接管理

- [ ] 使用连接池（SQLAlchemy）或连接复用（PyMySQL）
- [ ] 配置连接超时和读取超时
- [ ] 启用连接健康检查（pool_pre_ping）
- [ ] 设置连接回收时间（pool_recycle）
- [ ] 使用上下文管理器（with语句）确保连接关闭

### 6.2 安全配置

- [ ] 使用环境变量存储密码
- [ ] 生产环境启用 SSL/TLS
- [ ] 使用只读用户进行数据导出
- [ ] 限制数据库用户权限
- [ ] 定期更换密码

### 6.3 查询优化

- [ ] 使用参数化查询防止 SQL 注入
- [ ] 大数据量使用流式查询
- [ ] 为常用查询添加索引
- [ ] 限制查询结果集大小
- [ ] 避免 SELECT *

### 6.4 错误处理

- [ ] 捕获特定异常类型
- [ ] 实现重试机制（指数退避）
- [ ] 记录详细的错误日志
- [ ] 设置合理的超时时间
- [ ] 实现熔断机制（防止级联故障）

### 6.5 性能优化

- [ ] 使用连接池
- [ ] 批量插入代替单条插入
- [ ] 使用 SSDictCursor 处理大结果集
- [ ] 合理设置连接池大小
- [ ] 使用 LIFO 模式减少连接使用

---

## 七、针对远程 MySQL (101.231.132.10:33306) 的特别建议

### 7.1 网络优化

```python
# 增加超时时间（远程连接可能需要更长时间）
connect_args = {
    'connect_timeout': 30,    # 连接超时增加到30秒
    'read_timeout': 60,       # 读取超时增加到60秒
    'write_timeout': 60,      # 写入超时增加到60秒
}
```

### 7.2 连接稳定性

```python
# 启用更强的连接检测
engine = create_engine(
    connection_string,
    pool_pre_ping=True,        # 使用前检测连接
    pool_recycle=1800,         # 30分钟回收连接（防止防火墙断开）
    pool_use_lifo=True,        # LIFO模式
)
```

### 7.3 数据导出优化

```python
# 分批次导出大数据量
def export_large_table(exporter, table_name, output_file, batch_size=10000):
    """分批次导出大表"""
    offset = 0
    first_batch = True
    
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        while True:
            sql = f"SELECT * FROM {table_name} LIMIT {batch_size} OFFSET {offset}"
            df = pd.read_sql(sql, exporter.engine)
            
            if df.empty:
                break
            
            # 第一批创建sheet，后续追加
            if first_batch:
                df.to_excel(writer, sheet_name='Data', index=False)
                first_batch = False
            else:
                # 读取现有数据并追加
                start_row = writer.sheets['Data'].max_row
                df.to_excel(writer, sheet_name='Data', 
                           startrow=start_row, index=False, header=False)
            
            offset += batch_size
            logger.info(f"已导出 {offset} 行")
```

---

## 八、依赖安装

```bash
# SQLAlchemy 方案
pip install sqlalchemy pymysql pandas openpyxl

# PyMySQL 方案
pip install pymysql pandas openpyxl
```

---

## 总结

对于连接远程 MySQL (101.231.132.10:33306) 并导出数据到 Excel 的需求：

1. **推荐方案**：SQLAlchemy + PyMySQL
   - 更好的连接池管理
   - 自动连接回收和检测
   - 更完善的错误处理

2. **关键配置**：
   - 增加超时时间（远程连接）
   - 启用 pool_pre_ping
   - 使用环境变量存储密码
   - 分批次处理大数据量

3. **安全建议**：
   - 使用只读用户
   - 启用 SSL（如果支持）
   - 限制用户权限
