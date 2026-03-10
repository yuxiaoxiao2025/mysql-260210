"""
SQL 安全校验测试

测试模块：src.sql_safety
- detect_intent: 检测SQL语句的意图类型
- validate_sql: 验证SQL语句安全性
"""

import pytest
from src.sql_safety import detect_intent, validate_direct_query_sql, validate_sql


def test_detect_intent_update():
    """测试检测UPDATE语句的意图"""
    assert detect_intent("UPDATE t SET a=1 WHERE id=1") == "update"


def test_validate_rejects_drop():
    """测试拒绝DROP TABLE等危险操作"""
    ok, reason = validate_sql("DROP TABLE t")
    assert ok is False
    assert "drop" in reason.lower()


def test_detect_intent_insert():
    """测试检测INSERT语句的意图"""
    assert detect_intent("INSERT INTO users VALUES (1, 'test')") == "insert"


def test_detect_intent_delete():
    """测试检测DELETE语句的意图"""
    assert detect_intent("DELETE FROM users WHERE id=1") == "delete"


def test_detect_intent_select():
    """测试检测SELECT语句的意图"""
    assert detect_intent("SELECT * FROM users") == "select"


def test_detect_intent_unknown():
    """测试未知SQL语句类型"""
    assert detect_intent("SHOW TABLES") == "unknown"


def test_detect_intent_empty():
    """测试空字符串"""
    assert detect_intent("") == "unknown"


def test_detect_intent_whitespace():
    """测试仅包含空白字符的字符串"""
    assert detect_intent("   \n\t  ") == "unknown"


def test_validate_rejects_alter():
    """测试拒绝ALTER TABLE等危险操作"""
    ok, reason = validate_sql("ALTER TABLE users ADD COLUMN age INT")
    assert ok is False
    assert "alter" in reason.lower()


def test_validate_rejects_truncate():
    """测试拒绝TRUNCATE TABLE等危险操作"""
    ok, reason = validate_sql("TRUNCATE TABLE users")
    assert ok is False
    assert "truncate" in reason.lower()


def test_validate_accepts_update():
    """测试接受安全的UPDATE语句"""
    ok, reason = validate_sql("UPDATE users SET name='test' WHERE id=1")
    assert ok is True
    assert reason == "ok"


def test_validate_accepts_insert():
    """测试接受安全的INSERT语句"""
    ok, reason = validate_sql("INSERT INTO users (name) VALUES ('test')")
    assert ok is True
    assert reason == "ok"


def test_validate_accepts_delete():
    """测试接受安全的DELETE语句"""
    ok, reason = validate_sql("DELETE FROM users WHERE id=1")
    assert ok is True
    assert reason == "ok"


def test_validate_case_insensitive():
    """测试关键字检测不区分大小写"""
    ok, _ = validate_sql("Drop Table users")
    assert ok is False

    ok, _ = validate_sql("DROP table users")
    assert ok is False


def test_validate_word_boundary():
    """测试单词边界匹配（避免误匹配）"""
    # 包含'drop'作为子串的合法语句应该通过
    # 例如包含'dropship'这样的字段名（实际场景中可能存在）
    ok, _ = validate_sql("SELECT dropship_status FROM orders")
    # 这个测试可能会失败，取决于实现细节
    # 如果使用正则表达式\b边界，应该通过
    assert ok is True


def test_validate_direct_query_allows_select():
    """测试直接查询模式允许 SELECT"""
    ok, reason = validate_direct_query_sql("SELECT * FROM users WHERE id = 1")
    assert ok is True
    assert reason == "ok"


def test_validate_direct_query_rejects_update():
    """测试直接查询模式拒绝 UPDATE"""
    ok, reason = validate_direct_query_sql("UPDATE users SET name='a' WHERE id=1")
    assert ok is False
    assert "仅允许 select" in reason.lower()


def test_validate_direct_query_rejects_multi_statement():
    """测试直接查询模式拒绝多语句"""
    ok, reason = validate_direct_query_sql("SELECT 1; SELECT 2")
    assert ok is False
    assert "多语句" in reason


def test_validate_allows_dangerous_keyword_in_string_literal():
    ok, reason = validate_sql("SELECT 'drop table users' AS msg")
    assert ok is True
    assert reason == "ok"


def test_validate_allows_dangerous_keyword_in_comment():
    ok, reason = validate_sql("SELECT 1 -- drop table users")
    assert ok is True
    assert reason == "ok"


def test_detect_intent_with_cte_select():
    assert detect_intent("WITH t AS (SELECT 1) SELECT * FROM t") == "select"


def test_validate_direct_query_rejects_into_outfile():
    ok, reason = validate_direct_query_sql("SELECT * INTO OUTFILE '/tmp/a.csv' FROM users")
    assert ok is False
    assert "outfile" in reason.lower()


def test_validate_direct_query_rejects_sleep_function():
    ok, reason = validate_direct_query_sql("SELECT SLEEP(5)")
    assert ok is False
    assert "危险函数" in reason
