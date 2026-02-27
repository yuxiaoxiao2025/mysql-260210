# SQLAlchemy 最佳实践

## 概述
使用 SQLAlchemy Core 进行高效的数据库操作，本项目使用非 ORM 方式。

## 连接管理

### 创建引擎
```python
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

def create_db_engine():
    """创建数据库引擎"""
    connection_string = get_db_url()

    engine = create_engine(
        connection_string,
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=3600,  # 1 小时回收连接
        pool_pre_ping=True,  # 连接前检查连接有效性
        echo=False  # 生产环境关闭 SQL 日志
    )
    return engine
```

### 使用上下文管理器
```python
from contextlib import contextmanager

@contextmanager
def get_db_connection():
    """获取数据库连接的上下文管理器"""
    engine = create_db_engine()
    connection = engine.connect()
    try:
        yield connection
    finally:
        connection.close()
        engine.dispose()
```

## 查询构建

### 基本 SELECT 查询
```python
from sqlalchemy import select, text

def execute_query(sql: str, params: dict = None) -> pd.DataFrame:
    """执行查询并返回 DataFrame"""
    engine = create_db_engine()

    with engine.connect() as conn:
        result = conn.execute(text(sql), params or {})
        df = pd.DataFrame(result.fetchall(), columns=result.keys())
        return df
```

### 使用 SQLAlchemy Core 构建查询
```python
from sqlalchemy import Table, MetaData, select, and_, or_

def get_active_users():
    """查询活跃用户"""
    metadata = MetaData()
    users = Table('users', metadata, autoload_with=engine)

    query = (
        select(users.c.id, users.c.name, users.c.email)
        .where(and_(
            users.c.active == True,
            users.c.deleted_at.is_(None)
        ))
        .order_by(users.c.created_at.desc())
        .limit(100)
    )

    with engine.connect() as conn:
        result = conn.execute(query)
        return pd.DataFrame(result.fetchall(), columns=result.keys())
```

### 参数化查询（防止 SQL 注入）
```python
# 正确：使用参数化查询
def get_user_by_id(user_id: int):
    query = text("SELECT * FROM users WHERE id = :user_id")
    with engine.connect() as conn:
        result = conn.execute(query, {"user_id": user_id})
        return result.fetchone()

# 错误：字符串拼接（不安全）
def get_user_by_id_unsafe(user_id: int):
    query = f"SELECT * FROM users WHERE id = {user_id}"  # 不安全！
    with engine.connect() as conn:
        result = conn.execute(query)
        return result.fetchone()
```

## 事务管理

### 基本事务
```python
def update_user_data(user_id: int, updates: dict):
    """更新用户数据"""
    engine = create_db_engine()

    with engine.begin() as conn:  # 自动提交或回滚
        conn.execute(
            text("UPDATE users SET name = :name WHERE id = :id"),
            {"name": updates["name"], "id": user_id}
        )
        # 如果这里抛出异常，整个事务会回滚
```

### 手动事务控制
```python
def complex_operation():
    """复杂操作需要手动控制事务"""
    engine = create_db_engine()
    conn = engine.connect()
    trans = conn.begin()

    try:
        # 执行多个操作
        conn.execute(text("UPDATE accounts SET balance = balance - 100 WHERE id = 1"))
        conn.execute(text("UPDATE accounts SET balance = balance + 100 WHERE id = 2"))

        trans.commit()  # 提交事务
    except Exception as e:
        trans.rollback()  # 回滚事务
        raise
    finally:
        conn.close()
```

## 性能优化

### 批量插入
```python
def batch_insert(data: list[dict]):
    """批量插入数据"""
    engine = create_db_engine()

    with engine.connect() as conn:
        # 使用 executemany 提高性能
        conn.execute(
            text("INSERT INTO users (name, email) VALUES (:name, :email)"),
            data
        )
```

