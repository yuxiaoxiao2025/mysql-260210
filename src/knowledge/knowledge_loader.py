"""
业务知识库加载器

负责加载和管理业务操作模板、枚举值和表关系映射。
支持缓存枚举值以提高性能。
"""

import os
import time
import yaml
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class OperationParam:
    """操作参数定义"""
    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None
    pattern: Optional[str] = None
    enum_from: Optional[str] = None
    example: Optional[str] = None
    min: Optional[int] = None
    max: Optional[int] = None


@dataclass
class OperationStep:
    """操作步骤定义"""
    name: str
    sql: str
    description: Optional[str] = None
    affects_rows: str = "single"  # single, multiple, unknown


@dataclass
class Operation:
    """操作模板定义"""
    id: str
    name: str
    description: str
    keywords: List[str]
    category: str  # query, mutation
    params: List[OperationParam] = field(default_factory=list)
    steps: List[OperationStep] = field(default_factory=list)
    sql: Optional[str] = None  # 查询类操作直接使用 SQL

    def is_query(self) -> bool:
        """是否为查询操作"""
        return self.category == "query"

    def is_mutation(self) -> bool:
        """是否为变更操作"""
        return self.category == "mutation"

    def get_param(self, name: str) -> Optional[OperationParam]:
        """获取指定参数"""
        for param in self.params:
            if param.name == name:
                return param
        return None

    def get_required_params(self) -> List[OperationParam]:
        """获取所有必需参数"""
        return [p for p in self.params if p.required]


@dataclass
class EnumDefinition:
    """枚举定义"""
    name: str
    description: str
    source: str
    cache_ttl: int
    value_field: str
    display_field: str


@dataclass
class RelationDefinition:
    """表关系定义"""
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    display_column: str
    description: str


