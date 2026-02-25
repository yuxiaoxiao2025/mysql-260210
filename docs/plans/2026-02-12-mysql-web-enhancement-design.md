# MySQL Web Enhancement Design

## 设计概述

本文档描述了 MySQL 数据导出工具从命令行升级为 Web 应用的设计方案，解决以下核心问题：

1. **变更预览** - 显示具体的新增/修改/删除数据
2. **表搜索性能** - 支持百级以上表的快速定位
3. **多表智能查询** - 通过自然语言自动发现表关联
4. **Web 界面展示** - 提供直观的可视化操作体验

---

## 第一部分：Schema 智能缓存系统

### 问题分析

当前 `SchemaLoader` 每次调用 `get_schema_context()` 时都会：
1. 解析 mysql.md 文件
2. 对每个表调用 `db_manager.get_table_schema()` 查询数据库

对于 100+ 表的场景，这会导致：
- 每次请求延迟 3-10 秒
- 数据库 CPU 占用高
- 表越多问题越严重

### 设计方案

#### 1.1 三层缓存架构

```
┌─────────────────────────────────────────────┐
│          第一层：静态文件缓存                 │
│  (schema_cache.json)                        │
│  - 持久化存储，启动时加载                   │
│  - 表名、列名、注释等元数据                 │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│          第二层：内存缓存                    │
│  (进程内 Dict/LRU Cache)                   │
│  - 运行时热数据                             │
│  - 最近访问的表结构                         │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│          第三层：数据库查询                  │
│  - 仅在缓存未命中时调用                     │
│  - 后台异步更新过期数据                     │
└─────────────────────────────────────────────┘
```

#### 1.2 智能更新策略

| 策略 | 触发条件 | 说明 |
|------|---------|------|
| 启动时全量 | 程序启动 | 加载完整缓存，无缓存时触发 |
| 按需加载 | 用户查询某表 | 缓存未命中时异步加载该表 |
| 定期刷新 | 每30分钟 | 后台异步更新过期的表结构 |
| 手动刷新 | 用户点击刷新 | 重新加载指定表或全部 |

#### 1.3 缓存数据结构

```json
{
  "version": "1.0",
  "last_updated": "2026-02-12T14:30:00Z",
  "tables": {
    "cloud_operator": {
      "database": "parkcloud",
      "description": "登录人员表",
      "columns": [
        {"name": "id", "type": "bigint", "comment": "主键ID"},
        {"name": "login_name", "type": "varchar(50)", "comment": "登录名"}
      ],
      "foreign_keys": [
        {"column": "cloud_role_id", "references": "cloud_role.id"}
      ],
      "last_synced": "2026-02-12T14:30:00Z"
    }
  }
}
```

#### 1.4 组件设计

**SchemaCache 类**

```python
class SchemaCache:
    def __init__(self, db_manager: DatabaseManager, cache_file: str = "schema_cache.json"):
        self.db_manager = db_manager
        self.cache_file = cache_file
        self.memory_cache = LRUCache(maxsize=200)  # 内存缓存

    def get_table_info(self, table_name: str) -> dict:
        """获取表信息，优先从缓存读取"""
        # 1. 检查内存缓存
        # 2. 检查文件缓存
        # 3. 查询数据库（异步）

    def warm_up(self, force: bool = False):
        """预热缓存，启动时调用"""

    def search_tables(self, keyword: str, limit: int = 10) -> list:
        """基于关键词搜索表名和描述"""

    def get_related_tables(self, table_name: str, max_depth: int = 2) -> list:
        """获取关联的表（通过外键推断）"""

    def invalidate(self, table_name: str = None):
        """使缓存失效"""
```

---

---

## 第二部分：AI 驱动的多表智能查询（含交互式消歧）

### 场景回顾与问题

用户查询示例：
```
"查一辆车是否是固定车、下发到哪些园区、谁添加的"
```

用户面临的挑战：
1. **字段歧义** - "车牌"字段可能存在于多个表中
2. 不知道表名（固定车表？园区表？添加人表？）
3. 不知道表之间的关联关系
4. 可能涉及多个数据库（parkcloud、cloudinterface 等）

**字段歧义示例：**
```
用户说："查一辆车"

数据库里可能有：
├── vehicle_base.plate       (车辆基础信息表)
├── car_white_list.plate     (固定车白名单)
├── car_temp.plate           (临时车记录)
├── park_record.plate        (停车记录)
└── ...

AI 怎么知道用户指的是哪个表？ → 需要用户确认！
```

### 设计方案

#### 2.1 智能查询流程（含消歧）

```
┌─────────────────────────────────────────────────────────┐
│              用户输入自然语言                              │
│         "查一辆车是否是固定车、下发到哪些园区、谁添加的"   │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│          第一步：语义实体提取                             │
│  提取关键概念：                                           │
│  - 车辆 (plate_number/car_id)                            │
│  - 固定车 (is_fixed/fixed_car)                           │
│  - 园区 (park_name/park_id)                              │
│  - 添加人 (operator_name/creator_id)                     │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│          第二步：候选表搜索                               │
│  基于关键词搜索相关表，返回候选列表：                       │
│                                                          │
│  📋 与"车辆"相关的表（按相关性排序）：                     │
│  ┌────────────────────────────────────────────────────┐   │
│  │ ✅ car_white_list (固定车白名单) - 匹配度 0.95   │   │
│  │    包含字段: plate, park_id, operator_id...      │   │
│  │ ✅ vehicle_base (车辆基础信息) - 匹配度 0.80    │   │
│  │    包含字段: plate, car_type, color...          │   │
│  │ ⚪ car_temp (临时车记录) - 匹配度 0.70         │   │
│  │    包含字段: plate, entry_time...              │   │
│  └────────────────────────────────────────────────────┘   │
│                                                          │
│  📋 与"园区"相关的表：                                    │
│  ┌────────────────────────────────────────────────────┐   │
│  │ ✅ park_info (园区信息) - 匹配度 0.92             │   │
│  │ ✅ park_area (园区区域) - 匹配度 0.75             │   │
│  └────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│          第三步：用户确认（关键步骤！）                    │
│                                                          │
│  ❓ 检测到多个可能的表，请确认：                           │
│                                                          │
│  "车辆"相关表，你想要哪一个？                              │
│  ○ car_white_list (固定车白名单) - 推荐 ⭐              │
│  ○ vehicle_base (车辆基础信息)                          │
│  ○ car_temp (临时车记录)                                │
│                                                          │
│  "园区"相关表：                                          │
│  ○ park_info (园区信息) - 推荐 ⭐                       │
│  ○ park_area (园区区域)                                 │
│                                                          │
│  [确认并继续] [查看表详情] [全部选择]                     │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│          第四步：关系推断                                │
│  基于用户确认的表，分析关联关系：                         │
│  1. 外键关联（从 Schema 缓存获取）                        │
│  2. 命名语义关联（car_id ↔ car_info_id）                │
│  3. 常见模式推断（operator_id → cloud_operator.id）     │
│                                                          │
│  生成：表关系图 + 推荐的 JOIN 路径                        │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│          第五步：SQL 生成与确认                           │
│  - 根据确认的表和关联关系生成 SQL                         │
│  - 再次确认后执行                                         │
└─────────────────────────────────────────────────────────┘
```

