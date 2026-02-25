# MySQL Web Enhancement Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 MySQL 数据导出工具实现 Web 增强功能，包括 Schema 智能缓存、AI 驱动的多表智能查询、变更预览增强和 Web 界面架构。

**Architecture:** 采用分层架构，后端使用 FastAPI 提供 REST API，前端使用 React + TypeScript。核心功能包括三层缓存架构（文件+内存+数据库）、交互式表选择消歧、渐进式学习机制、Before/After 变更对比预览。

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, React 18, TypeScript, Vite, Tailwind CSS, Pandas, Qwen API

---

## 任务分解与依赖关系

### 第一阶段：Schema 智能缓存系统（高优先级，基础依赖）

### Task 1: SchemaCache 类 - 三层缓存架构

**Files:**
- Create: `src/cache/schema_cache.py`
- Test: `tests/test_schema_cache.py`

**Step 1: Write the failing test**

```python
import unittest
from unittest.mock import MagicMock, patch
from src.cache.schema_cache import SchemaCache

class TestSchemaCache(unittest.TestCase):
    def setUp(self):
        self.mock_db = MagicMock()
        self.mock_db.get_table_schema.return_value = [
            {"name": "id", "type": "int", "comment": "主键"},
            {"name": "name", "type": "varchar", "comment": "姓名"}
        ]
        self.mock_db.get_all_tables.return_value = ["test_table"]
        
    def test_get_table_info_from_memory_cache(self):
        """测试从内存缓存获取表信息"""
        cache = SchemaCache(self.mock_db, cache_file="test_cache.json")
        # 首次调用应该查询数据库
        table_info = cache.get_table_info("test_table")
        self.assertEqual(table_info["table_name"], "test_table")
        
        # 第二次调用应该从内存缓存获取
        self.mock_db.get_table_schema.reset_mock()
        table_info2 = cache.get_table_info("test_table")
        self.mock_db.get_table_schema.assert_not_called()
        self.assertEqual(table_info, table_info2)
    
    def test_warm_up_cache(self):
        """测试预热缓存功能"""
        cache = SchemaCache(self.mock_db, cache_file="test_cache.json")
        cache.warm_up()
        self.mock_db.get_all_tables.assert_called()
        self.mock_db.get_table_schema.assert_called()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_schema_cache.py::TestSchemaCache::test_get_table_info_from_memory_cache -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.cache'"

**Step 3: Write minimal implementation**

```python
import json
import os
from typing import Dict, List, Optional
from collections import OrderedDict

class LRUCache:
    """简单的 LRU 缓存实现"""
    def __init__(self, maxsize: int = 100):
        self.maxsize = maxsize
        self.cache = OrderedDict()
    
    def get(self, key: str) -> Optional[dict]:
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        return None
    
    def put(self, key: str, value: dict):
        if key in self.cache:
            self.cache.move_to_end(key)
        elif len(self.cache) >= self.maxsize:
            self.cache.popitem(last=False)
        self.cache[key] = value

class SchemaCache:
    """Schema 智能缓存系统 - 三层缓存架构"""
    
    def __init__(self, db_manager, cache_file: str = "schema_cache.json"):
        self.db_manager = db_manager
        self.cache_file = cache_file
        self.memory_cache = LRUCache(maxsize=200)
        self.file_cache = {}
        self._load_file_cache()
    
    def _load_file_cache(self):
        """从文件加载缓存"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.file_cache = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.file_cache = {}
        else:
            self.file_cache = {}
    
    def _save_file_cache(self):
        """保存缓存到文件"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.file_cache, f, ensure_ascii=False, indent=2)
        except IOError:
            pass  # 忽略写入错误
    
    def get_table_info(self, table_name: str) -> dict:
        """获取表信息，优先从缓存读取"""
        # 1. 检查内存缓存
        cached = self.memory_cache.get(table_name)
        if cached is not None:
            return cached
        
        # 2. 检查文件缓存
        if table_name in self.file_cache:
            table_info = self.file_cache[table_name]
            self.memory_cache.put(table_name, table_info)
            return table_info
        
        # 3. 查询数据库
        try:
            schema_info = self.db_manager.get_table_schema(table_name)
            table_info = {
                "table_name": table_name,
                "columns": schema_info,
                "last_updated": "2026-02-24T00:00:00Z"
            }
            # 更新缓存
            self.memory_cache.put(table_name, table_info)
            self.file_cache[table_name] = table_info
            self._save_file_cache()
            return table_info
        except Exception:
            # 如果查询失败，返回空结构
            table_info = {
                "table_name": table_name,
                "columns": [],
                "last_updated": "2026-02-24T00:00:00Z"
            }
            return table_info
    
    def warm_up(self, force: bool = False):
        """预热缓存，启动时调用"""
        if not force and self.file_cache:
            return  # 已有缓存，不需要预热
        
        try:
            tables = self.db_manager.get_all_tables()
            for table in tables[:50]:  # 限制预热数量
                self.get_table_info(table)
        except Exception:
            pass  # 忽略预热错误
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_schema_cache.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/cache/schema_cache.py tests/test_schema_cache.py
git commit -m "feat: add SchemaCache with three-layer caching architecture"
```

### Task 2: SchemaCache 增强功能 - 搜索和关联表

**Files:**
- Modify: `src/cache/schema_cache.py`
- Test: `tests/test_schema_cache.py`

**Step 1: Write the failing test**

```python
def test_search_tables(self):
    """测试表搜索功能"""
    cache = SchemaCache(self.mock_db, cache_file="test_cache.json")
    # 预先加载一些表
    cache.file_cache = {
        "user_table": {"table_name": "user_table", "description": "用户表", "columns": []},
        "admin_user": {"table_name": "admin_user", "description": "管理员用户", "columns": []},
        "product_info": {"table_name": "product_info", "description": "产品信息", "columns": []}
    }
    results = cache.search_tables("user", limit=10)
    self.assertEqual(len(results), 2)
    self.assertTrue(any(r["table_name"] == "user_table" for r in results))
    self.assertTrue(any(r["table_name"] == "admin_user" for r in results))

