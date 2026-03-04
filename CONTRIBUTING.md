# 贡献指南

感谢您对漕河泾停车云数据导出工具的关注！我们欢迎任何形式的贡献。

## 目录

1. [如何贡献](#如何贡献)
2. [开发环境设置](#开发环境设置)
3. [代码规范](#代码规范)
4. [提交指南](#提交指南)
5. [测试指南](#测试指南)
6. [文档编写](#文档编写)
7. [问题报告](#问题报告)
8. [功能请求](#功能请求)

---

## 如何贡献

### 贡献方式

1. **报告 Bug**: 发现问题请报告
2. **提出建议**: 有改进想法欢迎提出
3. **提交代码**: 修复 Bug 或添加新功能
4. **完善文档**: 改进文档质量和准确性
5. **分享经验**: 分享使用经验和最佳实践

### 贡献流程

```
┌─────────────────┐
│  Fork 项目      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  创建分支       │
│  git checkout   │
│  -b feature/   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  开发功能       │
│  编写代码       │
│  编写测试       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  提交更改       │
│  git commit    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  推送到 Fork   │
│  git push     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  创建 Pull      │
│  Request       │
└─────────────────┘
```

---

## 开发环境设置

### 1. 克隆项目

```bash
# Fork 项目到您的 GitHub 账户

# 克隆您的 Fork
git clone https://github.com/your-username/mysql260227.git
cd mysql260227

# 添加上游仓库
git remote add upstream https://github.com/original-owner/mysql260227.git
```

### 2. 创建虚拟环境

```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
# Linux/Mac
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. 安装开发依赖

```bash
# 安装项目依赖
pip install -r requirements.txt

# 安装开发依赖
pip install -r requirements-dev.txt  # 如果有的话

# 安装测试依赖
pip install pytest pytest-cov pytest-mock
```

### 4. 配置开发环境

```bash
# 复制配置文件
cp .env.example .env

# 编辑配置文件
nano .env
```

### 5. 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_db_manager.py

# 运行测试并生成覆盖率报告
pytest --cov=src --cov-report=html

# 查看覆盖率报告
# 打开 htmlcov/index.html
```

### 6. 代码检查

```bash
# 使用 pylint 检查代码质量
pylint src/

# 使用 black 格式化代码
black src/

# 使用 isort 排序导入
isort src/
```

---

## 代码规范

### Python 代码风格

我们遵循 [PEP 8](https://pep8.org/) 代码风格指南。

#### 基本规范

```python
# ✅ 正确：使用 4 空格缩进
def my_function():
    if condition:
        do_something()

# ❌ 错误：使用 Tab 缩进
def my_function():
	if condition:
		do_something()
```

```python
# ✅ 正确：行长度不超过 88 字符
long_variable_name = some_function_with_long_name(
    argument1, argument2, argument3
)

# ❌ 错误：行长度超过 88 字符
long_variable_name = some_function_with_long_name(argument1, argument2, argument3)
```

#### 命名规范

```python
# ✅ 正确：使用下划线命名法
class_name = "MyClass"
function_name = "my_function"
variable_name = "my_variable"
CONSTANT_NAME = "MY_CONSTANT"

# ❌ 错误：使用驼峰命名法
className = "MyClass"
functionName = "myFunction"
```

#### 文档字符串

```python
# ✅ 正确：使用 Google 风格的文档字符串
def my_function(param1, param2):
    """
    函数简短描述

    函数详细描述，可以跨多行。

    Args:
        param1: 参数1的描述
        param2: 参数2的描述

    Returns:
        返回值描述

    Raises:
        ValueError: 当参数无效时抛出

    Example:
        >>> my_function("value1", "value2")
        "result"
    """
    pass

# ❌ 错误：没有文档字符串
def my_function(param1, param2):
    pass
```

### 类型注解

推荐使用类型注解提升代码可读性：

```python
from typing import Optional, List, Dict, Any

def my_function(
    param1: str,
    param2: Optional[int] = None
) -> Dict[str, Any]:
    """
    函数描述

    Args:
        param1: 字符串参数
        param2: 可选整数参数

    Returns:
        字典返回值
    """
    return {"key": "value"}
```

### 错误处理

```python
# ✅ 正确：捕获特定异常
try:
    result = risky_operation()
except SpecificError as e:
    logger.error(f"操作失败: {e}")
    raise

# ❌ 错误：捕获所有异常
try:
    result = risky_operation()
except:
    pass
```

### 日志记录

```python
# ✅ 正确：使用结构化日志
logger.info({
    "event": "operation",
    "operation_id": "test",
    "success": True
})

# ✅ 正确：使用不同日志级别
logger.debug("调试信息")
logger.info("常规信息")
logger.warning("警告信息")
logger.error("错误信息")
logger.critical("严重错误")

# ❌ 错误：使用 print
print("This is a log message")
```

---

## 提交指南

### Commit 消息格式

遵循 [Conventional Commits](https://www.conventionalcommits.org/zh-hans/) 规范：

```
<类型>(<范围>): <描述>

[可选的正文]

[可选的脚注]
```

#### 类型

- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档变更
- `style`: 代码格式（不影响功能）
- `refactor`: 重构（既不是新功能也不是修复）
- `perf`: 性能优化
- `test`: 测试相关
- `chore`: 构建/工具相关
- `ci`: CI/CD 相关

#### 示例

```bash
# 新功能
git commit -m "feat(monitoring): 添加告警管理系统"

# Bug 修复
git commit -m "fix(db): 修复 execute_update 方法缺失问题"

# 文档更新
git commit -m "docs: 更新用户操作手册"

# 重构
git commit -m "refactor(executor): 简化操作执行逻辑"
```

### Commit 最佳实践

```bash
# ✅ 正确：清晰描述变更
git commit -m "fix: 修复车牌号正则表达式匹配问题"

# ✅ 正确：包含详细说明
git commit -m "feat: 添加批量下发功能

支持一次性下发车牌到多个场库，提升操作效率。
- 添加 batch_distribute 操作模板
- 优化数据库事务处理
- 添加批量操作测试"

# ❌ 错误：模糊的描述
git commit -m "update code"

# ❌ 错误：一次提交包含多个不相关的变更
git commit -m "fix bugs and add features"
```

### 分支命名

```
feature/功能描述
fix/问题描述
docs/文档更新
refactor/重构说明
test/测试相关
```

示例：

```bash
git checkout -b feature/alert-system
git checkout -b fix/sql-injection
git checkout -b docs/user-guide
```

---

## 测试指南

### 测试要求

- 单元测试覆盖率：≥ 80%
- 所有新功能必须有测试
- 所有 Bug 修复必须有回归测试

### 测试文件位置

```
tests/
├── test_db_manager.py
├── test_operation_executor.py
├── test_intent_recognizer.py
├── test_knowledge_loader.py
├── test_monitoring.py
└── ...
```

### 编写测试

```python
import pytest
from unittest.mock import Mock, patch
from src.db_manager import DatabaseManager

class TestDatabaseManager:
    """数据库管理器测试"""

    def test_init_db_manager(self):
        """测试初始化数据库管理器"""
        db = DatabaseManager()
        assert db.db_url is not None

    def test_execute_query(self):
        """测试执行查询"""
        # 使用 Mock 避免真实数据库连接
        with patch.object(DatabaseManager, 'get_connection'):
            db = DatabaseManager()
            # 测试代码
            pass

    def test_execute_query_with_params(self):
        """测试使用参数执行查询"""
        db = DatabaseManager()
        result = db.execute_query(
            "SELECT * FROM table WHERE id = :id",
            params={"id": 1}
        )
        assert result is not None

    @pytest.mark.parametrize("input,expected", [
        ("沪A12345", True),
        ("A12345", False),
        ("沪12345", False),
    ])
    def test_plate_format(self, input, expected):
        """测试车牌格式验证"""
        result = is_valid_plate(input)
        assert result == expected
```

### 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_db_manager.py

# 运行特定测试函数
pytest tests/test_db_manager.py::TestDatabaseManager::test_init_db_manager

# 运行测试并显示详细输出
pytest -v

# 运行测试并停止在第一个失败
pytest -x

# 运行测试并显示覆盖率
pytest --cov=src --cov-report=html

# 运行慢速测试
pytest -m slow
```

---

## 文档编写

### 文档要求

- 使用 Markdown 格式
- 包含代码示例
- 提供清晰的步骤说明
- 使用中文编写（本项目要求）

### 文档位置

```
docs/
├── USER_GUIDE.md          # 用户操作手册
├── TROUBLESHOOTING.md     # 故障排除指南
├── API_REFERENCE.md       # API 参考文档
├── DEPLOYMENT.md         # 部署文档
└── ...
```

### 文档模板

```markdown
# 文档标题

## 简介

简要描述文档内容。

## 安装

### 前置要求

- 要求1
- 要求2

### 安装步骤

1. 步骤1
2. 步骤2

## 使用

### 基本用法

代码示例：

```python
# 代码示例
def example():
    pass
```

### 高级用法

## 故障排除

### 常见问题

**问题**: 描述问题

**解决方案**: 描述解决方案

## 参考资料

- [参考1](链接)
- [参考2](链接)
```

---

## 问题报告

### 报告 Bug

报告 Bug 时请包含以下信息：

1. **问题描述**
   - 清晰描述遇到的问题
   - 预期行为
   - 实际行为

2. **复现步骤**
   ```
   1. 步骤1
   2. 步骤2
   3. 步骤3
   ```

3. **环境信息**
   - 操作系统版本
   - Python 版本
   - 依赖版本
   - 配置信息（隐藏敏感信息）

4. **错误日志**
   ```python
   # 相关的错误日志
   ```

5. **截图（如果适用）**

### Bug 报告模板

```markdown
**问题描述**
[清晰描述问题]

**复现步骤**
1.
2.
3.

**预期行为**
[描述预期的行为]

**实际行为**
[描述实际的行为]

**环境信息**
- OS: [例如: Ubuntu 20.04]
- Python: [例如: 3.10.0]
- Version: [例如: 3.0.0]

**错误日志**
[粘贴相关日志]
```

---

## 功能请求

### 提出功能建议

提出新功能时请包含：

1. **功能描述**
   - 清晰描述功能需求
   - 使用场景
   - 预期效果

2. **设计方案**（可选）
   - 技术方案
   - 实现难点
   - 替代方案

3. **示例**（可选）
   - 使用示例
   - 界面设计（如果有 UI）

### 功能请求模板

```markdown
**功能描述**
[清晰描述功能需求]

**使用场景**
[描述使用场景]

**预期效果**
[描述预期的效果]

**设计方案（可选）**
[描述技术方案]

**示例（可选）**
[提供使用示例]
```

---

## 行为准则

### 社区准则

1. **尊重他人**
   - 尊重不同的观点和经验
   - 友善和包容

2. **建设性讨论**
   - 关注问题本身，不对人
   - 提供有帮助的反馈

3. **协作精神**
   - 乐于助人
   - 分享知识
   - 接受反馈

### 代码审查准则

1. **审查重点**
   - 代码正确性
   - 代码风格
   - 测试覆盖
   - 文档完整性

2. **审查态度**
   - 建设性反馈
   - 提出改进建议
   - 认可优秀的工作

---

## 获取帮助

如果您在贡献过程中遇到问题：

- 📖 查看文档
- 💬 参与讨论
- 📧 联系维护者

---

## 许可证

通过贡献代码，您同意您的贡献将根据项目的许可证进行许可。

---

**文档版本**: 1.0
**最后更新**: 2026-03-04