#### 2.2 消歧界面设计（Web 前端）

```html
<!-- 交互式表选择器 -->
<div class="table-selector">
  <h3>🔍 发现了多个相关表，请选择：</h3>

  <!-- 分组1：车辆相关 -->
  <div class="table-group">
    <h4>🚗 车辆相关</h4>
    <div class="table-card recommended" data-table="car_white_list">
      <label>
        <input type="checkbox" checked>
        <span class="table-name">car_white_list</span>
        <span class="tag recommended">推荐 ⭐</span>
        <span class="db-name">parkcloud</span>
      </label>
      <div class="table-desc">固定车白名单</div>
      <div class="table-preview">
        <span class="field">plate</span> (车牌),
        <span class="field">park_id</span> (园区ID),
        <span class="field">operator_id</span> (添加人)
      </div>
    </div>

    <div class="table-card" data-table="vehicle_base">
      <label>
        <input type="checkbox">
        <span class="table-name">vehicle_base</span>
        <span class="db-name">parkcloud</span>
      </label>
      <div class="table-desc">车辆基础信息</div>
      <div class="table-preview">
        <span class="field">plate</span> (车牌),
        <span class="field">car_type</span> (车型),
        <span class="field">color</span> (颜色)
      </div>
    </div>
  </div>

  <!-- 分组2：园区相关 -->
  <div class="table-group">
    <h4>🏢 园区相关</h4>
    <div class="table-card recommended" data-table="park_info">
      <label>
        <input type="checkbox" checked>
        <span class="table-name">park_info</span>
        <span class="tag recommended">推荐 ⭐</span>
        <span class="db-name">parkcloud</span>
      </label>
      <div class="table-desc">园区信息</div>
    </div>
  </div>

  <div class="actions">
    <button class="btn-secondary">查看表详情</button>
    <button class="btn-primary">确认并生成查询</button>
  </div>
</div>
```

#### 2.3 表详情展开功能

用户可以点击"查看表详情"来确认：

```
┌─────────────────────────────────────────────────────────┐
│  表详情：car_white_list (parkcloud)                      │
├─────────────────────────────────────────────────────────┤
│  描述：固定车白名单表                                     │
├─────────────────────────────────────────────────────────┤
│  字段列表：                                              │
│  ┌────────────────┬───────────┬─────────────────────┐   │
│  │ 字段名          │ 类型       │ 说明                 │   │
│  ├────────────────┼───────────┼─────────────────────┤   │
│  │ id             │ bigint    │ 主键                 │   │
│  │ plate          │ varchar   │ 车牌号               │   │
│  │ park_id        │ bigint    │ 所属园区ID           │   │
│  │ is_fixed       │ tinyint   │ 是否固定车(1=是)     │   │
│  │ operator_id    │ bigint    │ 添加人ID             │   │
│  └────────────────┴───────────┴─────────────────────┘   │
├─────────────────────────────────────────────────────────┤
│  外键关联：                                              │
│  • park_id → park_info.id                               │
│  • operator_id → cloud_operator.id                       │
└─────────────────────────────────────────────────────────┘
```

#### 2.4 优化后的匹配引擎

```python
class TableMatcher:
    def match_tables(self, query: str, top_k: int = 5) -> dict:
        """
        返回分组后的候选表

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

    def get_table_detail(self, table_name: str) -> dict:
        """获取表的完整详情（字段、注释、外键等）"""

    def smart_recommend(self, user_query: str, candidates: list) -> dict:
        """
        基于上下文智能推荐表

        例如：用户说"固定车"时，优先推荐 car_white_list
        用户说"临时车"时，优先推荐 car_temp
        """
```

#### 2.5 用户体验优化

1. **学习机制** - 记住用户的选择偏好
2. **快捷预设** - 常用查询可以保存为预设
3. **渐进式披露** - 先显示推荐表，展开后才显示更多选项
4. **搜索过滤** - 在候选表中进一步关键词搜索

---

这个设计解决了字段歧义问题吗？核心是：**AI 先找到候选表 → 让用户确认 → 再生成 SQL**，而不是 AI 猜测。

#### 2.6 渐进式学习机制（智能化体验）

**问题：** 每次都交互太麻烦，需要"记住用户偏好"

**解决方案：** 系统学习用户的选择模式，从"交互确认"到"自动应用"

```
┌─────────────────────────────────────────────────────────┐
│              渐进式学习体验示意                           │
└─────────────────────────────────────────────────────────┘

第1次查询："查固定车"
  ↓
  AI 发现候选表，展示 → 用户确认选择 car_white_list
  ↓
  🧠 系统记住：用户说"固定车" → car_white_list

第2次查询："查所有固定车"
  ↓
  AI 发现候选表 → 🎯 自动应用记忆！直接用 car_white_list
  ↓
  ✅ 直接生成 SQL，无需交互

第3次查询："查固定车下发到哪个园区"
  ↓
  AI 发现候选表：
    - 车辆表：自动用 car_white_list（已记忆）
    - 园区表：首次查询，需要用户确认
  ↓
  用户确认 park_info
  ↓
  🧠 系统记住：组合 [car_white_list, park_info]

第4次查询："查固定车和园区信息"
  ↓
  🎯 直接应用记忆的组合！无需交互
```