### 查询优化
```python
# 只选择需要的字段
def get_user_summary():
    query = text("SELECT id, name, email FROM users WHERE active = true")

    # 而不是 SELECT * FROM users

# 使用 LIMIT 限制结果集
def get_recent_users(limit: int = 100):
    query = text("SELECT * FROM users ORDER BY created_at DESC LIMIT :limit")

# 使用 EXPLAIN 分析慢查询
def analyze_query_performance():
    query = text("EXPLAIN SELECT * FROM large_table WHERE created_at > '2024-01-01'")
    with engine.connect() as conn:
        result = conn.execute(query)
        return result.fetchall()
```

### 使用索引
```python
# 确保查询字段有适当的索引
def create_indexes():
    """创建必要的索引"""
    engine = create_db_engine()

    with engine.connect() as conn:
        # 单列索引
        conn.execute(text("CREATE INDEX idx_users_email ON users(email)"))

        # 复合索引
        conn.execute(text("CREATE INDEX idx_users_active_created ON users(active, created_at)"))

        # 部分索引（仅索引活跃用户）
        conn.execute(text("CREATE INDEX idx_active_users ON users(created_at) WHERE active = true"))
```

## 连接池配置

### 生产环境配置
```python
def create_production_engine():
    """生产环境的数据库引擎配置"""
    return create_engine(
        get_db_url(),
        pool_size=10,          # 连接池大小
        max_overflow=20,        # 最大溢出连接数
        pool_timeout=30,        # 获取连接超时时间（秒）
        pool_recycle=3600,      # 连接回收时间（秒）
        pool_pre_ping=True,     # 连接前检查连接有效性
        echo=False             # 生产环境关闭 SQL 日志
    )
```

### 开发环境配置
```python
def create_development_engine():
    """开发环境的数据库引擎配置"""
    return create_engine(
        get_db_url(),
        pool_size=5,
        max_overflow=5,
        pool_timeout=10,
        pool_recycle=1800,
        echo=True              # 开发环境开启 SQL 日志
    )
```

## 错误处理

### 捕获和处理异常
```python
from sqlalchemy.exc import SQLAlchemyError, OperationalError

def safe_query(sql: str, params: dict = None):
    """安全执行查询"""
    try:
        engine = create_db_engine()
        with engine.connect() as conn:
            result = conn.execute(text(sql), params or {})
            return pd.DataFrame(result.fetchall(), columns=result.keys())

    except OperationalError as e:
        logger.error(f"数据库连接错误: {e}")
        raise ConnectionError("无法连接到数据库") from e

    except SQLAlchemyError as e:
        logger.error(f"SQL 执行错误: {e}")
        raise

    except Exception as e:
        logger.error(f"未知错误: {e}")
        raise
```

## 元数据管理

### 反射数据库表结构
```python
from sqlalchemy import MetaData, Table

def get_table_schema(table_name: str):
    """获取表结构"""
    metadata = MetaData()
    engine = create_db_engine()

    # 反射表结构
    table = Table(table_name, metadata, autoload_with=engine)

    schema_info = []
    for column in table.columns:
        schema_info.append({
            "name": column.name,
            "type": str(column.type),
            "nullable": column.nullable,
            "primary_key": column.primary_key
        })

    return schema_info
```

### 列出所有表
```python
from sqlalchemy import inspect

def get_all_tables():
    """获取数据库中的所有表"""
    engine = create_db_engine()
    inspector = inspect(engine)
    return inspector.get_table_names()
```

## 安全最佳实践

### 1. 永远使用参数化查询
```python
# 正确
query = text("SELECT * FROM users WHERE id = :user_id")
conn.execute(query, {"user_id": user_id})

# 错误
query = f"SELECT * FROM users WHERE id = {user_id}"
conn.execute(query)
```

### 2. 限制结果集大小
```python
def search_users(keyword: str, limit: int = 100):
    """搜索用户，限制结果数量"""
    query = text("""
        SELECT id, name, email FROM users
        WHERE name LIKE :keyword OR email LIKE :keyword
        LIMIT :limit
    """)
    return conn.execute(query, {
        "keyword": f"%{keyword}%",
        "limit": limit
    })
```

### 3. 使用只读账户执行查询
```python
def create_readonly_engine():
    """创建只读数据库连接"""
    # 在配置文件中使用只读账户
    readonly_url = get_db_url().replace(
        os.getenv('DB_USER'),
        os.getenv('DB_READONLY_USER')
    )
    return create_engine(readonly_url)
```

