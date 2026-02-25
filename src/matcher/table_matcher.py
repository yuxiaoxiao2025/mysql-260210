import re
from typing import Dict, List, Any, Optional
from difflib import SequenceMatcher


class TableMatcher:
    """
    表匹配引擎 - 根据用户查询语句智能匹配相关数据库表
    """
    
    def __init__(self, schema_cache):
        """
        初始化TableMatcher
        
        Args:
            schema_cache: 数据库表结构缓存对象，提供表搜索和详细信息查询功能
        """
        self.schema_cache = schema_cache
        # 语义关键词映射，用于实体提取和匹配
        self.semantic_keywords = {
            "车辆": ["车", "车辆", "机动车", "汽车", "货车", "客车"],
            "园区": ["园区", "区域", "场地", "停车场", "场区", "区域"],
            "人员": ["人", "人员", "员工", "客户", "访客", "司机"], 
            "设备": ["设备", "机器", "装置", "硬件", "终端", "摄像头"],
            "订单": ["订单", "交易", "单据", "业务", "流水", "记录"],
            "固定车": ["固定车", "常用车", "备案车", "注册车", "白名单车"],
            "临时车": ["临时车", "临停车", "过路车", "临时进出场车"],
            "通行": ["通行", "进出", "门禁", "闸口", "通道", "卡口"],
            "统计": ["统计", "分析", "报表", "汇总", "数据", "趋势"],
            "日志": ["日志", "记录", "历史", "轨迹", "事件", "操作"]
        }

    def _extract_entities(self, query: str) -> List[str]:
        """
        从查询语句中提取语义实体
        
        Args:
            query: 用户查询语句
            
        Returns:
            List[str]: 提取的语义实体列表
        """
        entities = []
        
        # 遍历语义关键词映射
        for semantic_term, keywords in self.semantic_keywords.items():
            for keyword in keywords:
                if keyword in query:
                    entities.append(semantic_term)
                    break  # 避免重复添加同一类别
        
        # 去重并返回
        return list(set(entities))

    def _calculate_similarity(self, query: str, entity: str, table_info: Dict[str, Any]) -> float:
        """
        计算查询与表的相似度
        
        Args:
            query: 原始查询语句
            entity: 提取的实体
            table_info: 表信息字典
            
        Returns:
            float: 相似度分数 (0~1)
        """
        score = 0.0
        
        # 查询与表名匹配度
        table_name_sim = SequenceMatcher(None, query, table_info['table_name']).ratio()
        if table_name_sim > 0.3:  # 设置阈值
            score += table_name_sim * 0.3  # 加权
        
        # 查询与表描述匹配度
        description_sim = 0.0
        if table_info.get('description'):
            description_sim = SequenceMatcher(None, query, table_info['description']).ratio()
            if description_sim > 0.3:
                score += description_sim * 0.4  # 加权
        
        # 实体与表名/描述匹配度
        entity_name_sim = SequenceMatcher(None, entity, table_info['table_name']).ratio()
        if entity_name_sim > 0.3:
            score += entity_name_sim * 0.2
        
        entity_desc_sim = 0.0
        if table_info.get('description'):
            entity_desc_sim = SequenceMatcher(None, entity, table_info['description']).ratio()
            if entity_desc_sim > 0.3:
                score += entity_desc_sim * 0.1
        
        return min(score, 1.0)  # 限制分数不超过1.0

    def match_tables(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        """
        匹配查询相关的表
        
        Args:
            query: 用户查询语句
            top_k: 返回前k个结果
            
        Returns:
            Dict[str, Any]: 包含匹配的表组和总数的字典
        """
        # 提取查询中的实体
        entities = self._extract_entities(query)
        
        # 如果没有提取到实体，尝试直接使用原始查询
        if not entities:
            entities = [query]
        
        all_candidates = []
        
        # 针对每个实体搜索相关表
        for entity in entities:
            # 搜索相关表 - 这里调用缓存接口
            candidates = self.schema_cache.search_tables(entity)
            
            # 为每个候选表计算相似度
            for candidate in candidates:
                similarity = self._calculate_similarity(query, entity, candidate)
                
                # 只保留相似度大于0的表
                if similarity > 0:
                    candidate_with_score = candidate.copy()
                    candidate_with_score['similarity'] = similarity
                    all_candidates.append(candidate_with_score)
        
        # 按相似度降序排列
        all_candidates.sort(key=lambda x: x.get('similarity', 0), reverse=True)
        
        # 取前top_k个结果
        matched_tables = all_candidates[:top_k]
        
        # 分组成字典
        groups = {
            "matched_tables": matched_tables,
            "entities": entities
        }
        
        return {
            "groups": groups,
            "total_count": len(matched_tables)
        }

    def smart_recommend(self, user_query: str, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        智能推荐表
        
        Args:
            user_query: 用户查询语句
            candidates: 候选表列表
            
        Returns:
            List[Dict[str, Any]]: 包含推荐标记的结果列表
        """
        recommended_results = []
        
        for candidate in candidates:
            candidate_copy = candidate.copy()
            
            # 判断是否推荐该表
            recommended = False
            table_name_lower = candidate['table_name'].lower()
            description_lower = (candidate.get('description', '') or '').lower()
            query_lower = user_query.lower()
            
            # 基于关键词的推荐逻辑
            if '固定车' in user_query and ('white' in table_name_lower or 'fixed' in table_name_lower or 'white' in description_lower or 'fixed' in description_lower or '固定' in table_name_lower or '固定' in description_lower):
                recommended = True
            elif '临时车' in user_query and ('temp' in table_name_lower or 'temporary' in table_name_lower or 'temp' in description_lower or 'temporary' in description_lower or '临时' in table_name_lower or '临时' in description_lower):
                recommended = True
            elif query_lower in table_name_lower or query_lower in description_lower:
                recommended = True
            elif any(keyword in table_name_lower or keyword in description_lower for keyword in user_query.split()):
                recommended = True
            
            candidate_copy['recommended'] = recommended
            recommended_results.append(candidate_copy)
        
        return recommended_results

    def get_table_detail(self, table_name: str) -> Dict[str, Any]:
        """
        获取表详细信息
        
        Args:
            table_name: 表名
            
        Returns:
            Dict[str, Any]: 表详细信息
        """
        return self.schema_cache.get_table_info(table_name)