#### 2.7 学习系统架构

```
┌─────────────────────────────────────────────────────────┐
│                  用户学习偏好存储                          │
├─────────────────────────────────────────────────────────┤
│  user_preferences.json                                   │
│  {                                                      │
│    "semantic_mappings": {                              │
│      "固定车": {                                         │
│        "table": "car_white_list",                        │
│        "confidence": 0.95,                               │
│        "used_count": 5,                                  │
│        "last_used": "2026-02-12T14:30:00Z"              │
│      },                                                 │
│      "临时车": {                                         │
│        "table": "car_temp",                              │
│        "confidence": 0.85,                                │
│        "used_count": 2                                   │
│      }                                                   │
│    },                                                    │
│    "table_combinations": {                               │
│      "[car_white_list,park_info]": {                    │
│        "description": "固定车和园区",                     │
│        "confidence": 0.90,                               │
│        "used_count": 3,                                  │
│        "last_used": "2026-02-12T14:25:00Z"              │
│      }                                                   │
│    },                                                    │
│    "field_mappings": {                                  │
│      "车牌": "plate",                                    │
│      "园区": "park_id"                                   │
│    }                                                     │
│  }                                                      │
└─────────────────────────────────────────────────────────┘
```

#### 2.8 智能查询流程（学习版）

```python
class SmartQueryEngine:
    def __init__(self, schema_cache: SchemaCache, learner: PreferenceLearner):
        self.cache = schema_cache
        self.learner = learner  # 学习组件

    def process_query(self, user_query: str) -> dict:
        """
        智能处理用户查询，包含学习机制

        返回：
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
        candidates = self._find_candidates(entities)
        return {
            "needs_interaction": True,
            "selected_tables": [],
            "reason": "🔍 发现了多个可能的表，请选择",
            "suggestions": candidates
        }

    def record_user_choice(self, entities: list, selected_tables: list, user_query: str):
        """记录用户选择，用于学习"""
        self.learner.learn(entities, selected_tables, user_query)
```

#### 2.9 偏好学习器设计

```python
class PreferenceLearner:
    def __init__(self, storage_path: str = "user_preferences.json"):
        self.storage_path = storage_path
        self.preferences = self._load_preferences()

    def learn(self, entities: list, selected_tables: list, user_query: str):
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

        # 3. 保存到文件
        self._save_preferences()

    def lookup(self, entities: list) -> dict:
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
                    "description": f"'{entity}' → {entry['table']} (已使用{entry['used_count']}次)"
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

#### 2.10 Web 交互界面（学习版）

```
┌─────────────────────────────────────────────────────────┐
│  智能查询 - 渐进式学习体验                                │
├─────────────────────────────────────────────────────────┤
│  输入框：查固定车和园区信息                                │
│                                                         │
│  场景 A：首次查询（需交互）                               │
│  ┌──────────────────────────────────────────────────┐   │
│  │ 🔍 发现了多个相关表，请选择                       │   │
│  │                                                   │   │
│  │ 🚗 车辆相关                                       │   │
│  │   ✅ car_white_list (固定车白名单) 推荐 ⭐        │   │
│  │   ⬜ vehicle_base (车辆基础信息)                   │   │
│  │                                                   │   │
│  │ 🏢 园区相关                                       │   │
│  │   ✅ park_info (园区信息) 推荐 ⭐                │   │
│  │                                                   │   │
│  │   [👾 记住我的选择] [确认并生成]                  │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
│  场景 B：有记忆（自动应用）                              │
│  ┌──────────────────────────────────────────────────┐   │
│  │ 🎯 已识别您的查询模式：                           │   │
│  │                                                   │   │
│  │  表：car_white_list + park_info                   │   │
│  │  说明：固定车和园区信息 (已使用5次)               │   │
│  │                                                   │   │
│  │  生成的 SQL：                                     │   │
│  │  SELECT c.plate AS '车牌',                       │   │
│  │         p.name AS '园区名称'                      │   │
│  │  FROM car_white_list c                           │   │
│  │  LEFT JOIN park_info p ON c.park_id = p.id       │   │
│  │                                                   │   │
│  │   [修改表选择] [✅ 直接执行]                     │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

#### 2.11 学习体验提升

| 阶段 | 用户输入 | 系统响应 | 体验 |
|------|---------|---------|------|
| 第1次 | "查固定车" | 展示候选表，让选择 | 需要交互 |
| 第2次 | "查所有固定车" | 直接用记忆的表 | ✨ 无需交互 |
| 第3次 | "查固定车和园区" | 固定车用记忆，园区需选择 | 部分自动化 |
| 第5次 | "固定车园区信息" | 全部用记忆的组合 | ✨ 完全自动化 |

---

**总结：渐进式智能**
- **首次**：交互确认（避免错误）
- **重复**：自动应用（提升效率）
- **混合**：部分记忆 + 部分交互（平衡）
- **持续学习**：用得越多越智能

---

## 第三部分：变更预览增强（Before/After 对比）

### 问题分析

当前变更预览只显示统计信息：
```
📊 变更预览:
  - 插入: 0 行
  - 更新: 0 行
  - 删除: 3 行
```

用户需求：
- **新增**：显示即将插入的数据
- **修改**：显示修改前后的数据对比
- **删除**：显示将被删除的数据

### 设计方案

#### 3.1 预览数据获取机制

现有代码已具备 `execute_in_transaction` 功能，可以获取 before/after 数据：

```python
# 在 db_manager.py 中已有的实现
result = db.execute_in_transaction(
    mutation_sql=sql_to_execute,
    preview_sql=preview_sql,  # LLM 生成的预览查询
    key_columns=key_columns,
    commit=False  # 预览阶段不提交
)

# 返回值包含：
# - before: 变更前的 DataFrame
# - after: 变更后的 DataFrame
# - diff_summary: 差异摘要
```