### 4. 验证用户输入的 SQL
```python
def validate_sql_safety(sql: str) -> bool:
    """验证 SQL 是否安全（仅允许 SELECT）"""
    sql_upper = sql.strip().upper()
    dangerous_keywords = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE', 'TRUNCATE']

    for keyword in dangerous_keywords:
        if keyword in sql_upper:
            raise ValueError(f"不允许的 SQL 关键字: {keyword}")

    return True

def execute_safe_query(sql: str, params: dict = None):
    """安全执行查询"""
    validate_sql_safety(sql)
    return execute_query(sql, params)
```

## 调试和监控

### 开启 SQL 日志
```python
import logging

# 配置 SQLAlchemy 日志
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
logging.getLogger('sqlalchemy.pool').setLevel(logging.DEBUG)
```

### 性能监控
```python
from time import time

def monitor_query_performance():
    """监控查询性能"""
    engine = create_db_engine()

    start_time = time()
    with engine.connect() as conn:
        result = conn.execute(text("SELECT * FROM large_table"))
        data = result.fetchall()

    duration = time() - start_time
    logger.info(f"查询耗时: {duration:.2f}秒，返回 {len(data)} 行")

    return data
```

## 常见模式

### 分页查询
```python
def get_paginated_data(page: int, page_size: int = 20):
    """分页查询"""
    offset = (page - 1) * page_size

    query = text("""
        SELECT * FROM data_table
        ORDER BY created_at DESC
        LIMIT :limit OFFSET :offset
    """)

    with engine.connect() as conn:
        result = conn.execute(query, {
            "limit": page_size,
            "offset": offset
        })
        return pd.DataFrame(result.fetchall(), columns=result.keys())
```

### 聚合查询
```python
def get_statistics():
    """获取统计信息"""
    query = text("""
        SELECT
            COUNT(*) as total_records,
            AVG(value) as average_value,
            MAX(value) as max_value,
            MIN(value) as min_value
        FROM data_table
        WHERE created_at >= :start_date
    """)

    with engine.connect() as conn:
        result = conn.execute(query, {"start_date": datetime.now() - timedelta(days=30)})
        return result.fetchone()
```

## MySQL 特定优化

### MySQL 索引优化
```python
def create_mysql_indexes():
    """MySQL 索引优化"""
    engine = create_db_engine()

    with engine.connect() as conn:
        # 复合索引
        conn.execute(text("CREATE INDEX idx_orders_user_created ON orders(user_id, created_at DESC)"))

        # FULLTEXT 索引（文本搜索）
        conn.execute(text("CREATE FULLTEXT INDEX idx_products_search ON products(name, description)"))

        # 前缀索引（大文本字段）
        conn.execute(text("CREATE INDEX idx_large_text ON large_table(text_column(100))"))
```

### MySQL 查询分析
```python
def analyze_mysql_query():
    """使用 EXPLAIN 分析 MySQL 查询"""
    query = text("EXPLAIN FORMAT=JSON SELECT * FROM users WHERE email = :email")
    with engine.connect() as conn:
        result = conn.execute(query, {"email": "test@example.com"})
        return result.fetchone()
```

### MySQL 批量更新
```python
def batch_update_updates(updates: list[dict]):
    """MySQL 批量更新"""
    engine = create_db_engine()

    with engine.connect() as conn:
        # 使用 VALUES 子句批量更新
        query = text("""
            UPDATE products p
            JOIN (
                SELECT :id as id, :price as price
            ) AS updates ON p.id = updates.id
            SET p.price = updates.price
        """)
        for update in updates:
            conn.execute(query, update)
```

## 禁止事项

- 禁止使用字符串拼接构建 SQL 查询
- 禁止在生产环境中启用 `echo=True`（SQL 日志）
- 禁止不关闭数据库连接或引擎
- 禁止在循环中执行单独的 SQL 语句（使用批量操作）
- 禁止不验证用户输入就执行 SQL
- 禁止使用 `SELECT *` 而不指定具体字段
- 禁止在没有索引的列上进行 JOIN 或 WHERE 操作