class KnowledgeLoader:
    """业务知识库加载器"""

    def __init__(self, db_manager=None, config_path: Optional[str] = None):
        """
        初始化知识库加载器

        Args:
            db_manager: 数据库管理器（用于加载动态枚举）
            config_path: 配置文件路径，默认为 src/knowledge/business_knowledge.yaml
        """
        self.db_manager = db_manager

        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(__file__),
                "business_knowledge.yaml"
            )
        self.config_path = config_path

        self._config: Dict = {}
        self._operations: Dict[str, Operation] = {}
        self._enums: Dict[str, EnumDefinition] = {}
        self._relations: List[RelationDefinition] = []
        self._categories: Dict[str, Dict] = {}
        self._province_codes: Dict[str, str] = {}

        # 枚举值缓存
        self._enum_cache: Dict[str, tuple] = {}  # {name: (values, expire_time)}

        self._load_config()

    def _load_config(self) -> None:
        """加载配置文件"""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f)

            self._parse_operations()
            self._parse_enums()
            self._parse_relations()
            self._parse_categories()
            self._parse_province_codes()

            logger.info(f"知识库加载成功: {len(self._operations)} 个操作, "
                       f"{len(self._enums)} 个枚举, {len(self._relations)} 个关系")

        except FileNotFoundError:
            logger.warning(f"知识库配置文件不存在: {self.config_path}")
        except yaml.YAMLError as e:
            logger.error(f"知识库配置文件解析错误: {e}")

    def _parse_operations(self) -> None:
        """解析操作模板"""
        operations = self._config.get("operations", {})
        for op_id, op_def in operations.items():
            # 解析参数
            params = []
            for param_def in op_def.get("params", []):
                params.append(OperationParam(
                    name=param_def.get("name", ""),
                    type=param_def.get("type", "string"),
                    description=param_def.get("description", ""),
                    required=param_def.get("required", True),
                    default=param_def.get("default"),
                    pattern=param_def.get("pattern"),
                    enum_from=param_def.get("enum_from"),
                    example=param_def.get("example"),
                    min=param_def.get("min"),
                    max=param_def.get("max"),
                ))

            # 解析步骤（变更操作）
            steps = []
            for step_def in op_def.get("steps", []):
                steps.append(OperationStep(
                    name=step_def.get("name", ""),
                    sql=step_def.get("sql", ""),
                    description=step_def.get("description"),
                    affects_rows=step_def.get("affects_rows", "single"),
                ))

            self._operations[op_id] = Operation(
                id=op_id,
                name=op_def.get("name", op_id),
                description=op_def.get("description", ""),
                keywords=op_def.get("keywords", []),
                category=op_def.get("category", "query"),
                params=params,
                steps=steps,
                sql=op_def.get("sql"),
            )

    def _parse_enums(self) -> None:
        """解析枚举定义"""
        enums = self._config.get("enums", {})
        for enum_name, enum_def in enums.items():
            self._enums[enum_name] = EnumDefinition(
                name=enum_name,
                description=enum_def.get("description", ""),
                source=enum_def.get("source", ""),
                cache_ttl=enum_def.get("cache_ttl", 3600),
                value_field=enum_def.get("value_field", "value"),
                display_field=enum_def.get("display_field", "display"),
            )

    def _parse_relations(self) -> None:
        """解析表关系"""
        relations = self._config.get("relations", [])
        for rel_def in relations:
            self._relations.append(RelationDefinition(
                from_table=rel_def.get("from_table", ""),
                from_column=rel_def.get("from_column", ""),
                to_table=rel_def.get("to_table", ""),
                to_column=rel_def.get("to_column", ""),
                display_column=rel_def.get("display_column", ""),
                description=rel_def.get("description", ""),
            ))

    def _parse_categories(self) -> None:
        """解析操作类别"""
        self._categories = self._config.get("categories", {})

    def _parse_province_codes(self) -> None:
        """解析省份代码"""
        self._province_codes = self._config.get("province_codes", {})

    # ==================== 操作相关方法 ====================

    def get_operation(self, operation_id: str) -> Optional[Operation]:
        """获取指定操作模板"""
        return self._operations.get(operation_id)

    def get_all_operations(self) -> Dict[str, Operation]:
        """获取所有操作模板"""
        return self._operations

    def get_query_operations(self) -> Dict[str, Operation]:
        """获取所有查询操作"""
        return {k: v for k, v in self._operations.items() if v.is_query()}

    def get_mutation_operations(self) -> Dict[str, Operation]:
        """获取所有变更操作"""
        return {k: v for k, v in self._operations.items() if v.is_mutation()}

    def find_operations_by_keywords(self, text: str) -> List[Operation]:
        """
        根据关键词查找匹配的操作

        Args:
            text: 用户输入的文本

        Returns:
            匹配的操作列表（按匹配程度排序）
        """
        text_lower = text.lower()
        matched = []

        for op in self._operations.values():
            # 计算匹配分数
            score = 0
            matched_keywords = []

            for keyword in op.keywords:
                if keyword.lower() in text_lower:
                    score += len(keyword)  # 关键词越长，权重越高
                    matched_keywords.append(keyword)

            if score > 0:
                matched.append({
                    "operation": op,
                    "score": score,
                    "matched_keywords": matched_keywords,
                })

        # 按分数降序排序
        matched.sort(key=lambda x: x["score"], reverse=True)
        return [m["operation"] for m in matched]

    def get_operation_context_for_llm(self) -> str:
        """
        生成用于 LLM 的操作上下文

        Returns:
            格式化的操作描述文本
        """
        lines = ["# 可用业务操作", ""]

        for op in self._operations.values():
            lines.append(f"## {op.id}")
            lines.append(f"名称: {op.name}")
            lines.append(f"描述: {op.description}")
            lines.append(f"类别: {op.category}")
            lines.append(f"关键词: {', '.join(op.keywords)}")

            if op.params:
                lines.append("参数:")
                for param in op.params:
                    required = "必需" if param.required else "可选"
                    enum_info = f" (枚举: {param.enum_from})" if param.enum_from else ""
                    lines.append(f"  - {param.name} ({param.type}, {required}): {param.description}{enum_info}")

            lines.append("")

        return "\n".join(lines)

    # ==================== 枚举相关方法 ====================

    def get_enum_values(self, enum_name: str, use_cache: bool = True) -> List[Dict[str, str]]:
        """
        获取枚举值列表

        Args:
            enum_name: 枚举名称
            use_cache: 是否使用缓存

        Returns:
            枚举值列表，每个元素包含 value 和 display 字段
        """
        enum_def = self._enums.get(enum_name)
        if not enum_def:
            logger.warning(f"未找到枚举定义: {enum_name}")
            return []

        # 检查缓存
        if use_cache and enum_name in self._enum_cache:
            values, expire_time = self._enum_cache[enum_name]
            if time.time() < expire_time:
                return values

        # 从数据库加载
        if self.db_manager is None:
            logger.warning(f"无法加载枚举 {enum_name}: 数据库管理器未设置")
            return []

        try:
            df = self.db_manager.execute_query(enum_def.source)
            values = []

            # 对于 park_names 枚举，添加"全部"特殊值（批量下发功能）
            if enum_name == "park_names":
                values.append({
                    "value": "全部",
                    "display": "全部"
                })

            for _, row in df.iterrows():
                values.append({
                    "value": row[enum_def.value_field],
                    "display": row[enum_def.display_field],
                })

            # 更新缓存
            self._enum_cache[enum_name] = (
                values,
                time.time() + enum_def.cache_ttl
            )

            return values

        except Exception as e:
            logger.error(f"加载枚举 {enum_name} 失败: {e}")
            return []

    def get_enum_values_flat(self, enum_name: str, use_cache: bool = True) -> List[str]:
        """
        获取枚举值列表（仅值）

        Args:
            enum_name: 枚举名称
            use_cache: 是否使用缓存

        Returns:
            枚举值列表
        """
        values = self.get_enum_values(enum_name, use_cache)
        return [v["value"] for v in values]

    def lookup_enum_value(self, enum_name: str, search_text: str) -> Optional[str]:
        """
        在枚举中查找匹配的值

        Args:
            enum_name: 枚举名称
            search_text: 搜索文本

        Returns:
            匹配的枚举值，未找到返回 None
        """
        values = self.get_enum_values(enum_name)

        # 精确匹配
        for v in values:
            if v["value"].lower() == search_text.lower():
                return v["value"]
            if v["display"].lower() == search_text.lower():
                return v["value"]

        # 模糊匹配
        search_lower = search_text.lower()
        for v in values:
            if search_lower in v["value"].lower():
                return v["value"]
            if search_lower in v["display"].lower():
                return v["value"]

        return None

    def invalidate_enum_cache(self, enum_name: Optional[str] = None) -> None:
        """
        使枚举缓存失效

        Args:
            enum_name: 指定枚举名称，为 None 则清除所有
        """
        if enum_name is None:
            self._enum_cache.clear()
            logger.info("已清除所有枚举缓存")
        elif enum_name in self._enum_cache:
            del self._enum_cache[enum_name]
            logger.info(f"已清除枚举缓存: {enum_name}")

    # ==================== 关系相关方法 ====================

    def get_relations(self) -> List[RelationDefinition]:
        """获取所有表关系"""
        return self._relations

    def find_relation_for_column(
        self, table: str, column: str
    ) -> Optional[RelationDefinition]:
        """
        查找指定列的关系

        Args:
            table: 表名
            column: 列名

        Returns:
            关系定义，未找到返回 None
        """
        for rel in self._relations:
            if rel.from_table == table and rel.from_column == column:
                return rel
        return None

    # ==================== 其他方法 ====================

    def get_category_info(self, category: str) -> Dict:
        """获取操作类别信息"""
        return self._categories.get(category, {})

    def get_province_name(self, code: str) -> Optional[str]:
        """根据省份代码获取省份名称"""
        return self._province_codes.get(code)

    def validate_plate(self, plate: str) -> tuple[bool, str]:
        """
        验证车牌号格式

        Args:
            plate: 车牌号

        Returns:
            (是否有效, 错误信息)
        """
        import re

        if not plate:
            return False, "车牌号不能为空"

        # 车牌正则
        pattern = r"^[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼][A-Z][A-Z0-9]{5,6}$"
        if not re.match(pattern, plate.upper()):
            province_code = plate[0] if plate else ""
            province_name = self.get_province_name(province_code)
            if not province_name:
                return False, f"无效的省份代码: {province_code}"
            return False, "车牌号格式不正确，应为: 省份简称+字母+5-6位字符"

        return True, ""

    def reload(self) -> None:
        """重新加载配置"""
        self._config.clear()
        self._operations.clear()
        self._enums.clear()
        self._relations.clear()
        self._categories.clear()
        self._province_codes.clear()
        self._enum_cache.clear()
        self._load_config()


# 全局单例
_knowledge_loader: Optional[KnowledgeLoader] = None


def get_knowledge_loader(db_manager=None, config_path: Optional[str] = None) -> KnowledgeLoader:
    """
    获取知识库加载器单例

    Args:
        db_manager: 数据库管理器
        config_path: 配置文件路径

    Returns:
        KnowledgeLoader 实例
    """
    global _knowledge_loader

    if _knowledge_loader is None:
        _knowledge_loader = KnowledgeLoader(db_manager, config_path)
    elif db_manager is not None and _knowledge_loader.db_manager is None:
        _knowledge_loader.db_manager = db_manager

    return _knowledge_loader