def test_get_related_tables(self):
    """测试获取关联表功能"""
    cache = SchemaCache(self.mock_db, cache_file="test_cache.json")
    # 模拟外键关系
    cache.file_cache = {
        "orders": {
            "table_name": "orders",
            "foreign_keys": [{"column": "user_id", "references": "users.id"}],
            "columns": []
        },
        "users": {
            "table_name": "users", 
            "foreign_keys": [{"column": "role_id", "references": "roles.id"}],
            "columns": []
        },
        "roles": {
            "table_name": "roles",
            "columns": []
        }
    }
    related = cache.get_related_tables("orders", max_depth=2)
    self.assertIn("users", related)
    self.assertIn("roles", related)
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_schema_cache.py::TestSchemaCache::test_search_tables -v`
Expected: FAIL with "AttributeError: 'SchemaCache' object has no attribute 'search_tables'"

**Step 3: Write minimal implementation**

```python
# 在 SchemaCache 类中添加以下方法

def search_tables(self, keyword: str, limit: int = 10) -> list:
    """基于关键词搜索表名和描述"""
    results = []
    keyword_lower = keyword.lower()
    
    # 搜索所有缓存的表
    all_tables = set(self.file_cache.keys())
    # 也包含内存缓存中的表
    all_tables.update(self.memory_cache.cache.keys())
    
    for table_name in all_tables:
        score = 0
        table_info = self.get_table_info(table_name)
        
        # 表名匹配
        if keyword_lower in table_name.lower():
            score += 2
        
        # 列名匹配
        for col in table_info.get("columns", []):
            if keyword_lower in col.get("name", "").lower():
                score += 1
            if keyword_lower in col.get("comment", "").lower():
                score += 1
        
        if score > 0:
            results.append({
                "table_name": table_name,
                "score": score,
                "table_info": table_info
            })
    
    # 按分数排序并限制数量
    results.sort(key=lambda x: x["score"], reverse=True)
    return [r["table_info"] for r in results[:limit]]

def get_related_tables(self, table_name: str, max_depth: int = 2) -> list:
    """获取关联的表（通过外键推断）"""
    related_tables = set()
    current_tables = {table_name}
    
    for depth in range(max_depth):
        next_tables = set()
        for current_table in current_tables:
            table_info = self.get_table_info(current_table)
            foreign_keys = table_info.get("foreign_keys", [])
            
            for fk in foreign_keys:
                # 解析外键引用，格式如 "users.id"
                if "." in fk.get("references", ""):
                    ref_table = fk["references"].split(".")[0]
                    if ref_table not in related_tables and ref_table != current_table:
                        next_tables.add(ref_table)
                        related_tables.add(ref_table)
        
        current_tables = next_tables
        if not current_tables:
            break
    
    return list(related_tables)

def invalidate(self, table_name: str = None):
    """使缓存失效"""
    if table_name:
        # 清除特定表的缓存
        if table_name in self.memory_cache.cache:
            del self.memory_cache.cache[table_name]
        if table_name in self.file_cache:
            del self.file_cache[table_name]
    else:
        # 清除所有缓存
        self.memory_cache.cache.clear()
        self.file_cache.clear()
    
    self._save_file_cache()
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_schema_cache.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/cache/schema_cache.py tests/test_schema_cache.py
git commit -m "feat: enhance SchemaCache with search and related tables functionality"
```

### 第二阶段：AI 驱动的多表智能查询（高优先级，核心功能）

### Task 3: TableMatcher 类 - 表匹配引擎

**Files:**
- Create: `src/matcher/table_matcher.py`
- Test: `tests/test_table_matcher.py`

**Step 1: Write the failing test**

```python
import unittest
from unittest.mock import MagicMock
from src.matcher.table_matcher import TableMatcher