**需要增强的是：前端展示和对比渲染**

#### 3.2 三种变更类型的预览设计

##### 3.2.1 删除操作预览

```
┌─────────────────────────────────────────────────────────┐
│  🗑️  变更预览 - DELETE 操作                            │
├─────────────────────────────────────────────────────────┤
│  生成的 SQL：                                           │
│  DELETE FROM parkcloud.cloud_operator                   │
│  WHERE state = 0;                                      │
├─────────────────────────────────────────────────────────┤
│  📊 影响统计：                                          │
│  • 将删除：3 行数据                                      │
│  • 预估耗时：0.02 秒                                    │
├─────────────────────────────────────────────────────────┤
│  ⚠️  即将被删除的数据：                                   │
│  ┌──────────────────────────────────────────────────┐   │
│  │ ID │ 登录名    │ 姓名     │ 电话号      │ 状态    │   │
│  ├──────────────────────────────────────────────────┤   │
│  │ 5  │ user_001  │ 张三     │ 138****0001 │ 0 (禁用)│   │
│  │ 12 │ user_002  │ 李四     │ 139****0002 │ 0 (禁用)│   │
│  │ 23 │ test_user │ 测试员   │ 137****0003 │ 0 (禁用)│   │
│  └──────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────┤
│  ⚠️  警告：                                             │
│  • 此操作不可恢复，请确认是否已备份必要数据                 │
│  • 删除后这些用户的关联数据可能仍保留                     │
├─────────────────────────────────────────────────────────┤
│  [❌ 取消]  [🗑️  确认删除]                              │
└─────────────────────────────────────────────────────────┘
```

##### 3.2.2 修改操作预览（Before/After 对比）

```
┌─────────────────────────────────────────────────────────┐
│  ✏️  变更预览 - UPDATE 操作                             │
├─────────────────────────────────────────────────────────┤
│  生成的 SQL：                                           │
│  UPDATE parkcloud.cloud_operator                        │
│  SET state = 1                                         │
│  WHERE state = 0;                                      │
├─────────────────────────────────────────────────────────┤
│  📊 影响统计：                                          │
│  • 将更新：3 行数据                                      │
│  • 状态变化：禁用(0) → 启用(1)                          │
├─────────────────────────────────────────────────────────┤
│  🔍 变更前后对比：                                       │
│  ┌──────────────────────────────────────────────────┐   │
│  │               修改前 (BEFORE)     →   修改后 (AFTER)  │
│  ├──────────────────────────────────────────────────┤   │
│  │ ID │ 登录名   │ 状态    │     │ ID │ 登录名   │ 状态 │   │
│  ├──────────────────────────────────────────────────┤   │
│  │ 5  │ user_001 │ 0 (禁用)│ ───►│ 5  │ user_001 │ 1(启用)│  🔴
│  │ 12 │ user_002 │ 0 (禁用)│ ───►│ 12 │ user_002 │ 1(启用)│  🔴
│  │ 23 │ test_u  │ 0 (禁用)│ ───►│ 23 │ test_u  │ 1(启用)│  🔴
│  └──────────────────────────────────────────────────┘   │
│                                                         │
│  🔴 标记表示有变化的字段                                  │
├─────────────────────────────────────────────────────────┤
│  ⚠️  注意：                                             │
│  • 启用后这些用户将可以登录系统                           │
│  • 确认这些用户已通过审核                                 │
├─────────────────────────────────────────────────────────┤
│  [❌ 取消]  [✅ 确认更新]                               │
└─────────────────────────────────────────────────────────┘
```

##### 3.2.3 新增操作预览

```
┌─────────────────────────────────────────────────────────┐
│  ➕ 变更预览 - INSERT 操作                              │
├─────────────────────────────────────────────────────────┤
│  生成的 SQL：                                           │
│  INSERT INTO parkcloud.cloud_operator                   │
│  (login_name, name, phone, state)                      │
│  VALUES                                               │
│  ('new_user', '新用户', '13800001234', 1);            │
├─────────────────────────────────────────────────────────┤
│  📊 影响统计：                                          │
│  • 将新增：1 行数据                                      │
│  • ID 将由数据库自动生成                                 │
├─────────────────────────────────────────────────────────┤
│  ➕ 即将插入的数据：                                      │
│  ┌──────────────────────────────────────────────────┐   │
│  │ 字段        │ 值                      │ 说明      │   │
│  ├──────────────────────────────────────────────────┤   │
│  │ login_name  │ new_user               │ 登录名    │   │
│  │ name        │ 新用户                  │ 姓名      │   │
│  │ phone       │ 13800001234            │ 电话号    │   │
│  │ state       │ 1 (启用)               │ 状态      │   │
│  │ id          │ [自动生成]              │ 主键      │   │
│  └──────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────┤
│  ⚠️  注意：                                             │
│  • 确认 login_name 是否已存在                           │
│  • 新增后可使用登录名和默认密码登录                       │
├─────────────────────────────────────────────────────────┤
│  [❌ 取消]  [➕ 确认新增]                               │
└─────────────────────────────────────────────────────────┘
```

#### 3.3 对比渲染器设计

```python
class DiffRenderer:
    """Before/After 数据对比渲染器"""

    def render_diff(self, before_df: pd.DataFrame,
                   after_df: pd.DataFrame,
                   operation_type: str,
                   key_columns: list) -> dict:
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

    def render_update_diff(self, before_df, after_df, key_columns) -> list:
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

    def render_delete_preview(self, before_df) -> list:
        """渲染 DELETE 操作的预览数据"""

    def render_insert_preview(self, values: dict) -> dict:
        """渲染 INSERT 操作的预览数据"""
```

#### 3.4 前端组件设计（React 示例）

