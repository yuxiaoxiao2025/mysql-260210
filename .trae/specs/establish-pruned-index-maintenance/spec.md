# 空表与幽灵表索引治理规范（Pruned Index Maintenance）

## Why

当前元数据向量索引存在两类高频噪声：

- 空表噪声：无数据表被写入索引，挤占检索 `top_k`。
- 幽灵表噪声：已删除或改名的表仍残留在索引中。

噪声会直接造成召回偏移，进而影响 SQL 生成准确性与业务表命中率，出现查询结果为 `None` 或错误表优先命中的问题。

## What Changes

- 交付流程要求：实施前必须先创建独立分支，再进行治理改造与验证。
- 索引流程默认跳过空表，避免新增噪声写入。
- 支持按需清理幽灵表索引（prune），保证索引与真实库表集合一致。
- 提供 CLI 显式控制项，覆盖日常维护与回溯场景。
- 增加可回归测试与日志指标，确保治理结果可验证。

## Impact

- 检索质量：有效业务表在召回中的占比提升，降低无效上下文干扰。
- 运维成本：通过标准命令执行治理，减少手工排查与索引污染累积。
- 兼容性：默认行为保持安全保守，不触发业务数据变更。
- 风险控制：通过幂等执行、候选清单与摘要日志降低误删风险。

## ADDED Requirements

### Requirement: 实施前必须先建分支
实施索引治理改造前，系统必须要求在独立分支执行开发与验证，避免直接在主干实施。

#### Scenario: 在治理前执行前置检查
- **GIVEN** 用户准备执行索引治理改造
- **WHEN** 治理流程开始
- **THEN** 系统提示并要求先完成独立分支创建

### Requirement: 提供空表检测能力
系统必须在索引前检测表是否为空，以避免将无效表写入向量索引。

#### Scenario: 通过统计信息判断空表
- **GIVEN** 目标表可读取 `information_schema.TABLES.TABLE_ROWS`
- **WHEN** 执行索引前检测
- **THEN** 系统使用 `TABLE_ROWS` 作为空表判定依据

#### Scenario: 统计信息不可靠时降级探测
- **GIVEN** `TABLE_ROWS` 无法可靠反映真实行数
- **WHEN** 系统执行空表二次探测
- **THEN** 系统使用 `SELECT 1 ... LIMIT 1` 判断表是否为空

### Requirement: 提供幽灵表清理能力
系统必须支持按需清理索引中已不存在于数据库的表及其字段索引。

#### Scenario: 执行幽灵表差集清理
- **GIVEN** 索引侧存在表 ID 集合且数据库可返回真实表清单
- **WHEN** 用户触发 prune
- **THEN** 系统计算差集并删除无效表及其字段索引

### Requirement: 输出治理观测指标
系统必须输出跳过空表数量、清理幽灵表数量、索引表数量等指标用于回归验证。

#### Scenario: 治理任务完成后输出摘要
- **GIVEN** 一次索引治理任务执行完成
- **WHEN** 系统生成执行结果
- **THEN** 输出空表跳过数、幽灵表清理数与索引表总数

## MODIFIED Requirements

### Requirement: 调整默认索引行为
`index schema` 的默认行为必须为跳过空表，且默认不执行 prune。

#### Scenario: 使用默认参数执行索引
- **GIVEN** 用户执行 `index schema`
- **WHEN** 未提供额外参数
- **THEN** 系统跳过空表并且不执行 prune

### Requirement: 扩展索引命令参数语义
系统必须支持明确的参数组合以覆盖日常维护和回溯场景。

#### Scenario: 使用 prune 参数执行索引
- **GIVEN** 用户执行 `index schema --prune`
- **WHEN** 命令开始处理
- **THEN** 系统先清理幽灵表再执行索引

#### Scenario: 使用 include-empty 参数执行索引
- **GIVEN** 用户执行 `index schema --include-empty`
- **WHEN** 命令开始处理
- **THEN** 系统显式包含空表参与索引

#### Scenario: 同时使用 prune 与 include-empty
- **GIVEN** 用户执行 `index schema --prune --include-empty`
- **WHEN** 命令开始处理
- **THEN** 系统先清理幽灵表并索引全部表

### Requirement: 强化非功能约束
系统必须满足幂等性、安全性与性能约束，确保治理可长期稳定执行。

#### Scenario: 重复执行 prune
- **GIVEN** 已执行过一次 prune 且索引与真实库表一致
- **WHEN** 再次执行 prune
- **THEN** 不发生异常删除或不一致结果

#### Scenario: 执行治理过程中的安全边界
- **GIVEN** 系统执行索引治理
- **WHEN** 涉及数据操作
- **THEN** 仅操作元数据索引，不执行业务数据变更 SQL

#### Scenario: 在中型库下执行治理
- **GIVEN** 数据库规模为千级表
- **WHEN** 执行治理流程
- **THEN** 任务整体时延保持在可接受范围

## REMOVED Requirements

### Requirement: 取消默认包含空表的行为
系统不再允许“默认索引包含空表”的隐式行为。

#### Scenario: 执行无参数索引时的空表处理
- **GIVEN** 用户未设置 `--include-empty`
- **WHEN** 执行 `index schema`
- **THEN** 空表不会被默认纳入索引

### Requirement: 取消索引长期不一致容忍
系统不再容忍索引与真实库表长期不一致，应通过显式 prune 进行治理。

#### Scenario: 发现索引存在已删除表
- **GIVEN** 索引中存在数据库已删除或改名的表
- **WHEN** 用户执行 prune
- **THEN** 系统清理幽灵表并恢复索引一致性