class TestTableMatcher(unittest.TestCase):
    def setUp(self):
        self.mock_cache = MagicMock()
        self.mock_cache.search_tables.return_value = [
            {"table_name": "car_white_list", "description": "固定车白名单", "columns": []},
            {"table_name": "vehicle_base", "description": "车辆基础信息", "columns": []}
        ]
        
    def test_match_tables_basic(self):
        """测试基本表匹配功能"""
        matcher = TableMatcher(self.mock_cache)
        result = matcher.match_tables("查固定车")
        self.assertIn("groups", result)
        self.assertIn("车辆", result["groups"])
        self.assertEqual(len(result["groups"]["车辆"]), 2)
        
    def test_smart_recommendation(self):
        """测试智能推荐功能"""
        matcher = TableMatcher(self.mock_cache)
        candidates = [
            {"table_name": "car_white_list", "description": "固定车白名单"},
            {"table_name": "car_temp", "description": "临时车记录"}
        ]
        recommended = matcher.smart_recommend("固定车", candidates)
        self.assertTrue(recommended[0]["recommended"])
        self.assertEqual(recommended[0]["table_name"], "car_white_list")
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_table_matcher.py::TestTableMatcher::test_match_tables_basic -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.matcher'"

**Step 3: Write minimal implementation**

```python
from typing import Dict, List, Any
import re

class TableMatcher:
    """表匹配引擎 - 将自然语言查询映射到数据库表"""
    
    def __init__(self, schema_cache):
        self.cache = schema_cache
        # 语义关键词映射
        self.semantic_keywords = {
            "车辆": ["car", "vehicle", "plate", "车牌", "固定车", "临时车"],
            "园区": ["park", "area", "zone", "园区", "停车场"],
            "人员": ["operator", "user", "admin", "人员", "用户", "管理员"],
            "订单": ["order", "bill", "invoice", "订单", "账单"],
            "配置": ["config", "setting", "配置", "参数"]
        }
    
    def match_tables(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        """
        返回分组后的候选表
        
        Returns:
            {
                "groups": {
                    "车辆": [
                        {"table": "car_white_list", "score": 0.95, "recommended": true},
                        {"table": "vehicle_base", "score": 0.80, "recommended": false}
                    ],
                    "园区": [
                        {"table": "park_info", "score": 0.92, "recommended": true}
                    ]
                },
                "total_count": 3
            }
        """
        # 提取查询中的实体
        entities = self._extract_entities(query)
        
        groups = {}
        total_count = 0
        
        for entity in entities:
            # 搜索相关表
            candidates = self.cache.search_tables(entity, limit=top_k * 2)
            if candidates:
                # 计算相似度分数
                scored_candidates = []
                for table_info in candidates:
                    score = self._calculate_similarity(query, entity, table_info)
                    scored_candidates.append({
                        "table": table_info["table_name"],
                        "score": score,
                        "table_info": table_info
                    })
                
                # 排序并应用智能推荐
                scored_candidates.sort(key=lambda x: x["score"], reverse=True)
                top_candidates = scored_candidates[:top_k]
                recommended = self.smart_recommend(query, [c["table_info"] for c in top_candidates])
                
                groups[entity] = recommended
                total_count += len(recommended)
        
        return {
            "groups": groups,
            "total_count": total_count
        }
    
    def _extract_entities(self, query: str) -> List[str]:
        """从查询中提取语义实体"""
        entities = []
        query_lower = query.lower()
        
        for category, keywords in self.semantic_keywords.items():
            for keyword in keywords:
                if keyword in query_lower:
                    if category not in entities:
                        entities.append(category)
                    break
        
        # 如果没有匹配到预定义类别，使用关键词本身
        if not entities:
            # 简单的关键词提取
            words = re.findall(r'\w+', query)
            entities = words[:3]  # 取前3个词
        
        return entities
    
    def _calculate_similarity(self, query: str, entity: str, table_info: Dict) -> float:
        """计算查询与表的相似度分数"""
        score = 0.0
        table_name = table_info["table_name"].lower()
        description = table_info.get("description", "").lower()
        
        # 表名匹配
        if entity.lower() in table_name:
            score += 0.4
        if query.lower() in table_name:
            score += 0.3
            
        # 描述匹配
        if entity.lower() in description:
            score += 0.2
        if query.lower() in description:
            score += 0.1
            
        # 列名匹配
        for col in table_info.get("columns", []):
            col_name = col.get("name", "").lower()
            col_comment = col.get("comment", "").lower()
            if entity.lower() in col_name or entity.lower() in col_comment:
                score += 0.1
            if query.lower() in col_name or query.lower() in col_comment:
                score += 0.05
        
        return min(score, 1.0)
    
    def smart_recommend(self, user_query: str, candidates: List[Dict]) -> List[Dict]:
        """
        基于上下文智能推荐表
        
        例如：用户说"固定车"时，优先推荐 car_white_list
        用户说"临时车"时，优先推荐 car_temp
        """
        query_lower = user_query.lower()
        result = []
        
        for candidate in candidates:
            table_name = candidate["table_name"]
            description = candidate.get("description", "")
            full_text = f"{table_name} {description}".lower()
            
            recommended = False
            # 固定车相关
            if "固定车" in query_lower and ("white" in full_text or "fixed" in full_text):
                recommended = True
            elif "临时车" in query_lower and ("temp" in full_text or "temporary" in full_text):
                recommended = True
            elif "园区" in query_lower and ("park" in full_text or "园区" in full_text):
                recommended = True
            elif "人员" in query_lower and ("operator" in full_text or "user" in full_text):
                recommended = True
            
            result.append({
                "table": table_name,
                "score": candidate.get("score", 0.5),
                "recommended": recommended,
                "table_info": candidate
            })
        
        # 确保至少有一个推荐
        if result and not any(r["recommended"] for r in result):
            result[0]["recommended"] = True
            
        return result
    
    def get_table_detail(self, table_name: str) -> Dict:
        """获取表的完整详情（字段、注释、外键等）"""
        return self.cache.get_table_info(table_name)
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_table_matcher.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/matcher/table_matcher.py tests/test_table_matcher.py
git commit -m "feat: add TableMatcher class for intelligent table matching"
```