```tsx
// DiffTable.tsx - 变更对比表格
interface DiffTableProps {
  operation: 'insert' | 'update' | 'delete';
  beforeData?: Record<string, any>[];
  afterData?: Record<string, any>[];
  keyColumns: string[];
  onConfirm: () => void;
  onCancel: () => void;
}

const DiffTable: React.FC<DiffTableProps> = ({
  operation,
  beforeData,
  afterData,
  keyColumns,
  onConfirm,
  onCancel
}) => {
  return (
    <div className="diff-preview">
      {/* 操作标题 */}
      <h2>
        {operation === 'insert' && '➕ 新增预览'}
        {operation === 'update' && '✏️ 修改预览'}
        {operation === 'delete' && '🗑️ 删除预览'}
      </h2>

      {/* 统计信息 */}
      <div className="summary">
        <StatsSummary operation={operation} data={beforeData} />
      </div>

      {/* 数据展示 */}
      {operation === 'delete' && (
        <DeletePreview data={beforeData} />
      )}

      {operation === 'insert' && (
        <InsertPreview data={afterData} />
      )}

      {operation === 'update' && (
        <UpdateComparison
          before={beforeData}
          after={afterData}
          keyColumns={keyColumns}
        />
      )}

      {/* 警告信息 */}
      <div className="warnings">
        <OperationWarnings operation={operation} />
      </div>

      {/* 操作按钮 */}
      <div className="actions">
        <button onClick={onCancel} className="btn-cancel">❌ 取消</button>
        <button onClick={onConfirm} className="btn-confirm">
          {operation === 'insert' && '➕ 确认新增'}
          {operation === 'update' && '✅ 确认更新'}
          {operation === 'delete' && '🗑️ 确认删除'}
        </button>
      </div>
    </div>
  );
};

// UpdateComparison.tsx - 修改操作对比组件
const UpdateComparison = ({ before, after, keyColumns }) => {
  return (
    <table className="diff-table">
      <thead>
        <tr>
          <th rowSpan={2} colSpan={before[0].keys.length}>修改前 (BEFORE)</th>
          <th></th>
          <th rowSpan={2} colSpan={after[0].keys.length}>修改后 (AFTER)</th>
        </tr>
        <tr>
          {/* 列名 */}
          {Object.keys(before[0]).map(key => <th key={key}>{key}</th>)}
          <th></th>
          {Object.keys(after[0]).map(key => <th key={key}>{key}</th>)}
        </tr>
      </thead>
      <tbody>
        {before.map((row, idx) => {
          const afterRow = after.find(a =>
            keyColumns.every(k => a[k] === row[k])
          );
          return (
            <tr key={idx}>
              {Object.values(row).map((val, i) => (
                <td
                  key={i}
                  className={hasChanged(row, afterRow, i) ? 'changed' : ''}
                >
                  {val}
                </td>
              ))}
              <td className="arrow">→</td>
              {Object.values(afterRow).map((val, i) => (
                <td
                  key={i}
                  className={hasChanged(row, afterRow, i) ? 'changed' : ''}
                >
                  {val}
                </td>
              ))}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
};
```

#### 3.5 样式设计（对比表格）

```css
.diff-table {
  border-collapse: collapse;
  width: 100%;
  font-size: 13px;
}

.diff-table th,
.diff-table td {
  border: 1px solid #ddd;
  padding: 8px 12px;
  text-align: left;
}

.diff-table th {
  background: #f5f5f5;
  font-weight: 600;
}

.diff-table .arrow {
  background: #fafafa;
  text-align: center;
  font-size: 18px;
}

.diff-table .changed {
  background: #fff3e0;
  color: #e65100;
  font-weight: 500;
  border-left: 3px solid #ff9800;
}

/* 统计卡片 */
.summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin: 20px 0;
}

.stat-card {
  background: #f5f5f5;
  padding: 16px;
  border-radius: 8px;
  text-align: center;
}

.stat-value {
  font-size: 32px;
  font-weight: bold;
  color: #1976d2;
}

.stat-label {
  color: #666;
  font-size: 14px;
}

/* 警告区域 */
.warnings {
  background: #fff3e0;
  border-left: 4px solid #ff9800;
  padding: 12px 16px;
  margin: 16px 0;
  border-radius: 4px;
}

.warnings ul {
  margin: 8px 0 0 20px;
}
```

#### 3.6 API 接口设计

```python
# FastAPI 路由
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel

app = FastAPI()

class MutationPreviewRequest(BaseModel):
    sql: str
    preview_sql: str
    key_columns: List[str]
    operation_type: str  # "insert" | "update" | "delete"

class MutationPreviewResponse(BaseModel):
    operation_type: str
    summary: dict  # {"inserted": 0, "updated": 3, "deleted": 0}
    before_data: Optional[List[dict]] = None
    after_data: Optional[List[dict]] = None
    warnings: List[str] = []
    estimated_time: float  # 预估执行时间

@app.post("/api/mutation/preview", response_model=MutationPreviewResponse)
async def preview_mutation(request: MutationPreviewRequest, background_tasks: BackgroundTasks):
    """
    预览变更操作（不提交）
    """
    start_time = time.time()

    # 执行事务预览
    result = db.execute_in_transaction(
        mutation_sql=request.sql,
        preview_sql=request.preview_sql,
        key_columns=request.key_columns,
        commit=False
    )

    # 渲染对比
    renderer = DiffRenderer()
    diff_data = renderer.render_diff(
        before_df=result["before"],
        after_df=result["after"],
        operation_type=request.operation_type,
        key_columns=request.key_columns
    )

    # 预估执行时间
    estimated_time = time.time() - start_time

    return MutationPreviewResponse(
        operation_type=request.operation_type,
        summary=result["diff_summary"],
        before_data=result["before"].to_dict("records") if not result["before"].empty else None,
        after_data=result["after"].to_dict("records") if not result["after"].empty else None,
        warnings=diff_data["warnings"],
        estimated_time=estimated_time
    )

@app.post("/api/mutation/execute")
async def execute_mutation(request: MutationPreviewRequest):
    """
    确认并执行变更操作
    """
    result = db.execute_in_transaction(
        mutation_sql=request.sql,
        preview_sql=request.preview_sql,
        key_columns=request.key_columns,
        commit=True
    )

    return {
        "success": True,
        "summary": result["diff_summary"]
    }
```

