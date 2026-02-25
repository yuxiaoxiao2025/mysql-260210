from typing import Dict, List, Any

class SmartQueryEngine:
    """智能查询引擎 - 结合缓存、匹配和学习"""
    
    def __init__(self, schema_cache, preference_learner, table_matcher):
        self.cache = schema_cache
        self.learner = preference_learner
        self.matcher = table_matcher
    
    def _extract_entities(self, user_query: str) -> List[str]:
        return self.matcher._extract_entities(user_query)
    
    def _find_alternatives(self, entities: List[str]) -> List[Dict]:
        candidates = self.matcher.match_tables(" ".join(entities))
        # 转换为建议列表格式
        alternatives = []
        matched = candidates.get("groups", {}).get("matched_tables", [])
        for table_info in matched:
            alternatives.append({
                "table": table_info.get("table_name"),
                "recommended": table_info.get("recommended", False)
            })
        return alternatives
    
    def process_query(self, user_query: str) -> Dict[str, Any]:
        # 1. 提取实体
        entities = self._extract_entities(user_query)
        
        # 2. 查找记忆
        learned = self.learner.lookup(entities)
        
        if learned and learned.get("confidence", 0) >= 0.85:
            # 高置信度，自动应用
            return {
                "needs_interaction": False,
                "selected_tables": learned["tables"],
                "reason": f"🎯 已记忆，置信度: {learned['confidence']:.0%}",
                "suggestions": []
            }
        elif learned:
            # 低置信度，需要确认
            return {
                "needs_interaction": True,
                "selected_tables": learned["tables"],
                "reason": f"💭 记得您之前用过，继续使用？",
                "suggestions": self._find_alternatives(entities)
            }
        
        # 3. 无记忆，需要交互
        return {
            "needs_interaction": True,
            "selected_tables": [],
            "reason": "🔍 发现了多个可能的表，请选择",
            "suggestions": self._find_alternatives(entities)
        }
    
    def record_user_choice(self, entities: List[str], selected_tables: List[str], user_query: str):
        self.learner.learn(entities, selected_tables, user_query)