### Task 4: PreferenceLearner 类 - 用户偏好学习

**Files:**
- Create: `src/learner/preference_learner.py`
- Test: `tests/test_preference_learner.py`

**Step 1: Write the failing test**

```python
import unittest
import os
from src.learner.preference_learner import PreferenceLearner

class TestPreferenceLearner(unittest.TestCase):
    def setUp(self):
        self.test_file = "test_preferences.json"
        if os.path.exists(self.test_file):
            os.remove(self.test_file)
    
    def tearDown(self):
        if os.path.exists(self.test_file):
            os.remove(self.test_file)
    
    def test_learn_and_lookup(self):
        """测试学习和查找功能"""
        learner = PreferenceLearner(storage_path=self.test_file)
        
        # 学习一个映射
        learner.learn(["固定车"], ["car_white_list"], "查固定车")
        
        # 查找记忆
        result = learner.lookup(["固定车"])
        self.assertIsNotNone(result)
        self.assertEqual(result["tables"], ["car_white_list"])
        self.assertGreaterEqual(result["confidence"], 0.5)
        
        # 再次学习，置信度应该提高
        learner.learn(["固定车"], ["car_white_list"], "查所有固定车")
        result2 = learner.lookup(["固定车"])
        self.assertGreater(result2["confidence"], result["confidence"])
    
    def test_lookup_combinations(self):
        """测试表组合查找"""
        learner = PreferenceLearner(storage_path=self.test_file)
        
        # 学习表组合
        learner.learn(["固定车", "园区"], ["car_white_list", "park_info"], "查固定车和园区")
        
        # 查找组合
        result = learner.lookup(["固定车", "园区"])
        self.assertIsNotNone(result)
        self.assertEqual(result["tables"], ["car_white_list", "park_info"])
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_preference_learner.py::TestPreferenceLearner::test_learn_and_lookup -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.learner'"

**Step 3: Write minimal implementation**

```python
import json
import os
from datetime import datetime
from typing import Dict, List, Optional

