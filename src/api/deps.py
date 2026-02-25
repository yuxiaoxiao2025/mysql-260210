"""
依赖注入模块 - 统一管理所有组件的实例化
"""
from functools import lru_cache
from src.db_manager import DatabaseManager
from src.llm_client import LLMClient
from src.cache.schema_cache import SchemaCache
from src.matcher.table_matcher import TableMatcher
from src.learner.preference_learner import PreferenceLearner
from src.matcher.smart_query_engine import SmartQueryEngine


@lru_cache()
def get_db() -> DatabaseManager:
    """获取数据库管理器单例"""
    return DatabaseManager()


@lru_cache()
def get_llm() -> LLMClient:
    """获取 LLM 客户端单例"""
    return LLMClient()


@lru_cache()
def get_cache() -> SchemaCache:
    """获取 Schema 缓存单例"""
    return SchemaCache(db_manager=get_db())


@lru_cache()
def get_matcher() -> TableMatcher:
    """获取表匹配器单例"""
    return TableMatcher(schema_cache=get_cache())


@lru_cache()
def get_learner() -> PreferenceLearner:
    """获取偏好学习器单例"""
    return PreferenceLearner()


@lru_cache()
def get_query_engine() -> SmartQueryEngine:
    """获取智能查询引擎单例"""
    return SmartQueryEngine(
        schema_cache=get_cache(),
        preference_learner=get_learner(),
        table_matcher=get_matcher()
    )
