# 空表与幽灵表索引治理任务分解

## Task 0：先建分支（必做）

- [x] 创建功能分支：`feat/pruned-index-maintenance`
- [x] 基于当前主干同步最新代码后切换到新分支
- [x] 在分支内开始后续开发与测试

建议命令：

```bash
git checkout main
git pull
git checkout -b feat/pruned-index-maintenance
```

## Task 1：实现空表检测能力

- [x] 在 `DatabaseManager` 增加空表检测方法
- [x] 实现快速检测（`information_schema.TABLE_ROWS`）逻辑
- [x] 增加二次探测兜底逻辑（`SELECT 1 ... LIMIT 1`）
- [x] 为空表检测增加单元测试

交付物：

- 代码：空表检测方法与调用入口
- 测试：空表/非空表/异常分支覆盖

## Task 2：实现索引存储清理能力

- [x] 在 `GraphStore` 增加索引表 ID 枚举能力
- [x] 校验并加固表与字段删除逻辑
- [x] 提供批量删除执行路径
- [x] 为清理能力增加单元测试

交付物：

- 代码：索引枚举与删除方法
- 测试：差集删除、重复执行幂等场景

## Task 3：改造 SchemaIndexer 治理流程

- [x] 为索引流程新增 `skip_empty_tables` 开关（默认开启）
- [x] 在索引单表前接入空表检测并记录跳过日志
- [x] 新增 `prune_invalid_entries()` 清理幽灵表逻辑
- [x] 在治理流程输出统计摘要（跳过数、清理数、索引数）

交付物：

- 代码：索引器治理主流程
- 日志：可观测治理统计信息

## Task 4：集成 CLI 参数与行为

- [x] 在 `index schema` 增加 `--prune` 参数
- [x] 在 `index schema` 增加 `--include-empty` 参数
- [x] 实现参数组合行为与默认策略
- [x] 更新命令帮助与使用示例

交付物：

- CLI：完整参数与执行路径
- 文档：命令行为说明

## Task 5：验证与回归

- [x] 新增/更新单元测试并通过
- [x] 增加集成测试覆盖 `--prune` 与空表跳过场景
- [x] 运行完整测试集，确认无回归
- [x] 记录一次真实库执行结果（日志摘要）

交付物：

- 测试报告：核心治理能力通过
- 验证记录：真实运行前后对比

## Task 6：验收失败项修复闭环

- [x] 修复全量回归测试中的失败用例
- [x] 补充异常路径日志可定位的自动化验证
- [x] 补充 `index schema --prune` 场景集成测试
- [x] 更新发布说明与回滚方案文档