class PreferenceLearner:
    """用户偏好学习器 - 记住用户的选择模式"""
    
    def __init__(self, storage_path: str = "user_preferences.json"):
        self.storage_path = storage_path
        self.preferences = self._load_preferences()
    
    def _load_preferences(self) -> Dict:
        """加载用户偏好"""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        
        return {
            "semantic_mappings": {},
            "table_combinations": {},
            "field_mappings": {}
        }
    
    def _save_preferences(self):
        """保存用户偏好"""
        try:
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(self.preferences, f, ensure_ascii=False, indent=2)
        except IOError:
            pass
    
    def _make_combo_key(self, tables: List[str]) -> str:
        """生成表组合的键"""
        return "[" + ",".join(sorted(tables)) + "]"
    
    def _calculate_match(self, entities: List[str], tables: List[str]) -> float:
        """计算实体与表组合的匹配度"""
        if len(entities) != len(tables):
            return 0.0
        
        # 简单匹配：检查是否有共同关键词
        match_score = 0.0
        for entity in entities:
            entity_lower = entity.lower()
            for table in tables:
                if entity_lower in table.lower():
                    match_score += 0.3
                # 这里可以添加更复杂的匹配逻辑
        return min(match_score, 1.0)
    
    def learn(self, entities: List[str], selected_tables: List[str], user_query: str):
        """
        学习用户偏好
        entities: 提取的语义实体 ["固定车", "园区"]
        selected_tables: 用户选择的表 ["car_white_list", "park_info"]
        """
        # 1. 单表映射学习
        for entity, table in zip(entities, selected_tables):
            if entity not in self.preferences["semantic_mappings"]:
                self.preferences["semantic_mappings"][entity] = {
                    "table": table,
                    "confidence": 0.5,
                    "used_count": 0
                }
            
            # 更新置信度
            entry = self.preferences["semantic_mappings"][entity]
            entry["used_count"] += 1
            entry["confidence"] = min(0.95, entry["confidence"] + 0.1)
            entry["last_used"] = datetime.now().isoformat()
            entry["description"] = f"'{entity}' → {table}"
        
        # 2. 表组合学习
        combo_key = self._make_combo_key(selected_tables)
        if combo_key not in self.preferences["table_combinations"]:
            self.preferences["table_combinations"][combo_key] = {
                "tables": selected_tables,
                "confidence": 0.5,
                "used_count": 0,
                "description": user_query
            }
        
        combo_entry = self.preferences["table_combinations"][combo_key]
        combo_entry["used_count"] += 1
        combo_entry["confidence"] = min(0.95, combo_entry["confidence"] + 0.1)
        combo_entry["last_used"] = datetime.now().isoformat()
        
        # 3. 保存到文件
        self._save_preferences()
    
    def lookup(self, entities: List[str]) -> Optional[Dict]:
        """
        查找记忆中是否有匹配
        返回: None 或 {tables: [], confidence: float, description: str}
        """
        # 尝试单表映射
        if len(entities) == 1:
            entity = entities[0]
            if entity in self.preferences["semantic_mappings"]:
                entry = self.preferences["semantic_mappings"][entity]
                return {
                    "tables": [entry["table"]],
                    "confidence": entry["confidence"],
                    "description": entry["description"]
                }
        
        # 尝试表组合
        candidates = []
        for combo_key, entry in self.preferences["table_combinations"].items():
            # 计算实体与表组合的匹配度
            match_score = self._calculate_match(entities, entry["tables"])
            if match_score > 0.7:
                candidates.append((entry, match_score))
        
        if candidates:
            # 返回最高匹配的
            best = max(candidates, key=lambda x: x[1])
            return {
                "tables": best[0]["tables"],
                "confidence": best[0]["confidence"],
                "description": f"{best[0]['description']} (已使用{best[0]['used_count']}次)"
            }
        
        return None
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_preference_learner.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/learner/preference_learner.py tests/test_preference_learner.py
git commit -m "feat: add PreferenceLearner for progressive intelligence"
```

### Task 5: SmartQueryEngine 类 - 智能查询引擎

**Files:**
- Create: `src/matcher/smart_query_engine.py`
- Test: `tests/test_smart_query_engine.py`

**Step 1: Write the failing test**

```python
import unittest
from unittest.mock import MagicMock
from src.matcher.smart_query_engine import SmartQueryEngine

class TestSmartQueryEngine(unittest.TestCase):
    def setUp(self):
        self.mock_cache = MagicMock()
        self.mock_learner = MagicMock()
        self.mock_matcher = MagicMock()
        
    def test_process_query_with_memory(self):
        """测试有记忆时的查询处理"""
        engine = SmartQueryEngine(self.mock_cache, self.mock_learner, self.mock_matcher)
        
        # 模拟有高置信度记忆
        self.mock_learner.lookup.return_value = {
            "tables": ["car_white_list"],
            "confidence": 0.9,
            "description": "固定车表"
        }
        
        result = engine.process_query("查固定车")
        self.assertFalse(result["needs_interaction"])
        self.assertEqual(result["selected_tables"], ["car_white_list"])
        self.assertIn("已记忆", result["reason"])
        
    def test_process_query_without_memory(self):
        """测试无记忆时的查询处理"""
        engine = SmartQueryEngine(self.mock_cache, self.mock_learner, self.mock_matcher)
        
        # 模拟无记忆
        self.mock_learner.lookup.return_value = None
        self.mock_matcher.match_tables.return_value = {
            "groups": {"车辆": [{"table": "car_white_list", "score": 0.95, "recommended": True}]},
            "total_count": 1
        }
        
        result = engine.process_query("查固定车")
        self.assertTrue(result["needs_interaction"])
        self.assertEqual(len(result["suggestions"]), 1)
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_smart_query_engine.py::TestSmartQueryEngine::test_process_query_with_memory -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.matcher.smart_query_engine'"

**Step 3: Write minimal implementation**

