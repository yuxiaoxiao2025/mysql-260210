"""
测试预览渲染模块

遵循 TDD 原则：先写测试，再实现功能
"""
import pandas as pd
import pytest
from src.preview_renderer import should_render_html


class TestShouldRenderHtml:
    """测试 should_render_html 函数"""

    def test_should_render_html_threshold(self):
        """测试当行数超过阈值时应返回 True"""
        # 创建超过阈值的 DataFrame (31 行 > 30)
        df = pd.DataFrame([{"id": i} for i in range(31)])
        assert should_render_html(df, df, max_rows=30) is True

    def test_should_render_html_within_threshold(self):
        """测试当行数未超过阈值时应返回 False"""
        # 创建未超过阈值的 DataFrame (29 行 < 30)
        df = pd.DataFrame([{"id": i} for i in range(29)])
        assert should_render_html(df, df, max_rows=30) is False

    def test_should_render_html_at_threshold_boundary(self):
        """测试在阈值边界时应返回 False"""
        # 创建恰好等于阈值的 DataFrame (30 行 == 30)
        df = pd.DataFrame([{"id": i} for i in range(30)])
        assert should_render_html(df, df, max_rows=30) is False

    def test_should_render_html_uses_max_of_both_dfs(self):
        """测试应使用两个 DataFrame 中的最大行数进行判断"""
        # before_df 10 行，after_df 25 行，阈值 20
        before_df = pd.DataFrame([{"id": i} for i in range(10)])
        after_df = pd.DataFrame([{"id": i} for i in range(25)])
        assert should_render_html(before_df, after_df, max_rows=20) is True

    def test_should_render_html_with_empty_dataframes(self):
        """测试空 DataFrame 应返回 False"""
        empty_df = pd.DataFrame()
        assert should_render_html(empty_df, empty_df, max_rows=30) is False
