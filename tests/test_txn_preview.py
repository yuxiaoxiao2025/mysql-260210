"""
事务预览引擎测试模块
测试 Before/After 数据框的差异摘要功能
"""
import pandas as pd
import pytest
from src.txn_preview import summarize_diff


def test_summarize_diff_counts():
    """测试差异摘要的基本计数功能"""
    # before: id=1 (v=1), id=2 (v=2)
    # after: id=1 (v=2 - 更新), id=3 (v=3 - 新增)
    # 期望: updated=1 (id=1 的值从 1 变为 2), deleted=1 (id=2 被删除), inserted=1 (id=3 新增)
    before = pd.DataFrame([{"id": 1, "v": 1}, {"id": 2, "v": 2}])
    after = pd.DataFrame([{"id": 1, "v": 2}, {"id": 3, "v": 3}])
    summary = summarize_diff(before, after, key_columns=["id"])
    assert summary["updated"] == 1
    assert summary["deleted"] == 1
    assert summary["inserted"] == 1


def test_summarize_diff_empty_before():
    """测试 before 为空的情况（全部插入）"""
    before = pd.DataFrame()
    after = pd.DataFrame([{"id": 1, "v": 1}, {"id": 2, "v": 2}])
    summary = summarize_diff(before, after, key_columns=["id"])
    assert summary["inserted"] == 2
    assert summary["updated"] == 0
    assert summary["deleted"] == 0


def test_summarize_diff_empty_after():
    """测试 after 为空的情况（全部删除）"""
    before = pd.DataFrame([{"id": 1, "v": 1}, {"id": 2, "v": 2}])
    after = pd.DataFrame()
    summary = summarize_diff(before, after, key_columns=["id"])
    assert summary["deleted"] == 2
    assert summary["inserted"] == 0
    assert summary["updated"] == 0


def test_summarize_diff_no_changes():
    """测试无变化的情况"""
    before = pd.DataFrame([{"id": 1, "v": 1}, {"id": 2, "v": 2}])
    after = pd.DataFrame([{"id": 1, "v": 1}, {"id": 2, "v": 2}])
    summary = summarize_diff(before, after, key_columns=["id"])
    assert summary["updated"] == 0
    assert summary["deleted"] == 0
    assert summary["inserted"] == 0


def test_summarize_diff_multiple_key_columns():
    """测试多列作为主键的情况"""
    before = pd.DataFrame([
        {"id": 1, "date": "2024-01-01", "value": 10},
        {"id": 1, "date": "2024-01-02", "value": 20}
    ])
    after = pd.DataFrame([
        {"id": 1, "date": "2024-01-01", "value": 15},  # 更新
        {"id": 1, "date": "2024-01-03", "value": 30}   # 新增
    ])
    summary = summarize_diff(before, after, key_columns=["id", "date"])
    assert summary["updated"] == 1
    assert summary["deleted"] == 1
    assert summary["inserted"] == 1


def test_summarize_diff_all_updated():
    """测试所有行都被更新的情况"""
    before = pd.DataFrame([{"id": 1, "v": 1}, {"id": 2, "v": 2}])
    after = pd.DataFrame([{"id": 1, "v": 10}, {"id": 2, "v": 20}])
    summary = summarize_diff(before, after, key_columns=["id"])
    assert summary["updated"] == 2
    assert summary["deleted"] == 0
    assert summary["inserted"] == 0