```python
from typing import Dict, List, Any

class SmartQueryEngine:
    """智能查询引擎 - 结合缓存、匹配和学习"""
    
    def __init__(self, schema_cache, preference_learner, table_matcher):
        self.cache = schema_cache
        self.learner = preference_learner
        self.matcher = table_matcher
    
    def _extract_entities(self, user_query: str) -> List[str]:
        """提取查询中的语义实体"""
        # 复用 TableMatcher 的实体提取逻辑
        return self.matcher._extract_entities(user_query)
    
    def _find_alternatives(self, entities: List[str]) -> List[Dict]:
        """查找替代表选项"""
        candidates = self.matcher.match_tables(" ".join(entities))
        alternatives = []
        for group_name, tables in candidates["groups"].items():
            for table_info in tables:
                alternatives.append({
                    "group": group_name,
                    "table": table_info["table"],
                    "score": table_info["score"],
                    "recommended": table_info["recommended"]
                })
        return alternatives
    
    def process_query(self, user_query: str) -> Dict[str, Any]:
        """
        智能处理用户查询，包含学习机制
        
        Returns:
            {
                "needs_interaction": bool,      # 是否需要交互
                "selected_tables": list,       # 选中的表（自动或确认后）
                "reason": str,                 # 原因说明
                "suggestions": list            # 可供用户选择的表
            }
        """
        # 1. 语义提取
        entities = self._extract_entities(user_query)
        
        # 2. 尝试从学习记忆中匹配
        learned_tables = self.learner.lookup(entities)
        
        if learned_tables:
            # 有记忆，检查置信度
            if learned_tables["confidence"] >= 0.85:
                # 高置信度，直接应用，无需交互
                return {
                    "needs_interaction": False,
                    "selected_tables": learned_tables["tables"],
                    "reason": f"🎯 已记忆：{learned_tables['description']}",
                    "suggestions": []
                }
            else:
                # 中等置信度，询问用户是否使用记忆
                return {
                    "needs_interaction": True,
                    "selected_tables": learned_tables["tables"],  # 预选记忆
                    "reason": f"💭 记得您之前用过 {learned_tables['tables']}，继续使用？",
                    "suggestions": self._find_alternatives(entities)
                }
        
        # 3. 无记忆，需要首次交互
        candidates = self.matcher.match_tables(user_query)
        suggestions = []
        for group_name, tables in candidates["groups"].items():
            for table_info in tables:
                suggestions.append({
                    "group": group_name,
                    "table": table_info["table"],
                    "score": table_info["score"],
                    "recommended": table_info["recommended"]
                })
        
        return {
            "needs_interaction": True,
            "selected_tables": [],
            "reason": "🔍 发现了多个可能的表，请选择",
            "suggestions": suggestions
        }
    
    def record_user_choice(self, entities: List[str], selected_tables: List[str], user_query: str):
        """记录用户选择，用于学习"""
        self.learner.learn(entities, selected_tables, user_query)
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_smart_query_engine.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/matcher/smart_query_engine.py tests/test_smart_query_engine.py
git commit -m "feat: add SmartQueryEngine with progressive intelligence"
```

### 第三阶段：变更预览增强（中优先级，用户体验）

### Task 6: DiffRenderer 类 - Before/After 对比渲染

**Files:**
- Create: `src/preview/diff_renderer.py`
- Test: `tests/test_diff_renderer.py`

**Step 1: Write the failing test**

```python
import unittest
import pandas as pd
from src.preview.diff_renderer import DiffRenderer

class TestDiffRenderer(unittest.TestCase):
    def test_render_update_diff(self):
        """测试 UPDATE 操作的对比渲染"""
        renderer = DiffRenderer()
        
        before_df = pd.DataFrame([{"id": 1, "name": "张三", "state": 0}])
        after_df = pd.DataFrame([{"id": 1, "name": "张三", "state": 1}])
        
        changes = renderer.render_update_diff(before_df, after_df, ["id"])
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["changed_fields"], ["state"])
        self.assertEqual(changes[0]["before"]["state"], 0)
        self.assertEqual(changes[0]["after"]["state"], 1)
    
    def test_render_delete_preview(self):
        """测试 DELETE 操作的预览渲染"""
        renderer = DiffRenderer()
        
        before_df = pd.DataFrame([
            {"id": 1, "name": "张三", "state": 0},
            {"id": 2, "name": "李四", "state": 0}
        ])
        
        delete_data = renderer.render_delete_preview(before_df)
        self.assertEqual(len(delete_data), 2)
        self.assertEqual(delete_data[0]["id"], 1)
        self.assertEqual(delete_data[1]["id"], 2)
    
    def test_render_insert_preview(self):
        """测试 INSERT 操作的预览渲染"""
        renderer = DiffRenderer()
        
        values = {"login_name": "new_user", "name": "新用户", "state": 1}
        insert_data = renderer.render_insert_preview(values)
        self.assertEqual(insert_data["login_name"], "new_user")
        self.assertEqual(insert_data["name"], "新用户")
        self.assertEqual(insert_data["state"], 1)
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_diff_renderer.py::TestDiffRenderer::test_render_update_diff -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.preview'"

**Step 3: Write minimal implementation**

```python
import pandas as pd
from typing import Dict, List, Any, Optional

