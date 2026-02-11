"""
SQL 安全校验模块

提供SQL语句的意图检测和安全验证功能，用于防止危险操作。
遵循SOLID原则：
- 单一职责：专注于SQL安全校验
- 开闭原则：可通过扩展关键字列表增强检查
"""

import re
from typing import Tuple


# 支持的DML操作类型
DML_INTENTS = {"insert", "update", "delete", "select"}

# 禁止的危险关键字
DANGEROUS_KEYWORDS = ("drop", "alter", "truncate")


def detect_intent(sql: str) -> str:
    """
    检测SQL语句的意图类型

    Args:
        sql: SQL语句字符串

    Returns:
        意图类型: "insert", "update", "delete", "select" 或 "unknown"

    Examples:
        >>> detect_intent("UPDATE users SET name='test' WHERE id=1")
        'update'
        >>> detect_intent("SELECT * FROM users")
        'select'
        >>> detect_intent("SHOW TABLES")
        'unknown'
    """
    if not sql or not sql.strip():
        return "unknown"

    # 提取第一个单词作为SQL命令
    first_word = sql.strip().split()[0].lower()

    # 检查是否为已知DML操作
    if first_word in DML_INTENTS:
        return first_word

    return "unknown"


def validate_sql(sql: str) -> Tuple[bool, str]:
    """
    验证SQL语句的安全性

    检查是否包含危险关键字（DROP/ALTER/TRUNCATE等），
    这些操作可能对数据造成不可逆的破坏。

    Args:
        sql: 待验证的SQL语句

    Returns:
        (is_valid, reason): 验证结果和原因说明
        - is_valid=True, reason="ok": 安全
        - is_valid=False, reason="Disallowed keyword: xxx": 不安全

    Examples:
        >>> validate_sql("UPDATE users SET name='test' WHERE id=1")
        (True, 'ok')
        >>> validate_sql("DROP TABLE users")
        (False, 'Disallowed keyword: drop')
    """
    if not sql or not sql.strip():
        return True, "ok"

    lowered = sql.lower()

    # 使用单词边界匹配，避免误匹配（如'dropship'等合法字段名）
    for keyword in DANGEROUS_KEYWORDS:
        pattern = rf"\b{keyword}\b"
        if re.search(pattern, lowered):
            return False, f"Disallowed keyword: {keyword}"

    return True, "ok"
