# 漕河泾停车云数据导出工具 - 部署文档

## 目录

1. [系统要求](#系统要求)
2. [安装步骤](#安装步骤)
3. [配置指南](#配置指南)
4. [部署模式](#部署模式)
5. [生产环境配置](#生产环境配置)
6. [安全加固](#安全加固)
7. [监控和维护](#监控和维护)
8. [备份和恢复](#备份和恢复)

---

## 系统要求

### 最低要求

- **操作系统**:
  - Windows 10/11
  - Linux (Ubuntu 20.04+, CentOS 7+)
  - macOS 11+

- **Python**: 3.8 或更高版本

- **内存**: 512 MB RAM

- **磁盘空间**: 500 MB

### 推荐配置

- **操作系统**: Linux (Ubuntu 22.04 LTS 或 CentOS 8)

- **Python**: 3.10 或更高版本

- **内存**: 2 GB RAM 或更多

- **磁盘空间**: 5 GB 或更多

- **数据库**:
  - MySQL 5.7+ 或 MySQL 8.0+
  - 配置足够的连接数

---

## 安装步骤

### 1. 安装 Python

#### Windows

1. 下载 Python 安装包: https://www.python.org/downloads/

2. 运行安装程序，勾选 "Add Python to PATH"

3. 验证安装:

```powershell
python --version
pip --version
```

#### Linux (Ubuntu/Debian)

```bash
# 更新包列表
sudo apt update

# 安装 Python 3 和 pip
sudo apt install -y python3 python3-pip python3-venv

# 验证安装
python3 --version
pip3 --version
```

#### Linux (CentOS/RHEL)

```bash
# 安装 EPEL 仓库
sudo yum install -y epel-release

# 安装 Python 3
sudo yum install -y python3 python3-pip

# 验证安装
python3 --version
pip3 --version
```

#### macOS

```bash
# 使用 Homebrew 安装
brew install python3

# 验证安装
python3 --version
pip3 --version
```

### 2. 克隆或下载项目

```bash
# 使用 Git 克隆
git clone https://github.com/your-repo/mysql260227.git
cd mysql260227

# 或下载 ZIP 解压
```

### 3. 创建虚拟环境（推荐）

```bash
# Linux/Mac
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### 4. 安装依赖

```bash
# 升级 pip
pip install --upgrade pip

# 安装项目依赖
pip install -r requirements.txt

# 验证安装
pip list
```

### 5. 配置环境变量

```bash
# 复制示例配置文件
cp .env.example .env

# 编辑配置文件
nano .env  # Linux/Mac
notepad .env  # Windows
```

配置内容：

```env
# 数据库配置
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=parkcloud

# AI 配置（可选）
DASHSCOPE_API_KEY=your_api_key

# 监控配置（可选）
ALERT_EMAIL_ENABLED=false
ALERT_EMAIL_SMTP_HOST=
ALERT_EMAIL_SMTP_PORT=587
ALERT_EMAIL_USERNAME=
ALERT_EMAIL_PASSWORD=
ALERT_EMAIL_FROM=
ALERT_EMAIL_TO=

# Webhook 配置（可选）
ALERT_WEBHOOK_ENABLED=false
ALERT_WEBHOOK_URL=
```

### 6. 测试连接

```bash
# 运行测试
python main.py

# 或运行单元测试
pytest tests/ -v
```

---

## 配置指南

### 数据库连接配置

**配置文件**: `.env`

```env
# MySQL 数据库连接
DB_HOST=localhost          # 数据库主机地址
DB_PORT=3306             # 数据库端口
DB_USER=root             # 数据库用户名
DB_PASSWORD=your_password # 数据库密码
DB_NAME=parkcloud        # 数据库名称
```

### 数据库权限要求

数据库用户需要以下权限：

```sql
-- 查询权限
SELECT

-- 变更权限
INSERT, UPDATE, DELETE

-- 结构查看权限
SHOW DATABASES, SHOW TABLES

-- 索引权限（可选）
CREATE INDEX, DROP INDEX
```

授予权限示例：

```sql
-- 授予基本权限
GRANT SELECT, INSERT, UPDATE, DELETE ON parkcloud.* TO 'app_user'@'localhost';

-- 授予完整权限（仅限开发环境）
GRANT ALL PRIVILEGES ON parkcloud.* TO 'app_user'@'localhost';

-- 刷新权限
FLUSH PRIVILEGES;
```

### 日志配置

**配置文件**: `main.py`

```python
# 日志目录
log_dir = "logs"

# 日志级别
logging.basicConfig(level=logging.INFO)

# 日志轮转
RotatingFileHandler(
    'logs/mysql_ai.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,           # 保留 5 个文件
    encoding='utf-8'
)
```

### 监控配置

**配置文件**: `main.py`

```python
# 指标收集器
metrics_collector = MetricsCollector(
    window_size=300  # 5 分钟滑动窗口
)

# 告警管理器
alert_manager = AlertManager(
    metrics_collector=metrics_collector,
    error_rate_threshold=0.1,   # 10% 错误率
    avg_duration_threshold=5.0,   # 5 秒执行时间
    cooldown_period=60,            # 60 秒冷却期
    notifiers=[LogNotifier()]
)
```

---

## 部署模式

### 模式 1: 单机部署

适用于个人开发、测试环境或小规模使用。

**架构**:

```
┌─────────────────────────────────┐
│         用户终端              │
└─────────────┬───────────────┘
              │
              │ CLI
              │
┌─────────────▼───────────────┐
│   应用程序 (main.py)        │
│   ┌─────────────────────┐   │
│   │ 数据库管理器       │   │
│   │ 意图识别器       │   │
│   │ 操作执行器       │   │
│   │ 监控告警系统     │   │
│   └─────────────────────┘   │
└─────────────┬───────────────┘
              │
              │ SQLAlchemy
              │
┌─────────────▼───────────────┐
│      MySQL 数据库          │
│   (parkcloud 数据库)       │
└─────────────────────────────┘
```

**优点**:
- 部署简单
- 资源占用少
- 维护成本低

**缺点**:
- 单点故障
- 扩展性有限

### 模式 2: Docker 容器部署

适用于需要隔离环境和快速部署的场景。

**Dockerfile**:

```dockerfile
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建日志目录
RUN mkdir -p logs output

# 设置环境变量
ENV PYTHONUNBUFFERED=1

# 暴露端口（如果有 Web 界面）
# EXPOSE 8000

# 启动命令
CMD ["python", "main.py"]
```

**docker-compose.yml**:

```yaml
version: '3.8'

services:
  mysql:
    image: mysql:8.0
    container_name: parkcloud_mysql
    environment:
      MYSQL_ROOT_PASSWORD: ${DB_PASSWORD}
      MYSQL_DATABASE: ${DB_NAME}
    ports:
      - "3306:3306"
    volumes:
      - mysql_data:/var/lib/mysql
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    networks:
      - parkcloud_network

  app:
    build: .
    container_name: parkcloud_app
    environment:
      DB_HOST: mysql
      DB_PORT: 3306
      DB_USER: root
      DB_PASSWORD: ${DB_PASSWORD}
      DB_NAME: ${DB_NAME}
    volumes:
      - ./logs:/app/logs
      - ./output:/app/output
    depends_on:
      - mysql
    networks:
      - parkcloud_network
    stdin_open: true
    tty: true

volumes:
  mysql_data:

networks:
  parkcloud_network:
    driver: bridge
```

**部署步骤**:

```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f app

# 进入容器
docker-compose exec app bash
```

### 模式 3: 生产环境部署

适用于高可用、高并发的生产环境。

**架构**:

```
┌─────────────────────────────────────────────────────┐
│                  负载均衡器                     │
└────────────┬────────────────────┬────────────────┘
             │                    │
    ┌────────▼────────┐   ┌─────▼─────────┐
    │  应用服务器 1   │   │ 应用服务器 2  │
    │  (main.py)     │   │  (main.py)   │
    └────────┬────────┘   └─────┬─────────┘
             │                    │
             └────────┬───────────┘
                      │
        ┌─────────────▼─────────────┐
        │   MySQL 主从复制       │
        │  ┌──────┐    ┌──────┐  │
        │  │ 主库 │    │ 从库 │  │
        │  └───┬──┘    └───┬──┘  │
        │      │            │      │
        │      └─────┬──────┘      │
        └────────────┼──────────────┘
                     │
              ┌──────▼──────┐
              │   备份存储   │
              └─────────────┘
```

**组件说明**:

1. **应用服务器**
   - 多实例部署
   - 负载均衡
   - 健康检查

2. **数据库**
   - 主从复制
   - 读写分离
   - 自动故障转移

3. **监控**
   - 应用监控
   - 数据库监控
   - 日志聚合

4. **备份**
   - 定期全量备份
   - 实时增量备份
   - 异地备份存储

---

## 生产环境配置

### 1. 数据库优化

**my.cnf 配置**:

```ini
[mysqld]
# 连接配置
max_connections = 200
max_connect_errors = 10000
wait_timeout = 28800
interactive_timeout = 28800

# InnoDB 配置
innodb_buffer_pool_size = 2G
innodb_log_file_size = 512M
innodb_flush_log_at_trx_commit = 2
innodb_flush_method = O_DIRECT

# 查询缓存（MySQL 5.7）
query_cache_size = 128M
query_cache_type = 1

# 慢查询日志
slow_query_log = 1
long_query_time = 2
slow_query_log_file = /var/log/mysql/slow.log

# 二进制日志（用于备份和复制）
log_bin = /var/log/mysql/mysql-bin.log
binlog_format = ROW
expire_logs_days = 7

# 字符集
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci
```

### 2. 应用配置

**main.py**:

```python
# 生产环境配置
import os

# 日志配置
logging.basicConfig(level=logging.WARNING)  # 生产环境降低日志级别

# 数据库连接池
self.engine = create_engine(
    self.db_url,
    poolclass=QueuePool,
    pool_size=20,         # 生产环境增加连接池
    max_overflow=40,      # 增加最大溢出连接
    pool_recycle=3600,
    pool_pre_ping=True,    # 自动检测断开的连接
    echo=False            # 关闭 SQL 日志
)

# 监控配置
alert_manager = AlertManager(
    metrics_collector=metrics_collector,
    error_rate_threshold=0.05,      # 更严格的阈值
    avg_duration_threshold=3.0,      # 更严格的阈值
    cooldown_period=300,              # 5 分钟冷却期
    notifiers=[
        LogNotifier(),
        EmailNotifier(...),  # 生产环境添加邮件告警
        WebhookNotifier(...)  # 添加 Webhook 告警
    ]
)
```

### 3. 系统配置

**Linux 系统参数**:

```bash
# /etc/sysctl.conf

# 网络配置
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 8192
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_fin_timeout = 30
net.ipv4.tcp_keepalive_time = 1200

# 文件句柄限制
fs.file-max = 65535

# 共享内存
kernel.shmmax = 68719476736
kernel.shmall = 4294967296
```

应用配置：

```bash
# /etc/security/limits.conf

* soft nofile 65535
* hard nofile 65535
```

---

## 安全加固

### 1. 数据库安全

**使用最小权限原则**:

```sql
-- 创建专用用户
CREATE USER 'parkcloud_app'@'%' IDENTIFIED BY 'strong_password';

-- 仅授予必要权限
GRANT SELECT, INSERT, UPDATE, DELETE ON parkcloud.* TO 'parkcloud_app'@'%';

-- 刷新权限
FLUSH PRIVILEGES;
```

**启用 SSL 连接**:

```ini
# my.cnf
[mysqld]
require_ssl = ON
ssl_ca = /path/to/ca.pem
ssl_cert = /path/to/server-cert.pem
ssl_key = /path/to/server-key.pem
```

**禁用远程 root 登录**:

```sql
-- 删除远程 root 用户
DELETE FROM mysql.user WHERE User='root' AND Host NOT IN ('localhost', '127.0.0.1', '::1');
FLUSH PRIVILEGES;
```

### 2. 应用安全

**环境变量保护**:

```bash
# 设置 .env 文件权限
chmod 600 .env

# 不将 .env 提交到版本控制
echo ".env" >> .gitignore
```

**代码安全**:

```python
# 使用密钥管理服务
import os
from cryptography.fernet import Fernet

# 加密敏感配置
key = os.environ.get('ENCRYPTION_KEY')
cipher_suite = Fernet(key)

# 不要在代码中硬编码密码
# 错误示例
# password = "hardcoded_password"  # ❌

# 正确示例
password = os.environ.get('DB_PASSWORD')  # ✅
```

### 3. 网络安全

**防火墙配置**:

```bash
# UFW (Ubuntu)
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 3306/tcp  # MySQL（如果需要远程访问）
sudo ufw enable

# iptables
sudo iptables -A INPUT -p tcp --dport 22 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 3306 -s 192.168.1.0/24 -j ACCEPT
sudo iptables -A INPUT -j DROP
```

**使用 VPN 或专线**:

生产环境建议：
- 使用 VPN 连接数据库
- 或使用专线
- 禁止公网访问数据库端口

---

## 监控和维护

### 1. 系统监控

**使用监控工具**:

```bash
# 安装 htop
sudo apt install htop  # Linux
brew install htop       # macOS

# 查看系统资源
htop
```

**关键指标**:
- CPU 使用率 < 80%
- 内存使用率 < 80%
- 磁盘使用率 < 80%
- 网络延迟 < 50ms

### 2. 应用监控

**查看应用日志**:

```bash
# 实时查看日志
tail -f logs/mysql_ai.log

# 查看错误日志
tail -f logs/mysql_ai_error.log

# 搜索错误
grep ERROR logs/mysql_ai.log
```

**检查告警**:

```bash
# 查看操作日志中的告警
grep '"event": "alert"' logs/operation.log

# 统计告警数量
grep '"event": "alert"' logs/operation.log | wc -l
```

### 3. 数据库监控

**查看数据库状态**:

```sql
-- 查看连接数
SHOW STATUS LIKE 'Threads_connected';

-- 查看慢查询
SHOW STATUS LIKE 'Slow_queries';

-- 查看查询缓存命中率
SHOW STATUS LIKE 'Qcache%';

-- 查看 InnoDB 状态
SHOW ENGINE INNODB STATUS;
```

**数据库性能监控工具**:

```bash
# MySQL Workbench
# Percona Toolkit
# pt-query-digest /var/log/mysql/slow.log
```

### 4. 定期维护任务

**数据库维护**:

```bash
# 每周执行
# 1. 优化表
mysql -u root -p -e "OPTIMIZE TABLE parkcloud.*;"

# 2. 分析表
mysql -u root -p -e "ANALYZE TABLE parkcloud.*;"

# 3. 检查表
mysql -u root -p -e "CHECK TABLE parkcloud.*;"
```

**日志清理**:

```bash
# 每月清理旧日志
find logs/ -name "*.log.*" -mtime +30 -delete

# 或使用 logrotate 配置自动轮转
```

---

## 备份和恢复

### 1. 数据库备份

**全量备份**:

```bash
# 使用 mysqldump
mysqldump -u root -p parkcloud > backup_$(date +%Y%m%d).sql

# 压缩备份
mysqldump -u root -p parkcloud | gzip > backup_$(date +%Y%m%d).sql.gz
```

**增量备份**:

```bash
# 启用二进制日志
# my.cnf
log_bin = /var/log/mysql/mysql-bin.log

# 备份二进制日志
mysqladmin -u root -p flush-logs
```

**自动备份脚本**:

```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/backups/mysql"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# 全量备份
mysqldump -u root -p$DB_PASSWORD parkcloud | gzip > $BACKUP_DIR/parkcloud_$DATE.sql.gz

# 清理 7 天前的备份
find $BACKUP_DIR -name "parkcloud_*.sql.gz" -mtime +7 -delete

echo "Backup completed: parkcloud_$DATE.sql.gz"
```

**定时任务**:

```bash
# 编辑 crontab
crontab -e

# 每天凌晨 2 点执行备份
0 2 * * * /path/to/backup.sh
```

### 2. 数据库恢复

**从 SQL 文件恢复**:

```bash
# 解压（如果是压缩的）
gunzip backup_20260304.sql.gz

# 恢复
mysql -u root -p parkcloud < backup_20260304.sql
```

**从二进制日志恢复**:

```bash
# 应用二进制日志
mysqlbinlog /var/log/mysql/mysql-bin.000123 | mysql -u root -p parkcloud

# 指定时间点恢复
mysqlbinlog --start-datetime="2026-03-04 10:00:00" \
            --stop-datetime="2026-03-04 12:00:00" \
            /var/log/mysql/mysql-bin.000123 | \
            mysql -u root -p parkcloud
```

### 3. 应用备份

**备份应用文件**:

```bash
# 备份应用代码
tar -czf app_backup_$(date +%Y%m%d).tar.gz \
    main.py \
    src/ \
    requirements.txt

# 备份配置文件
cp .env .env.backup
```

**恢复应用**:

```bash
# 解压应用代码
tar -xzf app_backup_20260304.tar.gz

# 恢复配置
cp .env.backup .env
```

---

## 故障恢复流程

### 数据库故障

1. **检测故障**
   - 检查数据库进程
   - 查看错误日志
   - 检查连接状态

2. **尝试恢复**
   - 重启数据库服务
   - 检查磁盘空间
   - 检查配置文件

3. **数据恢复**
   - 从最近的备份恢复
   - 应用二进制日志
   - 验证数据完整性

### 应用故障

1. **检测故障**
   - 检查应用进程
   - 查看应用日志
   - 检查监控指标

2. **尝试恢复**
   - 重启应用
   - 回滚到上一个版本
   - 检查依赖服务

3. **通知相关人员**
   - 发送告警通知
   - 记录故障日志
   - 分析故障原因

---

**文档版本**: 1.0
**最后更新**: 2026-03-04
