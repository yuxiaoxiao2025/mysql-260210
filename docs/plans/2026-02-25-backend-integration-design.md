# 后端集成设计文档

## 概述

本文档描述 MySQL 数据导出工具 Web 增强的后端集成设计方案，将现有的业务组件连接到 FastAPI 路由，实现完整功能。

## 设计目标

1. **完整集成**：将 LLMClient、DatabaseManager、SchemaCache、SmartQueryEngine 等组件连接到 API
2. **智能推荐**：实现交互式表消歧和记忆学习
3. **安全可靠**：变更操作必须预览确认，危险操作拦截
4. **单一入口**：前端静态文件由 FastAPI 服务，统一访问地址

---

## 第一部分：整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                     前端 (React + Vite)                         │
│                    http://localhost:3000                        │
└──────────────────────────┬──────────────────────────────────────┘
                           │ API 请求
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI 后端                                  │
│                    http://127.0.0.1:8000                         │
├─────────────────────────────────────────────────────────────────┤
│  src/api/deps.py (依赖注入模块)                                  │
│  ├── get_db() → DatabaseManager                                 │
│  ├── get_llm() → LLMClient                                      │
│  ├── get_cache() → SchemaCache                                  │
│  ├── get_matcher() → TableMatcher                               │
│  ├── get_learner() → PreferenceLearner                          │
│  └── get_query_engine() → SmartQueryEngine                      │
├─────────────────────────────────────────────────────────────────┤
│  src/api/routes/                                                 │
│  ├── query.py    → /api/query/*    (智能查询)                    │
│  ├── schema.py   → /api/schema/*   (Schema管理)                  │
│  └── mutation.py → /api/mutation/* (变更预览/执行)               │
└──────────────────────────┬──────────────────────────────────────┘
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    ┌──────────┐    ┌──────────┐    ┌──────────┐
    │ Database │    │ DashScope│    │ 文件系统  │
    │  MySQL   │    │  LLM API │    │ (缓存等)  │
    └──────────┘    └──────────┘    └──────────┘
```

---

## 第二部分：API 接口设计

### 2.1 智能查询 API (`/api/query`)

| 接口 | 方法 | 功能 | 输入 | 输出 |
|------|------|------|------|------|
| `/analyze` | POST | 分析自然语言，返回表推荐 | `{query: string}` | `{needs_interaction, selected_tables, suggestions}` |
| `/confirm` | POST | 确认表选择，生成 SQL | `{query, selected_tables}` | `{sql, reasoning, intent}` |
| `/execute` | POST | 执行 SELECT 查询 | `{sql}` | `{data, row_count}` |

### 2.2 Schema 管理 API (`/api/schema`)

| 接口 | 方法 | 功能 | 输入 | 输出 |
|------|------|------|------|------|
| `/tables` | GET | 获取所有表列表 | 无 | `{tables: string[]}` |
| `/table/{name}` | GET | 获取单个表详情 | 表名 | `{name, columns, foreign_keys}` |
| `/search` | GET | 搜索表 | `?keyword=xxx` | `{tables: [...]}` |
| `/refresh` | POST | 刷新缓存 | `{table_name?: string}` | `{success: bool}` |

### 2.3 变更预览 API (`/api/mutation`)

| 接口 | 方法 | 功能 | 输入 | 输出 |
|------|------|------|------|------|
| `/preview` | POST | 预览变更（不提交） | `{sql, preview_sql, key_columns}` | `{before, after, diff_summary}` |
| `/execute` | POST | 执行变更（提交） | `{sql, preview_sql, key_columns}` | `{success, summary}` |

---

## 第三部分：多表/未知表处理流程

### 场景 1：首次查询（无记忆）

```
用户输入 → SmartQueryEngine 分析 → 返回候选表 → 用户确认 → 记录偏好 → 生成 SQL
```

返回示例：
```json
{
  "needs_interaction": true,
  "reason": "🔍 发现了多个可能的表，请选择",
  "suggestions": [
    {"table": "car_white_list", "recommended": true, "description": "固定车白名单", "score": 0.95},
    {"table": "park_info", "recommended": true, "description": "园区信息", "score": 0.92}
  ]
}
```

### 场景 2：有记忆（高置信度）

```
用户输入 → SmartQueryEngine 查找记忆 → 高置信度 → 直接生成 SQL（无需交互）
```

返回示例：
```json
{
  "needs_interaction": false,
  "selected_tables": ["car_white_list"],
  "reason": "🎯 已记忆，置信度: 95%"
}
```

### 场景 3：部分记忆

```
用户输入 → 部分实体有记忆 → 已记忆的自动应用 → 未记忆的需要确认
```

---

## 第四部分：智能推荐机制

### 推荐来源

| 组件 | 功能 |
|------|------|
| TableMatcher | 基于关键词匹配计算表相关性评分 |
| SchemaCache | 提供表的字段、注释、外键信息 |
| PreferenceLearner | 记忆用户历史选择，提升推荐准确度 |

### 推荐展示

1. **匹配度评分**：显示 0-100% 的相关性分数
2. **推荐标记**：高分表标记为"推荐"
3. **表详情预览**：点击查看字段列表和描述
4. **推荐理由**：解释为什么推荐这个表

---

## 第五部分：数据流设计

### 查询完整流程

```
用户输入
    ↓
① POST /api/query/analyze
    ↓
② SmartQueryEngine.process_query()
    ↓
③ 需要交互？
    ├── 是 → 返回候选表 → 用户确认 → ④
    └── 否 → 直接进入 ④
    ↓
④ 记录偏好 PreferenceLearner.learn()
    ↓
⑤ LLMClient.generate_sql() 生成 SQL
    ↓
⑥ 操作类型？
    ├── SELECT → 执行查询 → 返回数据
    └── INSERT/UPDATE/DELETE → 预览 → 用户确认 → 执行
```

---

## 第六部分：部署方案

### 当前状态 → 目标状态

| 项目 | 当前 | 目标 |
|------|------|------|
| 前端 | Vite 开发服务器 (localhost:3000) | 静态文件 (FastAPI 服务) |
| 后端 | FastAPI (127.0.0.1:8000) | 同左，同时服务前端 |
| 访问方式 | 两个地址 | **单一地址**: http://127.0.0.1:8000 |

### 部署步骤

1. **前端构建**：`npm run build` 生成 `frontend/dist/`
2. **修改 web_app.py**：添加静态文件服务
3. **启动服务**：`uvicorn web_app:app --host 0.0.0.0 --port 8000`

---

## 第七部分：错误处理与安全性

### 错误处理

| 错误类型 | 用户提示 | 处理方式 |
|---------|---------|---------|
| LLM API 失败 | "AI 服务暂时不可用，请稍后重试" | 记录日志，返回友好提示 |
| 数据库连接失败 | "数据库连接失败，请联系管理员" | 记录日志，检查配置 |
| SQL 执行错误 | "查询执行失败：表不存在" | 返回具体错误原因 |
| 表匹配无结果 | "没有找到相关的表，请尝试其他描述" | 建议提供更多信息 |

### SQL 安全规则

| 规则 | 说明 |
|------|------|
| 禁止危险操作 | DROP, TRUNCATE, ALTER TABLE 直接拒绝 |
| 强制 WHERE 条件 | DELETE/UPDATE 无 WHERE 条件拒绝 |
| 行数警告 | 影响 >100 行时显示警告 |
| 强制预览确认 | 所有变更操作必须预览后确认 |

---

## 实施范围

### 需要新建的文件

| 文件 | 说明 |
|------|------|
| `src/api/deps.py` | 依赖注入模块 |

### 需要修改的文件

| 文件 | 修改内容 |
|------|---------|
| `src/api/routes/query.py` | 连接 SmartQueryEngine + LLMClient |
| `src/api/routes/schema.py` | 连接 SchemaCache + DatabaseManager |
| `src/api/routes/mutation.py` | 连接 DiffRenderer + DatabaseManager |
| `web_app.py` | 添加静态文件服务 |
| `frontend/` | 构建生成 dist 目录 |

### 已完成无需修改的文件

- `src/llm_client.py` ✅
- `src/db_manager.py` ✅
- `src/config.py` ✅
- `src/cache/schema_cache.py` ✅
- `src/matcher/table_matcher.py` ✅
- `src/matcher/smart_query_engine.py` ✅
- `src/learner/preference_learner.py` ✅
- `src/preview/diff_renderer.py` ✅
- `.env` ✅

---

## 预期成果

实施完成后：
1. 访问 http://127.0.0.1:8000 可使用完整应用
2. 输入自然语言 → 系统智能匹配表 → LLM 生成 SQL → 执行返回结果
3. 变更操作必须预览确认
4. 系统记住用户偏好，越用越智能
