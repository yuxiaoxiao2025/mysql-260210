# ChromaDB 升级与 Embedding 模型修复方案

**日期:** 2026-03-09
**问题:** ChromaDB 版本不兼容 + Embedding 模型配置错误
**方案:** 升级 ChromaDB 并修复配置

## 问题总结

### 问题 1: ChromaDB 数据库结构不兼容
- **症状:** `sqlite3.OperationalError: no such column: collections.topic`
- **根因:** ChromaDB 0.4.15 与现有数据库结构不兼容
- **影响:** 无法执行 `index schema --force` 命令

### 问题 2: Embedding 模型配置错误
- **症状:** 使用 `text-embedding-v3` 而非设计要求的 `text-embedding-v4`
- **根因:** `embedding_service.py:47` 默认参数设置错误
- **影响:** 向量质量不符合设计要求

## 修复任务

### Task 1: 升级 ChromaDB 到最新稳定版本

**目标:** 升级 ChromaDB 依赖到最新稳定版本

**实施步骤:**
1. 检查 ChromaDB 最新稳定版本
2. 更新 `requirements.txt` 中的版本号
3. 升级依赖: `pip install --upgrade chromadb`
4. 验证升级成功: `python -c "import chromadb; print(chromadb.__version__)"`

**验收标准:**
- ChromaDB 版本 >= 0.5.0
- 能够成功导入 chromadb 模块
- 无依赖冲突

**文件变更:**
- `requirements.txt` - 更新 chromadb 版本

**测试:**
```bash
python -c "import chromadb; print(f'ChromaDB version: {chromadb.__version__}')"
python -c "from chromadb.config import Settings; print('Import successful')"
```

---

### Task 2: 删除旧的 ChromaDB 数据库文件

**目标:** 清理不兼容的旧数据库文件

**实施步骤:**
1. 备份现有数据库（可选，以防需要恢复）
2. 删除 `data/dev/chroma_db/` 目录
3. 删除 `data/prod/chroma_db/` 目录（如果存在）
4. 验证目录已删除

**验收标准:**
- `data/dev/chroma_db/` 目录不存在
- `data/prod/chroma_db/` 目录不存在（如果之前存在）

**注意事项:**
- 警告用户这将删除所有现有的向量索引
- 需要在修复后重新运行 `index schema --force`

---

### Task 3: 修复 Embedding 模型配置

**目标:** 将默认 embedding 模型从 v3 升级到 v4

**实施步骤:**
1. 修改 `src/metadata/embedding_service.py` 第 47 行
2. 将默认参数从 `model: str = "text-embedding-v3"` 改为 `model: str = "text-embedding-v4"`
3. 更新文档字符串中的说明
4. 添加模型版本验证（可选）

**验收标准:**
- `EmbeddingService()` 默认使用 `text-embedding-v4`
- 文档字符串准确反映新的默认值
- 单元测试需要更新（如果有硬编码 v3 的测试）

**文件变更:**
- `src/metadata/embedding_service.py:47` - 修改默认参数
- `src/metadata/embedding_service.py:52` - 更新文档字符串

**代码变更:**
```python
# 修改前
def __init__(self, model: str = "text-embedding-v3", dimension: int = 1024):
    """
    Initialize EmbeddingService.

    Args:
        model: DashScope embedding model name (default: text-embedding-v3)
        dimension: Embedding vector dimension (default: 1024)
    """

# 修改后
def __init__(self, model: str = "text-embedding-v4", dimension: int = 1024):
    """
    Initialize EmbeddingService.

    Args:
        model: DashScope embedding model name (default: text-embedding-v4)
        dimension: Embedding vector dimension (default: 1024)
    """
```

---

### Task 4: 更新相关测试用例

**目标:** 确保测试用例与新的配置一致

**实施步骤:**
1. 查找所有硬编码 `text-embedding-v3` 的测试
2. 更新为 `text-embedding-v4` 或使用默认值
3. 运行测试确保通过

**验收标准:**
- 所有测试通过
- 没有硬编码的旧版本模型名称

**文件变更:**
- `tests/test_llm_client.py` - 如果有相关测试
- `tests/metadata/test_*.py` - 检查 metadata 相关测试

---

### Task 5: 验证修复并重新索引

**目标:** 验证所有修复生效，重新建立索引

**实施步骤:**
1. 运行验证脚本测试 ChromaDB 连接
2. 运行 `index schema --force` 命令
3. 验证索引成功完成
4. 检查日志确认使用 `text-embedding-v4`

**验收标准:**
- `index schema --force` 成功执行
- 日志显示 `model=text-embedding-v4`
- 没有 "no such column" 错误
- 索引数据正常存储

**测试命令:**
```bash
python -c "
from src.metadata.graph_store import GraphStore
from src.metadata.embedding_service import EmbeddingService

# Test GraphStore
store = GraphStore(env='dev')
print(f'GraphStore initialized: {store.get_stats()}')

# Test EmbeddingService
service = EmbeddingService()
print(f'EmbeddingService model: {service.get_model_name()}')
"

# 然后运行
python main.py
# 在 CLI 中执行: index schema --force
```

---

## 风险与缓解

| 风险 | 缓解措施 |
|------|---------|
| ChromaDB 升级引入 breaking changes | 查阅 CHANGELOG，测试基本功能 |
| text-embedding-v4 API 不兼容 | 检查 DashScope API 文档，测试调用 |
| 重新索引耗时过长 | 分批索引，显示进度 |

## 成功标准

- ✅ ChromaDB 版本 >= 0.5.0
- ✅ `index schema --force` 成功执行
- ✅ 日志显示使用 `text-embedding-v4`
- ✅ 所有测试通过
- ✅ 向量索引正常工作