class DiffRenderer:
    """Before/After 数据对比渲染器"""
    
    def render_diff(self, before_df: pd.DataFrame,
                   after_df: pd.DataFrame,
                   operation_type: str,
                   key_columns: List[str]) -> Dict[str, Any]:
        """
        渲染变更对比
        
        Returns:
            {
                "operation_type": "update" | "insert" | "delete",
                "summary": {...},
                "changes": [...],  # 具体变更数据
                "warnings": [...]
            }
        """
        from src.txn_preview import summarize_diff
        
        summary = summarize_diff(before_df, after_df, key_columns)
        warnings = []
        
        if operation_type == "update":
            changes = self.render_update_diff(before_df, after_df, key_columns)
            if summary["updated"] > 10:
                warnings.append(f"⚠️ 此操作将更新 {summary['updated']} 行数据，请确认")
        elif operation_type == "delete":
            changes = self.render_delete_preview(before_df)
            if summary["deleted"] > 0:
                warnings.append(f"⚠️ 此操作将删除 {summary['deleted']} 行数据，不可恢复")
        elif operation_type == "insert":
            # INSERT 操作的 after_df 包含新数据
            changes = self.render_insert_preview(after_df.to_dict('records')[0] if not after_df.empty else {})
            if summary["inserted"] > 10:
                warnings.append(f"⚠️ 此操作将插入 {summary['inserted']} 行数据")
        else:
            changes = []
        
        return {
            "operation_type": operation_type,
            "summary": summary,
            "changes": changes,
            "warnings": warnings
        }
    
    def render_update_diff(self, before_df: pd.DataFrame, after_df: pd.DataFrame, key_columns: List[str]) -> List[Dict]:
        """
        渲染 UPDATE 操作的对比
        
        Returns: 对比行列表
        [
            {
                "id": "5",
                "before": {"name": "张三", "state": 0},
                "after": {"name": "张三", "state": 1},
                "changed_fields": ["state"]
            }
        ]
        """
        changes = []
        
        # 合并两个 DataFrame 来找到共同的行
        merged = before_df.merge(after_df, on=key_columns, how='inner', suffixes=('_before', '_after'))
        
        for _, row in merged.iterrows():
            before_row = {}
            after_row = {}
            changed_fields = []
            
            # 提取 key columns
            key_values = {}
            for key_col in key_columns:
                key_values[key_col] = row[key_col]
            
            # 提取非 key columns
            non_key_cols = [col for col in before_df.columns if col not in key_columns]
            for col in non_key_cols:
                before_val = row[f'{col}_before']
                after_val = row[f'{col}_after']
                before_row[col] = before_val
                after_row[col] = after_val
                
                # 检查值是否变化
                if before_val != after_val and not (pd.isna(before_val) and pd.isna(after_val)):
                    changed_fields.append(col)
            
            if changed_fields:  # 只有发生变化的行才添加
                changes.append({
                    **key_values,
                    "before": before_row,
                    "after": after_row,
                    "changed_fields": changed_fields
                })
        
        return changes
    
    def render_delete_preview(self, before_df: pd.DataFrame) -> List[Dict]:
        """渲染 DELETE 操作的预览数据"""
        if before_df.empty:
            return []
        return before_df.to_dict('records')
    
    def render_insert_preview(self, values: Dict) -> Dict:
        """渲染 INSERT 操作的预览数据"""
        return values
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_diff_renderer.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/preview/diff_renderer.py tests/test_diff_renderer.py
git commit -m "feat: add DiffRenderer for enhanced mutation preview"
```

### 第四阶段：Web 界面整体架构（低优先级，可后续实现）

### Task 7: FastAPI 后端入口和路由

**Files:**
- Create: `web_app.py`
- Create: `src/api/__init__.py`
- Create: `src/api/routes/query.py`
- Create: `src/api/routes/schema.py`
- Create: `src/api/routes/mutation.py`
- Create: `src/api/models.py`

**Step 1: Write the failing test**

```python
import pytest
from fastapi.testclient import TestClient
from web_app import app

def test_api_health_check():
    """测试 API 健康检查"""
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_query_analyze_endpoint():
    """测试查询分析端点"""
    client = TestClient(app)
    response = client.post("/api/query/analyze", json={
        "natural_language": "查固定车"
    })
    assert response.status_code == 200
    data = response.json()
    assert "needs_interaction" in data
    assert "selected_tables" in data
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_web_api.py::test_api_health_check -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'web_app'"

**Step 3: Write minimal implementation**

```python
# web_app.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.routes import query, schema, mutation

app = FastAPI(
    title="MySQL 数据导出工具 Web 版",
    description="基于 AI 的智能数据查询和导出工具",
    version="2.0"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(query.router, prefix="/api/query", tags=["查询"])
app.include_router(schema.router, prefix="/api/schema", tags=["Schema"])
app.include_router(mutation.router, prefix="/api/mutation", tags=["变更"])

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
```

