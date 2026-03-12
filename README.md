# 漕河泾停车云数据导出工具

> 智能化的 MySQL 数据库管理工具，支持自然语言交互和业务操作

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)](tests/)

## ✨ 特性

- 🤖 **智能意图识别**: 使用自然语言描述操作，系统自动识别意图
- 📊 **数据导出**: 将查询结果导出为 Excel 文件
- 🔒 **安全操作**: 支持操作预览、事务回滚、SQL 注入防护
- 📈 **监控告警**: 实时监控系统性能，异常自动告警
- 🚗 **业务操作**: 支持停车场相关的业务操作（车牌下发、查询等）
- 🎨 **友好交互**: 清晰的命令行交互界面

## 🚀 快速开始

### 环境要求

- Python 3.8 或更高版本
- MySQL 5.7+ 或 MySQL 8.0+

### 安装

```bash
# 克隆项目
git clone https://github.com/your-repo/mysql260227.git
cd mysql260227

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 配置

```bash
# 复制配置文件
cp .env.example .env

# 编辑配置文件
nano .env
```

配置示例：

```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=parkcloud
```

### 运行

```bash
python main.py
```

## 📖 使用示例

### 基本操作

```bash
# 列出所有表
[MySQL/AI] > list tables

# 查看表结构
[MySQL/AI] > desc cloud_fixed_plate

# 执行 SQL 查询
[MySQL/AI] > SELECT * FROM cloud_fixed_plate LIMIT 10
```

### 智能业务操作

```bash
# 查询车牌信息
[MySQL/AI] > 查询车牌 沪ABC1234

# 下发车牌到场库
[MySQL/AI] > 下发车牌 沪ABC1234 到 国际商务中心

# 批量下发
[MySQL/AI] > 下发车牌 沪ABC1234 到 所有场库

# 更新车牌备注
[MySQL/AI] > 更新车牌 沪ABC1234 的备注为 VIP客户

# 清空车牌备注
[MySQL/AI] > 把沪ABC1234的车辆备注删除掉

# 查看到期车牌
[MySQL/AI] > 查看今天到期的车牌

# 查询绑定关系
[MySQL/AI] > 查一下沪ABC1234都绑定了哪些场库
```

### 获取帮助

```bash
# 查看帮助
[MySQL/AI] > help

# 查看所有可用操作
[MySQL/AI] > operations

# 查看操作详情
[MySQL/AI] > help plate_distribute
```

## 📚 文档

- [用户操作手册](docs/USER_GUIDE.md) - 详细的使用指南
- [故障排除指南](docs/TROUBLESHOOTING.md) - 常见问题和解决方案
- [API 参考文档](docs/API_REFERENCE.md) - 开发者 API 参考
- [部署文档](docs/DEPLOYMENT.md) - 安装和配置指南
- [贡献指南](CONTRIBUTING.md) - 如何参与贡献

## 🏗️ 项目结构

```
mysql260227/
├── src/                    # 源代码
│   ├── api/               # API 接口
│   ├── cache/             # 缓存管理
│   ├── db_manager.py      # 数据库管理
│   ├── executor/          # 操作执行器
│   ├── handlers/          # 错误处理
│   ├── intent/            # 意图识别
│   ├── knowledge/         # 业务知识库
│   ├── learner/           # 学习系统
│   ├── llm_client.py      # LLM 客户端
│   ├── matcher/           # 匹配器
│   ├── monitoring/        # 监控告警
│   ├── preview/           # 预览渲染
│   └── schema_loader.py   # 结构加载
├── tests/                 # 测试文件
├── docs/                  # 文档
│   ├── USER_GUIDE.md
│   ├── TROUBLESHOOTING.md
│   ├── API_REFERENCE.md
│   └── DEPLOYMENT.md
├── logs/                  # 日志文件
├── output/                # 导出文件
├── main.py               # 主程序入口
├── requirements.txt       # 依赖列表
├── .env.example          # 配置示例
├── README.md             # 项目说明
├── CHANGELOG.md          # 变更日志
└── CONTRIBUTING.md       # 贡献指南
```

## 🔍 智能检索管道

本系统采用先进的智能检索管道，通过向量召回 + 两层重排序实现高精度的表/字段匹配。

### 核心特性

| 特性 | 说明 |
|------|------|
| **Embedding v4** | 使用 DashScope text-embedding-v4 模型，支持 query/document 模式 |
| **两层 Rerank** | 表级 + 字段级双重重排序，提升召回精度 |
| **预算控制** | 500ms 总预算，超时自动降级 |
| **语义增强** | 表元数据支持语义描述、标签、置信度 |

### 检索流程

```
用户查询 → 向量召回(Top 50) → 表级 Rerank(Top 10) → 字段级 Rerank(Top 30)
                    ↑                  ↓
               ChromaDB         qwen3-reranker