---

这个部分是否满足你对变更预览的需求？接下来我将展示 **第四部分：Web 界面整体架构**。

---

## 第四部分：Web 界面整体架构

### 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           Web 浏览器 (前端)                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   查询页面   │  │   表选择器   │  │   SQL预览    │  │  变更预览    │       │
│  │  (自然语言)  │  │  (智能消歧)  │  │  (结果展示)  │  │  (Before/After)│      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘       │
│         │                 │                 │                 │                 │
│         └─────────────────┴─────────────────┴─────────────────┘                 │
│                           │ React + TypeScript                                      │
│                           ↓                                                         │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        HTTP API (FastAPI)                                       │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐               │
│  │  /api/query     │  │  /api/mutation  │  │  /api/schema    │               │
│  │  - 智能查询      │  │  - 变更预览      │  │  - 表结构查询    │               │
│  │  - 表匹配        │  │  - 执行变更      │  │  - 表搜索        │               │
│  │  - SQL生成       │  │                  │  │                 │               │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘               │
│           │                      │                      │                          │
│           └──────────────────────┴──────────────────────┘                          │
│                           ↓                                                         │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐               │
│  │ SchemaCache     │  │ TableMatcher     │  │ PreferenceLearner│              │
│  │ - 三层缓存       │  │ - 表匹配引擎     │  │ - 用户偏好学习    │              │
│  │ - 智能更新       │  │ - 关系推断       │  │ - 渐进式智能     │              │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘               │
│           │                      │                      │                          │
│           └──────────────────────┴──────────────────────┘                          │
│                           ↓                                                         │
│  ┌──────────────────┐  ┌──────────────────┐                                      │
│  │ LLMClient       │  │ DatabaseManager  │                                      │
│  │ - Qwen API      │  │ - SQL执行        │                                      │
│  │ - SQL生成       │  │ - 事务预览       │                                      │
│  └────────┬─────────┘  └────────┬─────────┘                                      │
│           │                      │                                                  │
│           └──────────────────────┘                                                  │
│                           ↓                                                         │
│                    MySQL 数据库                                                       │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 目录结构

```
mysql-260210/
├── main.py                      # 命令行入口（保留）
├── web_app.py                   # Web 应用入口（新增）
│
├── src/
│   ├── config.py                # 配置
│   ├── db_manager.py            # 数据库管理
│   ├── llm_client.py            # AI 客户端
│   ├── schema_loader.py         # Schema 加载（保留，待迁移）
│   │
│   ├── cache/                   # 新增：缓存模块
│   │   ├── __init__.py
│   │   └── schema_cache.py     # Schema 缓存（三层架构）
│   │
│   ├── matcher/                 # 新增：表匹配模块
│   │   ├── __init__.py
│   │   ├── table_matcher.py    # 表匹配引擎
│   │   └── relation_inferrer.py # 关系推断引擎
│   │
│   ├── learner/                 # 新增：学习模块
│   │   ├── __init__.py
│   │   └── preference_learner.py # 用户偏好学习
│   │
│   ├── preview/                 # 新增：预览模块
│   │   ├── __init__.py
│   │   └── diff_renderer.py    # Before/After 渲染
│   │
│   ├── api/                    # 新增：API 模块
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── query.py       # 查询相关接口
│   │   │   ├── schema.py      # Schema 相关接口
│   │   │   └── mutation.py    # 变更相关接口
│   │   └── models.py          # Pydantic 模型
│   │
│   └── exporter.py             # Excel 导出器
│
├── frontend/                   # 新增：前端项目
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   │
│   ├── src/
│   │   ├── main.tsx            # 入口
│   │   ├── App.tsx             # 主应用
│   │   │
│   │   ├── components/         # 组件
│   │   │   ├── QueryInput.tsx      # 查询输入
│   │   │   ├── TableSelector.tsx   # 表选择器
│   │   │   ├── SqlPreview.tsx      # SQL 预览
│   │   │   ├── DiffTable.tsx        # 变更对比
│   │   │   └── ResultTable.tsx     # 结果表格
│   │   │
│   │   ├── pages/              # 页面
│   │   │   ├── QueryPage.tsx       # 查询页
│   │   │   └── SchemaPage.tsx      # Schema 浏览页
│   │   │
│   │   ├── hooks/              # React Hooks
│   │   │   ├── useQuery.ts         # 查询逻辑
│   │   │   ├── useSchema.ts        # Schema 获取
│   │   │   └── useMutation.ts      # 变更操作
│   │   │
│   │   ├── services/           # API 服务
│   │   │   ├── api.ts              # API 客户端
│   │   │   └── types.ts            # 类型定义
│   │   │
│   │   └── styles/             # 样式
│   │       ├── globals.css
│   │       └── components.css
│   │
│   └── index.html
│
├── data/                       # 新增：数据目录
│   ├── schema_cache.json        # Schema 缓存
│   ├── user_preferences.json    # 用户偏好
│   └── query_history.json     # 查询历史
│
├── output/                     # 导出文件
├── tests/                      # 测试
├── docs/                       # 文档
│   └── plans/2026-02-12-mysql-web-enhancement-design.md
│
├── requirements.txt
├── .env
└── README.md
```

### 4.1 后端架构 (FastAPI)

**web_app.py - 应用入口**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

from src.api.routes import query, schema, mutation
from src.cache.schema_cache import SchemaCache
from src.db_manager import DatabaseManager