```python
# src/api/models.py
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class QueryRequest(BaseModel):
    natural_language: str
    selected_tables: Optional[List[str]] = None

class QueryResponse(BaseModel):
    sql: str
    filename: str
    sheet_name: str
    reasoning: str
    needs_interaction: bool
    selected_tables: List[str]
    suggestions: List[Dict[str, Any]]

class MutationPreviewRequest(BaseModel):
    sql: str
    preview_sql: str
    key_columns: List[str]
    operation_type: str

class MutationPreviewResponse(BaseModel):
    operation_type: str
    summary: Dict[str, int]
    before_data: Optional[List[Dict]] = None
    after_data: Optional[List[Dict]] = None
    warnings: List[str] = []
    estimated_time: float
```

```python
# src/api/routes/query.py
from fastapi import APIRouter, Depends
from src.api.models import QueryRequest, QueryResponse

router = APIRouter()

@router.post("/analyze", response_model=QueryResponse)
async def analyze_query(request: QueryRequest):
    # TODO: 实现查询分析逻辑
    return QueryResponse(
        sql="",
        filename="result",
        sheet_name="Sheet1",
        reasoning="Placeholder response",
        needs_interaction=True,
        selected_tables=[],
        suggestions=[]
    )
```

```python
# src/api/routes/schema.py  
from fastapi import APIRouter

router = APIRouter()

@router.get("/tables")
async def get_all_tables():
    return {"tables": []}

@router.get("/table/{table_name}")
async def get_table_info(table_name: str):
    return {"table_name": table_name, "columns": []}
```

```python
# src/api/routes/mutation.py
from fastapi import APIRouter
from src.api.models import MutationPreviewRequest, MutationPreviewResponse

router = APIRouter()

@router.post("/preview", response_model=MutationPreviewResponse)
async def preview_mutation(request: MutationPreviewRequest):
    return MutationPreviewResponse(
        operation_type=request.operation_type,
        summary={"inserted": 0, "updated": 0, "deleted": 0},
        estimated_time=0.0
    )
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_web_api.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add web_app.py src/api/
git commit -m "feat: add FastAPI backend with basic routes"
```

## 依赖关系和执行顺序

### 串行依赖（必须按顺序执行）：
1. **Task 1 → Task 2**: SchemaCache 基础功能完成后才能添加搜索和关联功能
2. **Task 3 → Task 5**: TableMatcher 完成后才能集成到 SmartQueryEngine
3. **Task 4 → Task 5**: PreferenceLearner 完成后才能集成到 SmartQueryEngine
4. **Task 6**: DiffRenderer 依赖现有的 txn_preview.py 功能

### 并行执行（可以同时进行）：
- **Task 1, 3, 4, 6**: 这些任务相对独立，可以并行开发
- **Task 7**: Web API 可以在后端核心功能完成后单独开发

### 优先级排序：
1. **高优先级**: Task 1 (SchemaCache) - 基础性能优化
2. **高优先级**: Task 3, 4, 5 (智能查询) - 核心 AI 功能
3. **中优先级**: Task 6 (变更预览) - 用户体验增强
4. **低优先级**: Task 7 (Web API) - 前端集成

## 验收标准

每个任务完成的定义：

### Task 1 & 2 (SchemaCache):
- ✅ 单元测试通过率达到 100%
- ✅ 三层缓存（内存、文件、数据库）正常工作
- ✅ 搜索和关联表功能按设计文档实现
- ✅ 性能测试：100+ 表场景下响应时间 < 100ms

### Task 3, 4, 5 (智能查询):
- ✅ 单元测试覆盖所有分支逻辑
- ✅ 表匹配准确率达到 85% 以上（基于测试用例）
- ✅ 渐进式学习机制正常工作
- ✅ 交互式消歧流程符合设计文档

### Task 6 (变更预览):
- ✅ 所有变更类型（INSERT/UPDATE/DELETE）都能正确渲染
- ✅ Before/After 对比准确显示变化字段
- ✅ 警告信息根据影响范围正确触发

### Task 7 (Web API):
- ✅ 所有 API 端点返回正确的 JSON 格式
- ✅ 错误处理和输入验证完善
- ✅ CORS 配置正确，支持前端跨域请求

## 测试策略

1. **单元测试**: 每个类和方法都有对应的测试用例
2. **集成测试**: 测试模块间的集成（如 SmartQueryEngine + SchemaCache + PreferenceLearner）
3. **端到端测试**: 模拟完整用户流程（查询 → 选择表 → 生成 SQL → 预览 → 执行）
4. **性能测试**: 验证缓存系统在大数据量下的性能提升

## 增量交付计划

1. **第一阶段**: 完成 SchemaCache (Task 1, 2) - 提升基础性能
2. **第二阶段**: 完成智能查询核心 (Task 3, 4, 5) - 实现 AI 驱动功能  
3. **第三阶段**: 完成变更预览增强 (Task 6) - 改善用户体验
4. **第四阶段**: 完成 Web API (Task 7) - 支持前端集成

每个阶段完成后都可以独立部署和测试，确保系统的稳定性和可维护性。