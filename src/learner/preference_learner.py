import json
import os
from typing import Dict, List, Optional, Tuple


class PreferenceLearner:
    """
    用户偏好学习器
    学习用户对特定实体类型对应表关系的偏好
    """
    
    def __init__(self, storage_path: str = "preferences.json"):
        """
        初始化偏好学习器
        
        Args:
            storage_path: 偏好数据的存储路径
        """
        self.storage_path = storage_path
        self.preferences = self._load_preferences()
    
    def _load_preferences(self) -> Dict:
        """
        从文件加载偏好数据
        如果文件不存在，则返回默认结构
        """
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                # 如果文件损坏或无法读取，返回默认结构
                return self._get_default_preferences()
        else:
            return self._get_default_preferences()
    
    def _get_default_preferences(self) -> Dict:
        """
        获取默认的偏好数据结构
        """
        return {
            "semantic_mappings": {},
            "table_combinations": {},
            "field_mappings": {}
        }
    
    def _save_preferences(self):
        """
        将偏好数据保存到文件
        """
        try:
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(self.preferences, f, ensure_ascii=False, indent=2)
        except IOError as e:
            print(f"无法保存偏好数据到文件 {self.storage_path}: {e}")
    
    def _make_combo_key(self, tables: List[str]) -> str:
        """
        生成表组合键，将表名按字母顺序排序后连接
        
        Args:
            tables: 表名列表
            
        Returns:
            排序后的表名组合键
        """
        return "_".join(sorted(tables))
    
    def _calculate_match(self, entities: List[str], tables: List[str]) -> float:
        """
        计算实体和表之间的匹配度
        简单地计算实体中包含表名的比例
        
        Args:
            entities: 实体列表
            tables: 表名列表
            
        Returns:
            匹配度分数 (0-1)
        """
        match_count = 0
        total_entities = len(entities)
        
        if total_entities == 0:
            return 0.0
        
        for entity in entities:
            for table in tables:
                if table.lower() in entity.lower():
                    match_count += 1
                    break  # 每个entity只计算一次匹配
        
        return match_count / total_entities
    
    def learn(self, entities: List[str], selected_tables: List[str], user_query: str = ""):
        """
        学习用户偏好
        
        Args:
            entities: 实体列表
            selected_tables: 选择的表列表
            user_query: 用户查询语句
        """
        for entity in entities:
            # 创建或更新实体映射
            if entity not in self.preferences["semantic_mappings"]:
                self.preferences["semantic_mappings"][entity] = {
                    "table": selected_tables[0] if selected_tables else "",  # 取第一个表作为主要映射
                    "confidence": 0.5,  # 初始置信度
                    "used_count": 0,
                    "all_tables": selected_tables  # 保存完整表列表
                }
            
            # 更新映射信息
            mapping = self.preferences["semantic_mappings"][entity]
            if mapping["table"] in selected_tables:
                # 如果当前映射的表被再次选中，提高置信度
                mapping["used_count"] += 1
                # 使用递减增量来增加置信度，避免无限增长
                confidence_increment = 0.1 * (1.0 - mapping["confidence"])  # 最大置信度为1.0
                mapping["confidence"] = min(1.0, mapping["confidence"] + confidence_increment)
            else:
                # 如果选择了不同的表，更新映射
                mapping["table"] = selected_tables[0] if selected_tables else ""
                mapping["all_tables"] = selected_tables
                mapping["used_count"] += 1
                # 设置基础置信度
                mapping["confidence"] = 0.5 + 0.1 * min(mapping["used_count"], 5)  # 根据使用次数设置基础置信度
            
            # 保持置信度在合理范围内
            mapping["confidence"] = max(0.1, min(1.0, mapping["confidence"]))
        
        # 保存更改
        self._save_preferences()
    
    def lookup(self, entities: List[str]) -> Optional[Dict]:
        """
        查找已学习的实体映射
        
        Args:
            entities: 实体列表
            
        Returns:
            匹配的映射信息，如果未找到则返回None
        """
        if not entities:
            return None
        
        # 对每个实体进行查找
        for entity in entities:
            if entity in self.preferences["semantic_mappings"]:
                mapping = self.preferences["semantic_mappings"][entity]
                
                # 返回映射信息
                return {
                    "tables": mapping.get("all_tables") or (
                        [mapping["table"]] if mapping["table"] else []
                    ),
                    "confidence": mapping["confidence"],
                    "used_count": mapping["used_count"]
                }
        
        # 如果没有找到任何映射，返回None
        return None
