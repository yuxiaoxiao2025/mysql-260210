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

**当前版本**: 3.0.0
**最后更新**: 2026-03-04
