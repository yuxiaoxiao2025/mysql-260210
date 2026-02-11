"""
预览渲染模块

提供 CLI 和 HTML 预览之间的切换逻辑。
根据数据行数决定使用哪种渲染方式。
"""
import pandas as pd


def should_render_html(before_df: pd.DataFrame, after_df: pd.DataFrame, max_rows: int) -> bool:
    """
    判断是否应该使用 HTML 渲染而非 CLI 渲染。

    当 before_df 或 after_df 中的任一个 DataFrame 的行数超过 max_rows 时，
    返回 True 表示应使用 HTML 预览。

    Args:
        before_df: 执行前的数据
        after_df: 执行后的数据
        max_rows: CLI 渲染的最大行数阈值

    Returns:
        bool: 如果应使用 HTML 渲染则返回 True，否则返回 False
    """
    return max(len(before_df), len(after_df)) > max_rows
