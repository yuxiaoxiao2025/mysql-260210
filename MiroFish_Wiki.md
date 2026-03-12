# MiroFish 完整 Wiki 文档

> 基于 GitHub 仓库: [666ghj/MiroFish](https://github.com/666ghj/MiroFish)
> 文档生成日期: 2026-03-12

---

## 目录

1. [项目概述](#项目概述)
2. [系统架构](#系统架构)
3. [核心技术](#核心技术)
4. [五阶段工作流](#五阶段工作流)
5. [后端架构](#后端架构)
6. [前端架构](#前端架构)
7. [安装部署](#安装部署)
8. [API 参考](#api-参考)
9. [核心服务详解](#核心服务详解)
10. [开发指南](#开发指南)

---

## 项目概述

### 简介

**MiroFish** 是一款基于多智能体技术的新一代 AI 预测引擎。通过提取现实世界的种子信息（如突发新闻、政策草案、金融信号），自动构建出高保真的平行数字世界。在此空间内，成千上万个具备独立人格、长期记忆与行为逻辑的智能体进行自由交互与社会演化。

### 核心能力

| 功能 | 描述 | 优势 |
|------|------|------|
| **知识图谱构建** | 使用基于 LLM 的分析从文档中提取实体和关系，通过 Zep Cloud 集成构建全面的图谱 | 为智能体上下文创建结构化的知识表示 |
| **智能体档案生成** | 使用 OASIS 框架生成详细的人设，包含经 LLM 增强的性格特征、目标和行为模式 | 产生具有一致性行为的逼真多智能体模拟 |
| **双平台模拟** | 并行执行 Twitter 和 Reddit 平台的多智能体模拟 | 跨平台验证和比较性洞察 |
| **预测报告生成** | 自动分析模拟结果并生成预测报告 | 可执行的洞察和趋势预测 |
| **交互式探索** | 实时与智能体对话并可视化图谱 | 深度理解模拟动态 |

### 技术栈

**后端:**
- Python 3.11+
- Flask 3.0+
- OpenAI SDK (兼容格式)
- Zep Cloud 3.13.0
- CAMEL-AI / OASIS 0.2.x

**前端:**
- Vue.js 3
- Vite
- JavaScript/TypeScript

**基础设施:**
- Docker
- Docker Compose

---

## 系统架构

### 分层架构

MiroFish 采用严格的**三层架构**，边界清晰：

```
┌─────────────────────────────────────────────────────────────┐
│                    表示层 (前端)                             │
│           Vue.js SPA - 组件化UI、路由、状态管理              │
├─────────────────────────────────────────────────────────────┤
│                    应用层 (后端)                             │
│        Flask REST API - 服务导向的业务逻辑                   │
├─────────────────────────────────────────────────────────────┤
│                   基础设施层 (外部)                          │
│    Zep Cloud (图谱存储) | OASIS (模拟引擎) | LLM APIs        │
└─────────────────────────────────────────────────────────────┘
```

### 系统组件图

```
                    ┌──────────────────┐
                    │   Vue.js 前端    │
                    └────────┬─────────┘
                             │ HTTP/WebSocket
                    ┌────────▼─────────┐
                    │   Flask 后端     │
                    │  ┌──────────────┐│
                    │  │ API Routes   ││
                    │  ├──────────────┤│
                    │  │ Services     ││
                    │  ├──────────────┤│
                    │  │ Models       ││
                    │  └──────────────┘│
                    └────────┬─────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│   Zep Cloud     │ │   OASIS 引擎    │ │   LLM APIs      │
│  (GraphRAG)     │ │  (多智能体)     │ │  (推理/生成)    │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

### 模块化服务设计

每个主要功能都封装在专门的服务类中：

| 服务类 | 职责 |
|--------|------|
| `OntologyGenerator` | 使用 LLM 生成本体模式 |
| `GraphBuilderService` | Zep 图谱构建 |
| `SimulationManager` | OASIS 模拟编排 |
| `SimulationRunner` | 进程管理和操作日志记录 |
| `ReportAgent` | 基于 ReACT 的报告生成 |
| `ZepToolsService` | 图谱检索工具封装 |

---

## 核心技术

### GraphRAG 与知识图谱

MiroFish 利用 **Zep Cloud** 的 GraphRAG 功能，将非结构化文本转换为结构化的知识图谱：

**核心流程:**
1. 文本分块 (Chunking)
2. 实体识别 (Entity Recognition)
3. 关系提取 (Relationship Extraction)
4. 社区检测 (Community Detection)
5. 图谱存储与查询

**优势:**
- 自动从文档中提取知识
- 支持复杂的语义查询
- 保持实体间的关系上下文
- 支持时间维度的知识演化

### OASIS 多智能体模拟

OASIS 是由 CAMEL-AI 团队开发的开源社交媒体模拟框架，MiroFish 以此为核心驱动模拟引擎：

**架构特点:**
```
┌─────────────────────────────────────────────────────────────┐
│                    OASIS 模拟引擎                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  Agent 1    │  │  Agent 2    │  │  Agent N            │  │
│  │  (Twitter)  │  │  (Reddit)   │  │  (Multi-platform)   │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
│         │                │                    │              │
│         └────────────────┼────────────────────┘              │
│                          ▼                                   │
│              ┌─────────────────────┐                         │
│              │   共享环境/时间线   │                          │
│              └─────────────────────┘                         │
└─────────────────────────────────────────────────────────────┘
```

**智能体属性:**
- 独立人格与性格特征
- 长期记忆系统
- 目标驱动行为
- 社交关系网络

### ReACT 模式与 ReportAgent

ReportAgent 采用 **ReACT (Reasoning + Acting)** 模式进行报告生成：

```
思考 (Reasoning) → 行动 (Acting) → 观察 (Observation) → 循环
```

**工具集:**
| 工具 | 功能 |
|------|------|
| `InsightForge` | 深度洞察检索，自动生成子问题并多维度检索 |
| `PanoramaSearch` | 广度搜索，获取全貌包括过期内容 |
| `QuickSearch` | 快速检索 |
| `Interview` | 与模拟中的智能体进行对话 |

---

## 五阶段工作流

MiroFish 的工作流程分为五个清晰的阶段：

### 阶段 1: 图谱构建

**目标:** 将原始文档转换为结构化知识图谱

**流程:**
```
文档上传 → 本体生成 → 文本分块 → Zep处理 → 图谱生成
```

**关键组件:**
- `OntologyGenerator`: 基于文档内容自动生成本体定义
- `GraphBuilderService`: 调用 Zep API 构建图谱
- `TextProcessor`: 文本预处理与分块

### 阶段 2: 环境搭建

**目标:** 为多智能体模拟准备环境

**流程:**
```
实体读取 → 人设生成 → 配置生成 → 环境就绪
```

**关键组件:**
- `ZepEntityReader`: 从图谱读取并过滤实体
- `OasisProfileGenerator`: 生成智能体人格档案
- `SimulationConfigGenerator`: 智能生成模拟参数

### 阶段 3: 开始模拟

**目标:** 执行双平台并行模拟

**流程:**
```
启动模拟 → 双平台并行 → 动态监控 → 模拟完成
```

**关键组件:**
- `SimulationRunner`: 进程管理与执行
- 支持平台: Twitter / Reddit

**模拟状态:**
```python
class SimulationStatus(str, Enum):
    CREATED = "created"
    PREPARING = "preparing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    COMPLETED = "completed"
    FAILED = "failed"
```

### 阶段 4: 报告生成

**目标:** 分析模拟结果并生成预测报告

**流程:**
```
需求解析 → ReACT推理 → 工具调用 → 报告生成
```

**关键组件:**
- `ReportAgent`: 基于 ReACT 模式的报告生成
- `ZepToolsService`: 图谱检索工具

### 阶段 5: 深度互动

**目标:** 与模拟世界进行深度交互

**功能:**
- 与任意智能体对话
- 图谱可视化探索
- 与 ReportAgent 对话

---

## 后端架构

### 目录结构

```
backend/
├── app/
│   ├── __init__.py
│   ├── api/                    # API 路由层
│   │   ├── __init__.py
│   │   ├── graph.py            # 图谱相关 API
│   │   ├── report.py           # 报告相关 API
│   │   └── simulation.py       # 模拟相关 API
│   ├── config.py               # 配置管理
│   ├── models/                 # 数据模型层
│   │   ├── __init__.py
│   │   ├── project.py          # 项目模型
│   │   └── task.py             # 任务模型
│   ├── services/               # 服务层
│   │   ├── __init__.py
│   │   ├── graph_builder.py    # 图谱构建服务
│   │   ├── oasis_profile_generator.py
│   │   ├── ontology_generator.py
│   │   ├── report_agent.py     # 报告生成服务
│   │   ├── simulation_config_generator.py
│   │   ├── simulation_ipc.py
│   │   ├── simulation_manager.py
│   │   ├── simulation_runner.py
│   │   ├── text_processor.py
│   │   ├── zep_entity_reader.py
│   │   ├── zep_graph_memory_updater.py
│   │   └── zep_tools.py        # Zep 工具封装
│   └── utils/                  # 工具层
│       ├── __init__.py
│       ├── file_parser.py
│       ├── llm_client.py
│       ├── logger.py
│       ├── retry.py
│       └── zep_paging.py
├── scripts/                    # 运行脚本
│   ├── action_logger.py
│   ├── run_parallel_simulation.py
│   ├── run_reddit_simulation.py
│   ├── run_twitter_simulation.py
│   └── test_profile_format.py
├── pyproject.toml
├── requirements.txt
├── run.py
└── uv.lock
```

### 依赖管理

```toml
[project]
name = "mirofish-backend"
version = "0.1.0"
requires-python = ">=3.11"

dependencies = [
    # 核心框架
    "flask>=3.0.0",
    "flask-cors>=6.0.0",

    # LLM 相关
    "openai>=1.0.0",

    # Zep Cloud
    "zep-cloud==3.13.0",

    # OASIS 社交媒体模拟
    "camel-oasis==0.2.5",
    "camel-ai==0.2.78",

    # 文件处理
    "PyMuPDF>=1.24.0",
    "charset-normalizer>=3.0.0",
    "chardet>=5.0.0",

    # 工具库
    "python-dotenv>=1.0.0",
    "pydantic>=2.0.0",
]
```

### API 模块组织

| 蓝图 | 路由前缀 | 功能 |
|------|----------|------|
| `graph_bp` | `/api/graph` | 图谱构建和本体管理 |
| `simulation_bp` | `/api/simulation` | OASIS 模拟管理 |
| `report_bp` | `/api/report` | 报告生成与交互 |

---

## 前端架构

### 目录结构

```
frontend/
├── index.html
├── package.json
├── vite.config.js
├── public/
│   └── icon.png
├── src/
│   ├── App.vue                 # 根组件
│   ├── main.js                 # 入口文件
│   ├── api/                    # API 调用层
│   │   ├── graph.js
│   │   ├── index.js
│   │   ├── report.js
│   │   └── simulation.js
│   ├── assets/                 # 静态资源
│   │   └── logo/
│   ├── components/             # 组件
│   │   ├── GraphPanel.vue
│   │   ├── HistoryDatabase.vue
│   │   ├── Step1GraphBuild.vue
│   │   ├── Step2EnvSetup.vue
│   │   ├── Step3Simulation.vue
│   │   ├── Step4Report.vue
│   │   └── Step5Interaction.vue
│   ├── router/                 # 路由配置
│   │   └── index.js
│   ├── store/                  # 状态管理
│   │   └── pendingUpload.js
│   └── views/                  # 页面视图
│       ├── Home.vue
│       ├── InteractionView.vue
│       ├── MainView.vue
│       ├── Process.vue
│       ├── ReportView.vue
│       ├── SimulationRunView.vue
│       └── SimulationView.vue
```

### 组件架构

**核心视图组件:**

| 组件 | 功能 |
|------|------|
| `MainView.vue` | 主工作台，管理五阶段流程 |
| `Home.vue` | 首页/项目列表 |
| `Process.vue` | 流程入口页面 |
| `SimulationView.vue` | 模拟管理视图 |
| `SimulationRunView.vue` | 模拟运行视图 |
| `ReportView.vue` | 报告展示视图 |
| `InteractionView.vue` | 深度交互视图 |

**步骤组件:**

| 组件 | 阶段 |
|------|------|
| `Step1GraphBuild.vue` | 图谱构建 |
| `Step2EnvSetup.vue` | 环境搭建 |
| `Step3Simulation.vue` | 开始模拟 |
| `Step4Report.vue` | 报告生成 |
| `Step5Interaction.vue` | 深度互动 |

**通用组件:**

| 组件 | 功能 |
|------|------|
| `GraphPanel.vue` | 图谱可视化面板 |
| `HistoryDatabase.vue` | 历史记录管理 |

### 状态管理

前端使用简单的响应式状态管理：

```javascript
// store/pendingUpload.js
// 管理待上传文件和模拟需求
export function getPendingUpload()
export function setPendingUpload(files, simulationRequirement)
export function clearPendingUpload()
```

---

## 安装部署

### 前置要求

| 工具 | 版本要求 | 说明 |
|------|----------|------|
| **Node.js** | 18+ | 前端运行环境，包含 npm |
| **Python** | ≥3.11, ≤3.12 | 后端运行环境 |
| **uv** | 最新版 | Python 包管理器 |
| **Docker** | 最新版 | 可选，用于容器化部署 |

### 源码部署

#### 1. 配置环境变量

```bash
# 复制示例配置文件
cp .env.example .env
```

**必需的环境变量:**

```env
# LLM API配置（支持 OpenAI SDK 格式的任意 LLM API）
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL_NAME=qwen-plus

# Zep Cloud 配置
ZEP_API_KEY=your_zep_api_key
```

#### 2. 安装依赖

```bash
# 一键安装所有依赖
npm run setup:all
```

或分步安装：

```bash
# 安装 Node 依赖
npm run setup

# 安装 Python 依赖
npm run setup:backend
```

#### 3. 启动服务

```bash
# 同时启动前后端
npm run dev
```

**服务地址:**
- 前端: `http://localhost:3000`
- 后端 API: `http://localhost:5001`

### Docker 部署

```bash
# 1. 配置环境变量
cp .env.example .env

# 2. 拉取镜像并启动
docker compose up -d
```

端口映射: `3000 (前端) / 5001 (后端)`

---

## API 参考

### 图谱 API (`/api/graph`)

#### 生成本体

```http
POST /api/graph/ontology/generate
Content-Type: multipart/form-data

files: [文件列表]
simulation_requirement: 模拟需求描述
```

**响应:**
```json
{
  "success": true,
  "data": {
    "project_id": "proj_xxx",
    "ontology": {...},
    "status": "ontology_generated"
  }
}
```

#### 构建图谱

```http
POST /api/graph/build
Content-Type: application/json

{
  "project_id": "proj_xxx"
}
```

#### 获取图谱数据

```http
GET /api/graph/data/{graph_id}
```

### 模拟 API (`/api/simulation`)

#### 获取图谱实体

```http
GET /api/simulation/entities/{graph_id}
Query: entity_types, enrich
```

#### 创建模拟

```http
POST /api/simulation/create
Content-Type: application/json

{
  "project_id": "proj_xxx",
  "graph_id": "graph_xxx",
  "enable_twitter": true,
  "enable_reddit": true
}
```

#### 准备模拟

```http
POST /api/simulation/prepare/{simulation_id}
Content-Type: application/json

{
  "simulation_requirement": "预测需求描述",
  "document_text": "原始文档内容",
  "use_llm_for_profiles": true
}
```

#### 启动模拟

```http
POST /api/simulation/start/{simulation_id}
Content-Type: application/json

{
  "max_rounds": 30
}
```

### 报告 API (`/api/report`)

#### 生成报告

```http
POST /api/report/generate
Content-Type: application/json

{
  "project_id": "proj_xxx",
  "graph_id": "graph_xxx",
  "simulation_id": "sim_xxx",
  "report_requirement": "报告需求描述"
}
```

#### 智能体访谈

```http
POST /api/report/interview
Content-Type: application/json

{
  "agent_name": "智能体名称",
  "graph_id": "graph_xxx",
  "question": "访谈问题"
}
```

---

## 核心服务详解

### SimulationManager

**职责:** 管理完整的模拟生命周期

**核心方法:**

```python
class SimulationManager:
    def create_simulation(project_id, graph_id, enable_twitter, enable_reddit)
        """创建新的模拟"""

    def prepare_simulation(simulation_id, simulation_requirement, document_text, ...)
        """准备模拟环境（全程自动化）"""
        # 步骤：
        # 1. 从Zep图谱读取并过滤实体
        # 2. 为每个实体生成OASIS Agent Profile
        # 3. 使用LLM智能生成模拟配置参数
        # 4. 保存配置文件和Profile文件

    def get_simulation(simulation_id)
        """获取模拟状态"""

    def get_profiles(simulation_id, platform)
        """获取模拟的Agent Profile"""

    def get_simulation_config(simulation_id)
        """获取模拟配置"""
```

### GraphBuilderService

**职责:** 构建 Zep 知识图谱

**核心方法:**

```python
class GraphBuilderService:
    def build_graph_async(text, ontology, graph_name, ...)
        """异步构建图谱"""

    def create_graph(name)
        """创建Zep图谱"""

    def set_ontology(graph_id, ontology)
        """设置图谱本体"""

    def add_text_batches(graph_id, chunks, batch_size, ...)
        """分批添加文本到图谱"""

    def get_graph_data(graph_id)
        """获取完整图谱数据"""

    def delete_graph(graph_id)
        """删除图谱"""
```

### ReportAgent

**职责:** 基于 ReACT 模式生成预测报告

**核心功能:**
1. 根据模拟需求和 Zep 图谱信息生成报告
2. 先规划目录结构，然后分段生成
3. 每段采用 ReACT 多轮思考与反思模式
4. 支持与用户对话，在对话中自主调用检索工具

### ZepToolsService

**职责:** 封装图谱检索工具

**核心工具:**

```python
@dataclass
class SearchResult:
    facts: List[str]
    edges: List[Dict[str, Any]]
    nodes: List[Dict[str, Any]]
    query: str
    total_count: int

class ZepToolsService:
    def insight_forge(query, graph_id)
        """深度洞察检索 - 最强大的混合检索"""

    def panorama_search(query, graph_id)
        """广度搜索 - 获取全貌"""

    def quick_search(query, graph_id)
        """快速检索"""

    def interview(agent_name, question, graph_id)
        """与智能体对话"""
```

---

## 开发指南

### 项目初始化

```bash
# 克隆仓库
git clone https://github.com/666ghj/MiroFish.git
cd MiroFish

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API 密钥

# 安装依赖
npm run setup:all

# 启动开发服务器
npm run dev
```

### 常用命令

```bash
# 前端开发
npm run frontend

# 后端开发
npm run backend

# 同时启动
npm run dev

# Docker 部署
docker compose up -d
```

### 代码风格

- **后端:** Python 3.11+, Flask 最佳实践
- **前端:** Vue 3 Composition API
- **类型提示:** 使用 Pydantic 进行数据验证
- **日志:** 使用统一的 logger 模块

### 扩展开发

**添加新的智能体平台:**

1. 在 `SimulationManager` 中添加平台支持
2. 创建对应的 Profile 生成器
3. 在 `scripts/` 目录添加运行脚本

**添加新的检索工具:**

1. 在 `zep_tools.py` 中定义工具方法
2. 更新 `ReportAgent` 的工具列表
3. 在前端添加对应的 UI 入口

---

## 附录

### 相关链接

- **GitHub 仓库:** https://github.com/666ghj/MiroFish
- **在线演示:** https://666ghj.github.io/mirofish-demo/
- **OASIS 框架:** https://github.com/camel-ai/oasis
- **Zep Cloud:** https://app.getzep.com/

### 社区

- **Discord:** https://discord.com/channels/1469200078932545606/1469201282077163739
- **X (Twitter):** https://x.com/mirofish_ai
- **Instagram:** https://www.instagram.com/mirofish_ai/

### 致谢

MiroFish 得到了 **盛大集团** 的战略支持和孵化！

MiroFish 的仿真引擎由 **[OASIS](https://github.com/camel-ai/oasis)** 驱动，感谢 CAMEL-AI 团队的开源贡献！

---

*本文档由 DeepWiki 和 ZRead MCP 工具自动生成*