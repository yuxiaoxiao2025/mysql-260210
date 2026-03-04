# 漕河泾停车云数据导出工具 - 用户操作手册

## 目录

1. [简介](#简介)
2. [快速开始](#快速开始)
3. [基本操作](#基本操作)
4. [智能业务操作](#智能业务操作)
5. [命令参考](#命令参考)
6. [故障排除](#故障排除)
7. [常见问题](#常见问题)

---

## 简介

漕河泾停车云数据导出工具是一个智能化的 MySQL 数据库管理工具，支持：

- 🤖 **智能意图识别**：使用自然语言描述操作，系统自动识别意图
- 📊 **数据导出**：将查询结果导出为 Excel 文件
- 🔒 **安全操作**：支持操作预览、事务回滚、SQL 注入防护
- 📈 **监控告警**：实时监控系统性能，异常自动告警
- 🚗 **业务操作**：支持停车场相关的业务操作（车牌下发、查询等）

---

## 快速开始

### 1. 环境准备

确保已安装 Python 3.8+ 和必要的依赖：

```bash
pip install -r requirements.txt
```

### 2. 配置数据库连接

复制 `.env.example` 为 `.env` 并配置数据库连接信息：

```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=parkcloud
```

### 3. 启动程序

```bash
python main.py
```

启动后，您将看到欢迎界面：

```
============================================================
🚗 漕河泾停车云数据导出工具 v3.0 (AI Enhanced + Smart Operations)
============================================================
✨ 新功能：智能业务操作
  现在可以直接使用业务语言，系统会自动识别并执行操作：
  '下发车牌 沪ABC1234 到 国际商务中心'
  '查询车牌 沪A12345'
  '查看30天内到期的车牌'
------------------------------------------------------------
📝 命令列表：
  list tables       - 列出所有表
  desc <table>      - 查看表结构
  help [operation]  - 查看帮助或操作详情
  operations        - 列出所有可用操作
  exit / quit       - 退出程序
------------------------------------------------------------
💡 也可以直接输入自然语言或 SQL 语句
============================================================
```

---

## 基本操作

### 列出所有表

```
[MySQL/AI] > list tables
```

### 查看表结构

```
[MySQL/AI] > desc cloud_fixed_plate
```

输出示例：

```
📋 表 cloud_fixed_plate 结构：
字段名              类型            注释
--------------------------------------------------
plate               varchar(20)     车牌号
name                varchar(50)     车主姓名
phone               varchar(20)     联系电话
memo                varchar(200)     备注
create_time         datetime         创建时间
```

### 执行 SQL 查询

```
[MySQL/AI] > SELECT * FROM cloud_fixed_plate LIMIT 10
```

系统会：
1. 显示生成的 SQL
2. 显示思考过程
3. 询问是否执行
4. 将结果导出为 Excel 文件

---

## 智能业务操作

### 查看可用操作

```
[MySQL/AI] > operations
```

### 车牌相关操作

#### 查询车牌信息

```
[MySQL/AI] > 查询车牌 沪ABC1234
```

或者：

```
[MySQL/AI] > 查一下沪ABC1234的信息
```

#### 下发车牌到场库

```
[MySQL/AI] > 下发车牌 沪ABC1234 到 国际商务中心
```

或者：

```
[MySQL/AI] > 把沪ABC1234下发到田林园
```

#### 批量下发到场库

```
[MySQL/AI] > 下发车牌 沪ABC1234 到 所有场库
```

或者：

```
[MySQL/AI] > 下发车牌 沪ABC1234 到全部
```

#### 更新车牌备注

```
[MySQL/AI] > 更新车牌 沪ABC1234 的备注为 测试车辆
```

#### 清空车牌备注

```
[MySQL/AI] > 把沪ABC1234的车辆备注删除掉
```

或者：

```
[MySQL/AI] > 清空沪ABC1234的备注
```

### 查询类操作

#### 查看到期车牌

```
[MySQL/AI] > 查看今天到期的车牌
```

或者：

```
[MySQL/AI] > 查看30天内到期的车牌
```

#### 查询绑定关系

```
[MySQL/AI] > 查一下沪ABC1234都绑定了哪些场库
```

### 自然语言查询

如果不知道具体操作名称，可以直接用自然语言描述需求：

```
[MySQL/AI] > 我想查询上海地区的所有车牌
```

系统会自动：
1. 识别操作意图
2. 提取所需参数
3. 如果缺少参数，会提示您输入
4. 生成预览
5. 等待确认后执行

---

## 命令参考

### 内置命令

| 命令 | 说明 | 示例 |
|------|------|------|
| `list tables` | 列出所有数据库表 | `list tables` |
| `desc <table>` | 查看表结构 | `desc cloud_fixed_plate` |
| `help` | 显示帮助信息 | `help` |
| `help <operation>` | 查看操作详情 | `help plate_distribute` |
| `operations` | 列出所有可用操作 | `operations` |
| `exit` / `quit` | 退出程序 | `exit` |

### 车牌操作模板

#### plate_query - 查询车牌信息

**描述**：根据车牌号查询车牌基本信息

**参数**：
- `plate` (必需)：车牌号，格式如 沪A12345

**示例**：
```
查询车牌 沪ABC1234
```

#### plate_distribute - 下发车牌到场库

**描述**：将车牌下发到指定场库

**参数**：
- `plate` (必需)：车牌号
- `park_name` (必需)：场库名称（可用 `全部` 下发到所有场库）

**示例**：
```
下发车牌 沪ABC1234 到 国际商务中心
下发车牌 沪ABC1234 到全部
```

#### plate_update_memo - 更新车牌备注

**描述**：更新或清空车牌备注信息

**参数**：
- `plate` (必需)：车牌号
- `memo` (可选)：备注内容，不提供则清空备注

**示例**：
```
更新车牌 沪ABC1234 的备注为 测试车辆
把沪ABC1234的车辆备注删除掉
```

#### plate_query_expiring - 查询到期车牌

**描述**：查询指定天数内到期的车牌

**参数**：
- `days` (可选)：天数范围，默认 30 天

**示例**：
```
查看今天到期的车牌
查看30天内到期的车牌
```

#### plate_park_bindings - 查询绑定关系

**描述**：查询车牌绑定的场库列表

**参数**：
- `plate` (必需)：车牌号

**示例**：
```
查一下沪ABC1234都绑定了哪些场库
```

---

## 故障排除

### 问题 1：数据库连接失败

**症状**：
```
❌ 初始化失败: Can't connect to MySQL server
```

**解决方案**：

1. 检查 `.env` 文件中的数据库配置
2. 确认数据库服务正在运行
3. 检查网络连接
4. 验证用户名和密码

```env
# 检查这些配置是否正确
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=parkcloud
```

### 问题 2：操作执行失败

**症状**：
```
❌ 执行失败: 参数 plate 格式不正确
```

**解决方案**：

1. 检查车牌号格式：`[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼][A-Z][A-Z0-9]{5,6}`
2. 例如：沪A12345、京B67890

### 问题 3：意图识别失败

**症状**：
```
🔄 未匹配到操作模板，使用 LLM 生成 SQL
```

**解决方案**：

1. 使用更清晰的描述
2. 参考 [命令参考](#命令参考) 中的操作模板
3. 使用 `operations` 命令查看所有可用操作

### 问题 4：导出文件失败

**症状**：
```
❌ 导出失败: Permission denied
```

**解决方案**：

1. 检查 `output` 目录是否存在且可写
2. 确保有足够的磁盘空间
3. 检查文件名是否包含特殊字符

### 问题 5：查询结果为空

**症状**：
```
⚠️ 查询结果为空，未生成文件。
```

**解决方案**：

1. 确认查询条件是否正确
2. 检查数据库中是否有匹配的数据
3. 尝试使用更宽泛的查询条件

---

## 常见问题

### Q: 如何批量操作多个车牌？

A: 当前版本需要逐个操作。如需批量操作，可以使用 SQL 语句：

```sql
-- 批量更新备注
UPDATE cloud_fixed_plate SET memo = 'VIP客户' WHERE plate IN ('沪A12345', '沪B67890');
```

### Q: 操作可以撤销吗？

A: 是的，所有变更操作都支持预览模式。在执行前会显示预览，确认后才会执行。如需回滚，请联系数据库管理员。

### Q: 如何查看操作历史？

A: 操作历史记录在日志文件中：

```
logs/operation.log        # 操作日志
logs/mysql_ai.log        # 主日志
logs/operation_error.log # 错误日志
```

### Q: 支持哪些数据库？

A: 当前版本支持 MySQL 5.7+ 和 MySQL 8.0+。

### Q: 如何配置告警？

A: 告警配置在 `main.py` 中的监控系统初始化部分：

```python
alert_manager = AlertManager(
    metrics_collector=metrics_collector,
    error_rate_threshold=0.1,  # 10% 错误率
    avg_duration_threshold=5.0,  # 5 秒执行时间
    cooldown_period=60,  # 60 秒冷却期
    notifiers=[LogNotifier()]
)
```

可以添加邮件或 Webhook 通知器：

```python
from src.monitoring import EmailNotifier, WebhookNotifier

email_notifier = EmailNotifier(
    smtp_host="smtp.example.com",
    smtp_port=587,
    username="alert@example.com",
    password="password",
    from_addr="alert@example.com",
    to_addrs=["admin@example.com"]
)

webhook_notifier = WebhookNotifier(
    webhook_url="https://example.com/webhook"
)

alert_manager = AlertManager(
    metrics_collector=metrics_collector,
    error_rate_threshold=0.1,
    avg_duration_threshold=5.0,
    cooldown_period=60,
    notifiers=[LogNotifier(), email_notifier, webhook_notifier]
)
```

### Q: 系统如何保证数据安全？

A: 系统采用多层安全机制：

1. **SQL 注入防护**：使用参数化查询，防止 SQL 注入攻击
2. **操作预览**：变更操作前先预览影响范围
3. **事务支持**：支持多步骤事务，失败自动回滚
4. **SQL 安全检查**：检测危险操作（DROP、TRUNCATE 等）
5. **访问控制**：通过数据库用户权限控制访问范围

---

## 获取帮助

如果遇到问题无法解决：

1. 查看日志文件：`logs/mysql_ai.log`
2. 查看错误日志：`logs/operation_error.log`
3. 查看系统文档：`README.md` 和 `docs/` 目录
4. 联系系统管理员

---

**文档版本**: 1.0
**最后更新**: 2026-03-04
