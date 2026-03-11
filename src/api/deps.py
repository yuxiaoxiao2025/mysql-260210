"""
依赖注入模块 - 统一管理所有组件的实例化
"""
import os
from functools import lru_cache
from src.db_manager import DatabaseManager
from src.llm_client import LLMClient
from src.cache.schema_cache import SchemaCache
from src.matcher.table_matcher import TableMatcher
from src.learner.preference_learner import PreferenceLearner
from src.matcher.smart_query_engine import SmartQueryEngine


def get_llm_config() -> dict:
    """获取 LLM 配置（从环境变量读取）"""
    def _parse_bool(key: str, default: bool = False) -> bool:
        value = os.getenv(key, "").lower()
        if value in ("1", "true", "yes", "on"):
            return True
        if value in ("0", "false", "no", "off"):
            return False
        return default

    return {
        "enable_structured_output": _parse_bool("ENABLE_STRUCTURED_OUTPUT", False),
        "enable_thinking": _parse_bool("ENABLE_THINKING", False),
        "enable_stream": _parse_bool("ENABLE_STREAM", False),
        "enable_prompt_cache": _parse_bool("ENABLE_PROMPT_CACHE", False),
        "model": os.getenv("LLM_MODEL", "qwen-plus"),
    }


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
