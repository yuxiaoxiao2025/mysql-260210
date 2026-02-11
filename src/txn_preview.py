"""
事务预览引擎模块

提供 Before/After 数据框的差异摘要功能，用于在事务内
执行 SQL 变更后，展示变更前后的数据差异。

核心功能：
- summarize_diff(): 对比两个 DataFrame，计算插入/更新/删除的行数
"""

import pandas as pd
from typing import Dict, List


def summarize_diff(
    before_df: pd.DataFrame,
    after_df: pd.DataFrame,
    key_columns: List[str]
) -> Dict[str, int]:
    """
    对比 Before 和 After 数据框，计算差异摘要。

    根据 key_columns 对齐行，判断：
    - Inserted: After 中存在但 Before 中不存在的行
    - Deleted: Before 中存在但 After 中不存在的行
    - Updated: 两边都存在但值有变化的行

    Args:
        before_df: 变更前的数据框
        after_df: 变更后的数据框
        key_columns: 用于对齐行的主键列列表

    Returns:
        包含 inserted、updated、deleted 计数的字典
    """
    # 处理空数据框的情况（早返回）
    if before_df.empty:
        return {"inserted": len(after_df), "updated": 0, "deleted": 0}
    if after_df.empty:
        return {"inserted": 0, "updated": 0, "deleted": len(before_df)}

    # 使用 pandas merge 高效计算差异
    # indicator=True 会添加 _merge 列: 'left_only', 'right_only', 'both'
    merged = before_df.merge(
        after_df,
        on=key_columns,
        how='outer',
        indicator=True
    )

    # 计算 inserted（只在 after 中）和 deleted（只在 before 中）
    inserted = (merged['_merge'] == 'right_only').sum()
    deleted = (merged['_merge'] == 'left_only').sum()

    # 计算 updated：两边都存在但值有变化的行
    # 需要比较非主键列的值
    common_rows = merged[merged['_merge'] == 'both'].copy()
    updated = 0

    if not common_rows.empty:
        # 获取非主键列
        value_columns = [col for col in before_df.columns if col not in key_columns]

        # 为 before 和 after 的值列添加后缀以便比较
        before_suffix = '_before'
        after_suffix = '_after'

        # 重新进行 merge，这次使用 suffixes 区分 before/after 的值列
        merged_with_values = before_df.merge(
            after_df,
            on=key_columns,
            how='inner',
            suffixes=(before_suffix, after_suffix)
        )

        # 检查每一行是否有任何值列发生了变化
        for _, row in merged_with_values.iterrows():
            for col in value_columns:
                before_val = row[f'{col}{before_suffix}']
                after_val = row[f'{col}{after_suffix}']
                # 使用 pd.isna 处理 NaN 值的比较
                if before_val != after_val and not (pd.isna(before_val) and pd.isna(after_val)):
                    updated += 1
                    break

    return {"inserted": inserted, "updated": updated, "deleted": deleted}
