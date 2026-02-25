"""
Diff渲染器模块
提供变更对比渲染功能，用于在事务执行前预览数据变更效果。
"""

import pandas as pd
from typing import Dict, List


class DiffRenderer:
    """
    Diff渲染器类，负责处理数据变更的前后对比渲染
    """
    
    def render_diff(self, before_df: pd.DataFrame, after_df: pd.DataFrame, 
                    operation_type: str, key_columns: List[str]) -> Dict:
        """
        主入口方法：渲染数据差异
        
        Args:
            before_df: 变更前的数据框
            after_df: 变更后的数据框
            operation_type: 操作类型 ('insert', 'update', 'delete')
            key_columns: 主键列列表
            
        Returns:
            包含操作信息和变更详情的字典
        """
        changes = []
        
        if operation_type == "update":
            changes = self.render_update_diff(before_df, after_df, key_columns)
            summary = {"updated": len(changes)}
        elif operation_type == "delete":
            changes = self.render_delete_preview(before_df)
            summary = {"deleted": len(changes)}
        elif operation_type == "insert":
            changes = [self.render_insert_preview(after_df.iloc[0].to_dict())] if not after_df.empty else []
            summary = {"inserted": len(changes)}
        else:
            summary = {"unknown": 0}
            
        return {
            "operation_type": operation_type,
            "summary": summary,
            "changes": changes
        }
    
    def render_update_diff(self, before_df: pd.DataFrame, after_df: pd.DataFrame, 
                          key_columns: List[str]) -> List[Dict]:
        """
        渲染UPDATE操作的对比差异
        
        Args:
            before_df: 变更前的数据框
            after_df: 变更后的数据框
            key_columns: 主键列列表
            
        Returns:
            包含变更详情的列表
        """
        changes = []
        
        # 如果任一DataFrame为空，直接返回空列表
        if before_df.empty or after_df.empty:
            return []
        
        # 使用merge找出相同主键的记录
        merged = before_df.merge(after_df, on=key_columns, how='inner', suffixes=('_before', '_after'))
        
        # 遍历合并后的结果，找出实际发生变更的记录
        for _, row in merged.iterrows():
            changed_fields = {}
            
            # 遍历所有非主键列，检查是否有变化
            for col in before_df.columns:
                if col not in key_columns:
                    before_val = row[f'{col}_before']
                    after_val = row[f'{col}_after']
                    
                    # 检查值是否发生变化（注意处理NaN值）
                    if before_val != after_val and not (pd.isna(before_val) and pd.isna(after_val)):
                        changed_fields[col] = {
                            "before": before_val,
                            "after": after_val
                        }
            
            # 如果有字段发生了变化，则添加到变更列表中
            if changed_fields:
                # 构建before和after的数据字典
                before_data = {}
                after_data = {}
                
                # 添加主键列值
                for k_col in key_columns:
                    before_data[k_col] = row[k_col]
                    after_data[k_col] = row[k_col]
                
                # 添加非主键列值
                for col in before_df.columns:
                    if col not in key_columns:
                        before_data[col] = row[f'{col}_before']
                
                for col in after_df.columns:
                    if col not in key_columns:
                        after_data[col] = row[f'{col}_after']
                
                changes.append({
                    "keys": {k: row[k] for k in key_columns},
                    "changed_fields": list(changed_fields.keys()),
                    "before": before_data,
                    "after": after_data,
                    "field_details": changed_fields
                })
        
        return changes
    
    def render_delete_preview(self, before_df: pd.DataFrame) -> List[Dict]:
        """
        渲染DELETE操作的预览数据
        
        Args:
            before_df: 要删除的数据框
            
        Returns:
            删除数据的列表
        """
        if before_df.empty:
            return []
        
        # 将DataFrame转换为字典列表
        return before_df.to_dict('records')
    
    def render_insert_preview(self, values: Dict) -> Dict:
        """
        渲染INSERT操作的预览数据
        
        Args:
            values: 要插入的值字典
            
        Returns:
            插入数据的字典
        """
        return values