```

### 组件说明

#### EmbeddingService

支持 text-embedding-v3/v4 模型，提供：

- **query/document 模式**: 查询和文档使用不同的嵌入策略
- **instruction 支持**: 可为查询添加指令提升召回效果
- **批量处理**: 支持批量嵌入，自动重试机制

```python
from src.metadata.embedding_service import EmbeddingService

# 初始化服务（默认 text-embedding-v3）
service = EmbeddingService(model="text-embedding-v4", dimension=1024)

# 生成查询向量（使用 query 模式）
query_embedding = service.embed_text(
    "查询车牌信息",
    text_type="query",
    instruct="为数据库查询场景生成向量"
)

# 生成文档向量（使用 document 模式）
doc_embedding = service.embed_text(
    table_description,
    text_type="document"
)
```

#### RerankService

使用 qwen3-reranker 模型进行相关性重排序：

- **模型**: qwen3-reranker-0.6b
- **API**: OpenAI 兼容的 DashScope API
- **输出**: 按相关性分数排序的结果列表

```python
from src.metadata.rerank_service import RerankService

service = RerankService()
results = service.rerank(
    query="查询车牌",
    candidates=["cloud_fixed_plate: 固定车牌表", "cloud_park: 场库表"],
    top_n=5
)
# results[0].index = 最相关候选项的索引
# results[0].relevance_score = 相关性分数 (0-1)
```

#### RetrievalPipeline

两层检索管道，带预算控制：

- **默认预算**: 500ms
- **降级阈值**: 剩余时间 < 180ms 时跳过字段级 Rerank
- **降级策略**: 使用向量召回结果 + 表级 Rerank 结果

```python
from src.metadata.retrieval_pipeline import RetrievalPipeline

pipeline = RetrievalPipeline(budget_ms=500)
result = pipeline.search("查询车牌信息", top_k=10)

print(result.matches[0].table_name)  # 最相关的表
print(result.metadata["field_rerank_skipped"])  # 是否跳过字段 Rerank
print(result.execution_time_ms)  # 总耗时
```

### 语义增强模板

表元数据支持语义增强字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `semantic_description` | str | 语义描述（业务含义） |
| `semantic_tags` | list[str] | 语义标签 |
| `semantic_source` | str | 来源（comment/rule/llm） |
| `semantic_confidence` | float | 置信度 (0-1) |

语义描述模板：

```
【业务核心语义】
- 所属业务域：车辆管理
- 表业务含义：存储固定车牌信息
- 业务用途：VIP车牌下发、查询、管理

【SQL技术细节】
- 基础属性：parkcloud.cloud_fixed_plate
- 关联属性：关联 cloud_park 场库表
```

### 配置选项

```env
# DashScope API 密钥
DASHSCOPE_API_KEY=your_api_key

# Embedding 模型配置
EMBEDDING_MODEL=text-embedding-v4
EMBEDDING_DIMENSION=1024

# Rerank 配置
RERANK_MODEL=qwen3-reranker-0.6b
RERANK_BUDGET_MS=500
```

### 性能指标

| 指标 | 目标值 |
|------|--------|
| 两层 Rerank 总耗时 | < 500ms |
| 全链路查询 | 1-2 秒 |
| Top-10 命中率 | > 85% |

---

## 🔧 开发

### 运行测试

```bash
# 运行所有测试
pytest

# 运行测试并生成覆盖率报告
pytest --cov=src --cov-report=html
```

### 代码格式化

```bash
# 使用 black 格式化代码
black src/ tests/

# 使用 isort 排序导入
isort src/ tests/
```

## ⚠️ 重要变更

### DialogueEngine已废弃

DialogueEngine已被废弃，功能已整合到多智能体架构。请参考 [迁移指南](docs/migration/dialogue-engine-to-orchestrator.md) 更新你的代码。

**主要变更:**
- 概念学习 → `IntentAgent`
- 对话流程管理 → `Orchestrator`
- 流式输出 → `KnowledgeAgent`

---

## 🤝 贡献

欢迎贡献代码、报告问题或提出建议！请查看 [贡献指南](CONTRIBUTING.md) 了解详情。

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 📮 联系方式

- 问题反馈：[提交 Issue](https://github.com/your-repo/mysql260227/issues)
- 功能建议：[提交 Feature Request](https://github.com/your-repo/mysql260227/issues)

## 🙏 致谢

感谢所有为本项目做出贡献的开发者！

---

**当前版本**: 3.1.0
**最后更新**: 2026-03-09
