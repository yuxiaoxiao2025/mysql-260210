# 执行计划：修复 main.py 并提交到新仓库

## 问题分析（Phase 1: Root Cause Investigation）

### 错误信息
```
ModuleNotFoundError: No module named 'src.exporter'
```

### 根本原因
main.py 中导入了以下模块，但本地缺失：
- `src.exporter` - ExcelExporter 类
- `src.schema_loader` - SchemaLoader 类

### 对比分析
GitHub 仓库 `https://github.com/yuxiaoxiao2025/mysql-260210` 包含完整文件：
- ✓ E:\trae-pc\mysql260227_temp\src\exporter.py
- ✓ E:\trae-pc\mysql260227_temp\src\schema_loader.py
- ✓ E:\trae-pc\mysql260227_temp\src\api\ (mutation.py, query.py, schema.py)
- ✓ E:\trae-pc\mysql260227_temp\src\cache\ (schema_cache.py)
- ✓ E:\trae-pc\mysql260227_temp\src\learner\ (preference_learner.py)
- ✓ E:\trae-pc\mysql260227_temp\src\matcher\ (smart_query_engine.py, table_matcher.py)
- ✓ E:\trae-pc\mysql260227_temp\src\preview\ (diff_renderer.py)
- ✓ E:\trae-pc\mysql260227_temp\src\preview_renderer.py
- ✓ E:\trae-pc\mysql260227_temp\src\sql_safety.py
- ✓ E:\trae-pc\mysql260227_temp\src\txn_preview.py
- ✓ E:\trae-pc\mysql260227_temp\tests\ (多个测试文件)

当前项目缺失：
- ✗ src/exporter.py
- ✗ src/schema_loader.py
- ✗ src/api/
- ✗ src/cache/
- ✗ src/learner/
- ✗ src/matcher/
- ✗ src/preview/
- ✗ src/preview_renderer.py
- ✗ src/sql_safety.py
- ✗ src/txn_preview.py
- ✗ tests/test_exporter.py
- ✗ tests/test_integration.py
- ✗ tests/test_main_logic.py
- ✗ tests/test_*.py (其他测试文件)

---

## 执行计划（Phase 4: Implementation）

### 步骤 1: 同步缺失的源代码文件
**目标**: 从临时克隆目录复制所有缺失的源代码文件到项目目录

**操作**:
```bash
# 复制 src/ 目录下所有缺失的文件和目录
Copy-Item -Path "E:\trae-pc\mysql260227_temp\src\exporter.py" -Destination "E:\trae-pc\mysql260227\src\"
Copy-Item -Path "E:\trae-pc\mysql260227_temp\src\schema_loader.py" -Destination "E:\trae-pc\mysql260227\src\"
Copy-Item -Path "E:\trae-pc\mysql260227_temp\src\api" -Recurse -Destination "E:\trae-pc\mysql260227\src\"
Copy-Item -Path "E:\trae-pc\mysql260227_temp\src\cache" -Recurse -Destination "E:\trae-pc\mysql260227\src\"
Copy-Item -Path "E:\trae-pc\mysql260227_temp\src\learner" -Recurse -Destination "E:\trae-pc\mysql260227\src\"
Copy-Item -Path "E:\trae-pc\mysql260227_temp\src\matcher" -Recurse -Destination "E:\trae-pc\mysql260227\src\"
Copy-Item -Path "E:\trae-pc\mysql260227_temp\src\preview" -Recurse -Destination "E:\trae-pc\mysql260227\src\"
Copy-Item -Path "E:\trae-pc\mysql260227_temp\src\preview_renderer.py" -Destination "E:\trae-pc\mysql260227\src\"
Copy-Item -Path "E:\trae-pc\mysql260227_temp\src\sql_safety.py" -Destination "E:\trae-pc\mysql260227\src\"
Copy-Item -Path "E:\trae-pc\mysql260227_temp\src\txn_preview.py" -Destination "E:\trae-pc\mysql260227\src\"
```

**验证**: 检查 src/ 目录下是否包含所有必需文件

---

### 步骤 2: 同步测试文件
**目标**: 复制所有测试文件到 tests/ 目录

**操作**:
```bash
# 复制所有测试文件
Copy-Item -Path "E:\trae-pc\mysql260227_temp\tests\*.py" -Destination "E:\trae-pc\mysql260227\tests\"
```

**验证**: 运行 `pytest --collect-only` 确认所有测试可被收集

---

### 步骤 3: 验证 main.py 可以运行
**目标**: 确认所有导入错误已解决，程序可以正常启动

**操作**:
```bash
cd E:\trae-pc\mysql260227
python main.py
```

**预期结果**:
- 如果 .env 配置正确，程序应显示欢迎界面
- 如果数据库连接失败，应显示连接错误（而非模块导入错误）

**验证标准**:
- ✅ 不出现 `ModuleNotFoundError`
- ✅ 程序能够启动并显示欢迎界面

---

### 步骤 4: 初始化 Git 仓库
**目标**: 将项目纳入版本控制

**操作**:
```bash
cd E:\trae-pc\mysql260227

# 初始化 git 仓库（如果尚未初始化）
if (Test-Path .git) {
    Write-Host "Git 仓库已存在"
} else {
    git init
    Write-Host "Git 仓库初始化完成"
}
```