app = FastAPI(
    title="MySQL 数据导出工具 Web 版",
    description="基于 AI 的智能数据查询和导出工具",
    version="2.0"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(query.router, prefix="/api/query", tags=["查询"])
app.include_router(schema.router, prefix="/api/schema", tags=["Schema"])
app.include_router(mutation.router, prefix="/api/mutation", tags=["变更"])

# 初始化全局组件
@app.on_event("startup")
async def startup_event():
    """应用启动时初始化"""
    app.state.db = DatabaseManager()
    app.state.schema_cache = SchemaCache(app.state.db)
    app.state.schema_cache.warm_up()  # 预热缓存
    print("✅ 应用启动完成")

# 静态文件服务（前端构建后的文件）
# app.mount("/", StaticFiles(directory="frontend/dist", html_name="index.html"), name="frontend")

if __name__ == "__main__":
    uvicorn.run(
        "web_app:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
```

**API 路由设计**

```python
# src/api/routes/query.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

class QueryRequest(BaseModel):
    natural_language: str
    selected_tables: Optional[list] = None  # 用户已选择的表

class QueryResponse(BaseModel):
    sql: str
    filename: str
    sheet_name: str
    reasoning: str
    needs_interaction: bool  # 是否需要交互
    selected_tables: list    # 选中的表
    suggestions: list        # 候选表建议

@router.post("/analyze", response_model=QueryResponse)
async def analyze_query(request: QueryRequest, app=Depends(get_app)):
    """
    分析自然语言查询

    1. 提取语义实体
    2. 查找候选表
    3. 检查用户偏好记忆
    4. 返回分析结果
    """
    # 提取实体
    entities = EntityExtractor.extract(request.natural_language)

    # 查表（优先用记忆）
    result = app.state.learner.lookup(entities)

    if result and result["confidence"] >= 0.85:
        # 高置信度，直接应用
        return QueryResponse(
            sql=generate_sql(request.natural_language, result["tables"]),
            needs_interaction=False,
            selected_tables=result["tables"],
            suggestions=[]
        )
    else:
        # 需要交互
        candidates = app.state.matcher.match_tables(entities)
        return QueryResponse(
            sql="",  # 等用户确认后再生成
            needs_interaction=True,
            selected_tables=result["tables"] if result else [],
            suggestions=candidates
        )

@router.post("/generate")
async def generate_sql(request: QueryRequest):
    """
    基于用户确认的表生成 SQL
    """
    return {
        "sql": app.state.llm.generate_sql(
            request.natural_language,
            request.selected_tables
        )
    }

@router.post("/execute")
async def execute_query(request: QueryRequest):
    """
    执行查询并导出 Excel
    """
    df = app.state.db.execute_query(request.sql)
    filepath = app.state.exporter.export(df, request.filename)
    return {"filepath": filepath}
```

### 4.2 前端架构 (React + Vite + TypeScript)

**App.tsx - 主应用**

```tsx
import { QueryPage } from './pages/QueryPage';
import './styles/globals.css';

function App() {
  return (
    <div className="app">
      <header className="app-header">
        <h1>🚗 漕河泾停车云数据导出工具 v2.0</h1>
        <p>基于 AI 的智能数据查询</p>
      </header>
      <main className="app-main">
        <QueryPage />
      </main>
    </div>
  );
}

export default App;
```

**QueryPage.tsx - 查询页面**

```tsx
import { useState } from 'react';
import { QueryInput } from '../components/QueryInput';
import { TableSelector } from '../components/TableSelector';
import { SqlPreview } from '../components/SqlPreview';
import { DiffTable } from '../components/DiffTable';
import { ResultTable } from '../components/ResultTable';
import { useQuery } from '../hooks/useQuery';

type Stage = 'input' | 'select_tables' | 'preview_sql' | 'preview_mutation' | 'result';

export const QueryPage: React.FC = () => {
  const [stage, setStage] = useState<Stage>('input');
  const [query, setQuery] = useState('');
  const [selectedTables, setSelectedTables] = useState<string[]>([]);
  const [generatedSql, setGeneratedSql] = useState('');

  const { analyzeQuery, generateSql, executeQuery, isLoading } = useQuery();

  const handleQuerySubmit = async (text: string) => {
    setQuery(text);

    const result = await analyzeQuery(text);

    if (result.needs_interaction) {
      // 需要选择表
      setSelectedTables(result.selected_tables || []);
      setStage('select_tables');
    } else {
      // 直接生成 SQL
      const sqlResult = await generateSql(text, result.selected_tables);
      setGeneratedSql(sqlResult.sql);
      setStage('preview_sql');
    }
  };

  const handleTablesConfirm = async (tables: string[]) => {
    setSelectedTables(tables);
    const sqlResult = await generateSql(query, tables);
    setGeneratedSql(sqlResult.sql);

    // 检查是否是变更操作
    if (sqlResult.intent === 'mutation') {
      setStage('preview_mutation');
    } else {
      setStage('preview_sql');
    }
  };

  const handleSqlConfirm = async () => {
    const result = await executeQuery(generatedSql);
    setStage('result');
  };

  const handleMutationConfirm = async () => {
    // 执行变更
    await executeMutation(generatedSql);
    setStage('result');
  };

  return (
    <div className="query-page">
      {stage === 'input' && (
        <QueryInput
          onSubmit={handleQuerySubmit}
          isLoading={isLoading}
        />
      )}

      {stage === 'select_tables' && (
        <TableSelector
          suggestions={suggestions}
          selected={selectedTables}
          onConfirm={handleTablesConfirm}
        />
      )}

      {stage === 'preview_sql' && (
        <SqlPreview
          sql={generatedSql}
          onConfirm={handleSqlConfirm}
          onBack={() => setStage('input')}
        />
      )}

      {stage === 'preview_mutation' && (
        <DiffTable
          operation="update"
          beforeData={beforeData}
          afterData={afterData}
          onConfirm={handleMutationConfirm}
          onCancel={() => setStage('preview_sql')}
        />
      )}

      {stage === 'result' && (
        <ResultTable
          data={queryResult}
          onNewQuery={() => setStage('input')}
        />
      )}
    </div>
  );
};
```

### 4.3 部署方案

```
┌─────────────────────────────────────────────────────────┐
│                    开发环境                              │
├─────────────────────────────────────────────────────────┤
│  前端：npm run dev (http://localhost:5173)           │
│  后端：python web_app.py (http://localhost:8000)       │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                    生产环境                              │
├─────────────────────────────────────────────────────────┤
│  方式一：分离部署                                         │
│  • 前端：Vercel / Nginx 静态部署                       │
│  • 后端：Gunicorn + Nginx 反向代理                       │
│                                                         │
│  方式二：Docker 容器化                                   │
│  • docker-compose 编排前后端                             │
│  • 数据库外置或容器化                                    │
│                                                         │
│  方式三：一体化部署                                       │
│  • 前端打包后由 FastAPI 静态文件服务                      │
│  • 单一进程，部署简单                                    │
└─────────────────────────────────────────────────────────┘
```

### 4.4 技术栈总结

| 层级 | 技术选择 | 说明 |
|------|---------|------|
| **前端** | React 18 + TypeScript | 组件化、类型安全 |
| | Vite | 快速开发构建 |
| | Tailwind CSS | 样式框架 |
| **后端** | FastAPI | 高性能、自动文档 |
| | SQLAlchemy | ORM、数据库连接池 |
| | Pandas | 数据处理 |
| **AI** | Qwen (通义千问) | SQL 生成 |
| **缓存** | 文件 + 内存 | Schema 缓存、用户偏好 |
| **部署** | Docker / Nginx | 生产环境部署 |

---

## 总结

本设计文档涵盖了从命令行工具升级为 Web 应用的完整方案：

| 部分 | 解决的问题 | 核心方案 |
|------|-----------|---------|
| 1. Schema 智能缓存 | 表多查询慢 | 三层缓存架构、智能更新策略 |
| 2. AI 驱动多表查询 | 字段歧义、不知关联 | 交互式消歧 + 渐进式学习 |
| 3. 变更预览增强 | 只看行数、无具体数据 | Before/After 对比、高亮变化 |
| 4. Web 界面整体 | 命令行不够友好 | FastAPI + React 完整架构 |

**关键创新点：**

1. **渐进式智能** - 首次交互确认，后续自动应用
2. **三层缓存** - 性能与实时性平衡
3. **交互式消歧** - 避免 AI 猜测错误
4. **可视化预览** - 变更操作一目了然

---

设计文档已完成。是否需要我继续生成详细的实现计划？

#### 2.2 表匹配引擎设计

**TableMatcher 类**

```python
class TableMatcher:
    def __init__(self, schema_cache: SchemaCache):
        self.cache = schema_cache
        self.semantic_keywords = {
            "车辆": ["car", "vehicle", "plate", "车牌"],
            "固定车": ["fixed_car", "white_list", "car_white"],
            "园区": ["park", "area", "zone"],
            "人员": ["operator", "user", "admin"],
            "登录": ["login", "operator", "cloud_operator"]
        }

    def match_tables(self, query: str, top_k: int = 5) -> list:
        """
        基于查询匹配相关表

        返回格式：
        [
            {
                "table": "car_white_list",
                "database": "parkcloud",
                "score": 0.95,
                "reasons": ["表名包含 'car'", "描述包含 '固定车'"]
            }
        ]
        """

    def calculate_similarity(self, query: str, table_info: dict) -> float:
        """计算查询与表的相似度分数"""
        # 1. 表名匹配
        # 2. 描述匹配
        # 3. 列名匹配
        # 4. 关键词匹配
        pass
```

#### 2.3 关系推断引擎设计

**RelationInferrer 类**

```python
class RelationInferrer:
    def __init__(self, schema_cache: SchemaCache):
        self.cache = schema_cache

    def infer_relations(self, tables: list) -> dict:
        """
        推断表之间的关联关系

        返回格式：
        {
            "tables": ["car_white_list", "park_info", "cloud_operator"],
            "relations": [
                {
                    "from": "car_white_list.park_id",
                    "to": "park_info.id",
                    "type": "foreign_key"
                },
                {
                    "from": "car_white_list.operator_id",
                    "to": "cloud_operator.id",
                    "type": "foreign_key"
                }
            ],
            "join_paths": [
                ["car_white_list", "park_info", "cloud_operator"]
            ]
        }
        """

    def find_join_path(self, start_table: str, target_tables: list) -> list:
        """找到从起点表到目标表的最优 JOIN 路径"""
```

#### 2.4 增强 Prompt 策略

给 AI 的上下文需要包含：

```
### Schema Information（增强版）
数据库：parkcloud, cloudinterface, ...

## 表关系概览（从缓存推断）
- car_white_list (固定车白名单)
  - park_id → park_info.id (所属园区)
  - operator_id → cloud_operator.id (添加人)
- park_info (园区信息)
  - ...
- cloud_operator (登录人员)
  - ...

## 用户查询意图分析
关键词：["车辆", "固定车", "园区", "添加人"]
候选表：["car_white_list", "park_info", "cloud_operator"]
推荐JOIN路径：car_white_list → park_info, car_white_list → cloud_operator
```

#### 2.5 查询结果展示设计

对于用户查询"查某辆车..."，最终展示：

```
┌─────────────────────────────────────────────────────────┐
│  查询结果：车辆固定车状态及关联信息                     │
├─────────────────────────────────────────────────────────┤
│  使用的表：                                             │
│  ✅ car_white_list (固定车白名单) - parkcloud          │
│  ✅ park_info (园区信息) - parkcloud                   │
│  ✅ cloud_operator (登录人员) - parkcloud              │
├─────────────────────────────────────────────────────────┤
│  生成的 SQL：                                           │
│  SELECT                                                │
│    c.plate AS '车牌号',                                │
│    c.is_fixed AS '是否固定车',                          │
│    p.name AS '所属园区',                                │
│    o.name AS '添加人'                                  │
│  FROM parkcloud.car_white_list c                        │
│  LEFT JOIN parkcloud.park_info p ON c.park_id = p.id    │
│  LEFT JOIN parkcloud.cloud_operator o                  │
│         ON c.operator_id = o.id                         │
│  WHERE c.plate = '沪A12345';                           │
├─────────────────────────────────────────────────────────┤
│  关联关系说明：                                         │
│  • car_white_list 通过 park_id 关联到 park_info        │
│  • car_white_list 通过 operator_id 关联到 operator      │
└─────────────────────────────────────────────────────────┘
```

---

这个部分是否满足你关于多表智能查询的需求？接下来我将展示第三部分：变更预览增强（显示具体的新增/修改/删除数据）。
