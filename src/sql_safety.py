"""
SQL 安全校验模块

提供SQL语句的意图检测和安全验证功能，用于防止危险操作。
遵循SOLID原则：
- 单一职责：专注于SQL安全校验
- 开闭原则：可通过扩展关键字列表增强检查
"""

import re
from typing import Tuple
import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError


# 支持的DML操作类型
DML_INTENTS = {"insert", "update", "delete", "select"}

# 禁止的危险关键字
DANGEROUS_KEYWORDS = ("drop", "alter", "truncate")
SQL_STRING_PATTERN = r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|`(?:``|[^`])*`"
SQL_LINE_COMMENT_PATTERN = r"--[^\r\n]*"
SQL_BLOCK_COMMENT_PATTERN = r"/\*[\s\S]*?\*/"
RISKY_SELECT_PATTERNS = (
    (r"\binto\s+outfile\b", "SELECT 查询禁止使用 INTO OUTFILE"),
    (r"\binto\s+dumpfile\b", "SELECT 查询禁止使用 INTO DUMPFILE"),
    (r"\bsleep\s*\(", "SELECT 查询禁止使用危险函数 SLEEP"),
    (r"\bbenchmark\s*\(", "SELECT 查询禁止使用危险函数 BENCHMARK"),
)


def _strip_sql_literals_and_comments(sql: str) -> str:
    without_block_comments = re.sub(SQL_BLOCK_COMMENT_PATTERN, " ", sql)
    without_line_comments = re.sub(SQL_LINE_COMMENT_PATTERN, " ", without_block_comments)
    return re.sub(SQL_STRING_PATTERN, "''", without_line_comments)


def has_multiple_statements(sql: str) -> bool:
    normalized = _strip_sql_literals_and_comments(sql).strip()
    if normalized.endswith(";"):
        normalized = normalized[:-1].strip()
    return ";" in normalized


def has_where_clause(sql: str) -> bool:
    try:
        parsed = sqlglot.parse_one(sql, dialect="mysql")
    except SqlglotError:
        normalized = _strip_sql_literals_and_comments(sql)
        return re.search(r"\bwhere\b", normalized, flags=re.IGNORECASE) is not None

    if isinstance(parsed, exp.Update):
        return parsed.args.get("where") is not None
    if isinstance(parsed, exp.Delete):
        return parsed.args.get("where") is not None

    normalized = _strip_sql_literals_and_comments(sql)
    return re.search(r"\bwhere\b", normalized, flags=re.IGNORECASE) is not None


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

    try:
        parsed = sqlglot.parse_one(sql, dialect="mysql")
        if isinstance(parsed, exp.Select):
            return "select"
        if isinstance(parsed, exp.Insert):
            return "insert"
        if isinstance(parsed, exp.Update):
            return "update"
        if isinstance(parsed, exp.Delete):
            return "delete"
    except SqlglotError:
        pass

    first_word = sql.strip().split()[0].lower()
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

    lowered = _strip_sql_literals_and_comments(sql).lower()

    # 使用单词边界匹配，避免误匹配（如'dropship'等合法字段名）
    for keyword in DANGEROUS_KEYWORDS:
        pattern = rf"\b{keyword}\b"
        if re.search(pattern, lowered):
            return False, f"Disallowed keyword: {keyword}"

    return True, "ok"


def validate_direct_query_sql(sql: str) -> Tuple[bool, str]:
    """
    验证直接 SQL 模式下的语句安全性。

    直接 SQL 模式仅允许单条 SELECT 查询，禁止 DML 和多语句执行。
    """
    is_valid, reason = validate_sql(sql)
    if not is_valid:
        return False, reason

    intent = detect_intent(sql)
    if intent != "select":
        return False, "直接 SQL 模式仅允许 SELECT 查询"

    if has_multiple_statements(sql):
        return False, "直接 SQL 模式不允许多语句"

    normalized = _strip_sql_literals_and_comments(sql).lower()
    for pattern, reason in RISKY_SELECT_PATTERNS:
        if re.search(pattern, normalized):
            return False, reason

    return True, "ok"