**验证**: 确认 `.git` 目录存在

---

### 步骤 5: 创建 .gitignore 文件（如果缺失）
**目标**: 确保敏感文件和临时文件不被提交

**操作**:
```bash
# 检查 .gitignore 是否存在
if (-not (Test-Path .gitignore)) {
    Copy-Item -Path "E:\trae-pc\mysql260227_temp\.gitignore" -Destination "E:\trae-pc\mysql260227\.gitignore"
}
```

**验证**: 检查 .gitignore 内容包含：
- `.env`
- `__pycache__/`
- `*.pyc`
- `.coverage`
- `.pytest_cache/`

---

### 步骤 6: 添加所有文件到 Git
**目标**: 将所有项目文件加入版本控制

**操作**:
```bash
git add .
git status
```

**验证**: `git status` 应显示所有已修改/新增的文件

---

### 步骤 7: 创建初始提交
**目标**: 创建项目的第一个 Git 提交

**操作**:
```bash
git commit -m "chore: 同步完整的 MySQL 数据导出工具源代码

- 添加所有缺失的源代码模块（exporter, schema_loader, api, cache, learner, matcher, preview）
- 添加完整的测试套件
- 配置 AGENTS.md 和 .agents/ 项目规范
- 修复 main.py 导入错误"
```

**验证**: `git log` 显示提交记录

---

### 步骤 8: 在 GitHub 创建新仓库
**目标**: 创建远程仓库存储项目

**前提条件**: 需要用户提供以下信息：
- GitHub 用户名
- 新仓库名称（建议：`mysql260227`）
- 是否使用个人访问令牌（PAT）

**操作**:
```bash
# 方法 1: 使用 GitHub CLI（推荐）
gh repo create mysql260227 --public --source=. --remote=origin

# 方法 2: 手动创建后添加远程仓库
# 用户先在 GitHub 网站创建仓库
git remote add origin https://github.com/<username>/mysql260227.git
git remote -v
```

**验证**: `git remote -v` 显示远程仓库地址

---

### 步骤 9: 推送到远程仓库
**目标**: 将本地提交推送到 GitHub

**操作**:
```bash
git push -u origin main
```

**预期结果**:
- 成功推送所有提交
- GitHub 仓库显示完整的项目文件

**验证**: 在 GitHub 网站确认仓库内容

---

### 步骤 10: 清理临时文件
**目标**: 删除临时克隆的目录

**操作**:
```bash
Remove-Item -Recurse -Force "E:\trae-pc\mysql260227_temp"
```

**验证**: 临时目录已删除

---

## 执行顺序总结

| 步骤 | 操作 | 预期时间 | 验证方式 |
|------|------|----------|----------|
| 1 | 复制缺失的源代码文件 | 1 分钟 | 检查 src/ 目录 |
| 2 | 复制测试文件 | 1 分钟 | pytest --collect-only |
| 3 | 验证 main.py 运行 | 1 分钟 | 程序正常启动 |
| 4 | 初始化 Git 仓库 | 0.5 分钟 | 检查 .git 目录 |
| 5 | 创建/更新 .gitignore | 0.5 分钟 | 检查 .gitignore 内容 |
| 6 | 添加文件到 Git | 1 分钟 | git status |
| 7 | 创建初始提交 | 1 分钟 | git log |
| 8 | 创建 GitHub 仓库 | 2 分钟 | git remote -v |
| 9 | 推送到远程 | 2 分钟 | GitHub 网站验证 |
| 10 | 清理临时文件 | 0.5 分钟 | 临时目录已删除 |

**总预计时间**: 约 10-15 分钟

---

## 风险和注意事项

### 风险 1: 数据库连接失败
**原因**: .env 文件配置不正确或数据库服务未启动
**影响**: main.py 可以运行但无法连接数据库
**缓解**: 确保 .env.example 提供了正确的配置模板

### 风险 2: GitHub 认证失败
**原因**: 未配置 SSH 密钥或 PAT 令牌
**影响**: 无法推送到远程仓库
**缓解**: 使用 GitHub CLI 或手动配置认证

### 风险 3: 依赖包缺失
**原因**: requirements.txt 与远程仓库不一致
**影响**: 运行时出现 ImportError
**缓解**: 步骤 3 后运行 `pip install -r requirements.txt`

---

## 完成标准

执行计划完成后，以下标准必须满足：

1. ✅ `python main.py` 可以正常启动，显示欢迎界面
2. ✅ `pytest --collect-only` 显示所有测试可被收集
3. ✅ Git 仓库已初始化并包含所有项目文件
4. ✅ 存在至少一个 Git 提交
5. ✅ 远程仓库已配置并可访问
6. ✅ 代码已成功推送到 GitHub
7. ✅ 临时克隆目录已清理
8. ✅ .gitignore 正确配置，不包含敏感文件

---

## 后续改进建议

1. 添加 GitHub Actions CI/CD 配置
2. 添加项目 README.md 文档
3. 配置代码质量检查（flake8, mypy）
4. 设置依赖项安全扫描
5. 添加开发环境配置文档
