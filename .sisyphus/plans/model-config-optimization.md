# 工作计划：oh-my-opencode 模型配置优化

## TL;DR

> **快速摘要**：将 oh-my-opencode 配置文件从默认的 `opencode/glm-4.7-free` 模型更新为多模型配置方案，包括 Kimi K2.5、Kimi K2 Thinking、GLM-5、GLM-4.7 和 GLM-4.6V。
>
> **交付物**：
> - 更新后的配置文件 `C:\Users\Administrator\.config\opencode\oh-my-opencode.json`
>
> **预估工作量**：Quick（<5 分钟）
> **并行执行**：NO（单文件修改）
> **关键路径**：备份原配置 → 写入新配置

---

## 上下文

### 原始需求
用户希望为 oh-my-opencode 配置多个高性能模型，而不是使用默认的免费模型配置。

### 讨论摘要
**关键决策**：
- Provider 标识：GLM 系列使用 `zai-coding-plan/`，Kimi 系列使用 `kimi-for-coding/`
- 配置风格：简洁配置（仅 model + variant/reasoningEffort）
- sisyphus 使用 Kimi K2.5（Agent Swarm 能力）
- momus 使用 Kimi K2 Thinking（深度推理能力）
- multimodal-looker 使用 Kimi K2.5（视觉编程能力）
- 其余智能体使用 GLM 系列

### 自我审查（Gap 分析）

**自动解决的问题**：
- ✅ 确认正确的 provider 名称：`zai-coding-plan`（不是 `zhipu-ai-coding-plan`）
- ✅ 确认配置文件路径和格式

**需要验证的假设**：
- 用户已订阅 Kimi 和智谱 AI Coding Plan 服务
- 用户已配置相应的 API keys

---

## 工作目标

### 核心目标
更新 oh-my-opencode 配置文件，为 10 个智能体和 8 个类别分配最适合的模型。

### 具体交付物
- `C:\Users\Administrator\.config\opencode\oh-my-opencode.json` - 更新后的配置文件

### 完成定义
- [ ] 配置文件被正确更新
- [ ] JSON 格式有效（可通过 `opencode models` 命令验证）
- [ ] 所有 18 个配置项（10 agents + 8 categories）已更新

### 必须包含
- 所有智能体的 model 配置
- sisyphus 的 `reasoningEffort: "high"`
- hephaestus, prometheus 的 `variant: "high"`
- oracle 的 `variant: "max"`

### 必须不包含（约束）
- 不要添加 temperature、maxTokens 等高级参数
- 不要修改其他 OpenCode 配置文件
- 不要合并配置（完全替换）

---

## 验证策略

### 测试决策
- **基础设施存在**：NO（配置文件修改，无需测试）
- **自动化测试**：NO
- **Agent 执行 QA**：YES

### QA 策略
使用 Bash 命令验证配置：
- 验证 JSON 格式有效
- 验证配置项数量正确

---

## 执行策略

### 执行步骤
```
步骤 1：备份原配置（可选）
  → 复制现有配置到备份文件

步骤 2：写入新配置
  → 使用 Write 工具覆盖配置文件

步骤 3：验证配置
  → 运行验证命令确认配置有效
```

---

## TODOs

- [ ] 1. 更新 oh-my-opencode 配置文件

  **要做什么**：
  - 备份现有配置文件（可选）
  - 将新配置内容写入 `C:\Users\Administrator\.config\opencode\oh-my-opencode.json`

  **不要做什么**：
  - 不要修改 JSON 结构
  - 不要添加额外的高级参数
  - 不要修改其他配置文件

  **推荐智能体配置**：
  - **类别**：`quick`
    - 理由：单文件修改，简单快速
  - **技能**：无

  **并行化**：
  - **可并行运行**：NO
  - **并行组**：顺序
  - **阻塞**：无
  - **被阻塞**：无

  **参考**（关键）：
  - `C:\Users\Administrator\.config\opencode\oh-my-opencode.json` - 目标配置文件
  - `e:/trae-pc/mysql-260210/configuration.md` - oh-my-opencode 配置参考文档

  **验收标准**：
  - [ ] 配置文件已更新
  - [ ] JSON 格式有效

  **QA 场景**：

  ```
  场景：配置文件格式验证（正常路径）
    工具：Bash
    前置条件：配置文件已更新
    步骤：
      1. 读取配置文件内容
      2. 使用 jq 或 node 验证 JSON 格式
    预期结果：JSON 格式有效，无语法错误
    失败指示：JSON 解析错误
    证据：.sisyphus/evidence/task-1-json-valid.txt

  场景：配置项数量验证
    工具：Bash
    前置条件：配置文件已更新
    步骤：
      1. 检查 agents 对象包含 10 个键
      2. 检查 categories 对象包含 8 个键
    预期结果：agents=10, categories=8
    失败指示：配置项数量不匹配
    证据：.sisyphus/evidence/task-1-config-count.txt
  ```

  **要捕获的证据**：
  - [ ] JSON 验证输出
  - [ ] 配置项统计

  **提交**：YES
  - 消息：`chore(config): update oh-my-opencode model configuration`
  - 文件：无（配置文件在项目外）

---

## 最终验证步骤

- [ ] F1. **配置完整性检查** — `quick`
  验证所有 18 个配置项已正确设置，模型标识格式正确（provider/model）。
  输出：`Agents [10/10] | Categories [8/8] | 格式 [VALID] | 结果：通过/失败`

---

## 提交策略

- **1**：`chore(config): update oh-my-opencode model configuration` — 不适用（配置文件在项目外）

---

## 成功标准

### 验证命令
```bash
# 验证 JSON 格式
node -e "JSON.parse(require('fs').readFileSync('C:/Users/Administrator/.config/opencode/oh-my-opencode.json', 'utf8')); console.log('JSON Valid')"

# 验证配置项数量
node -e "const c=JSON.parse(require('fs').readFileSync('C:/Users/Administrator/.config/opencode/oh-my-opencode.json','utf8')); console.log('Agents:', Object.keys(c.agents).length, 'Categories:', Object.keys(c.categories).length)"
```

### 最终检查清单
- [ ] 所有"必须包含"项存在
- [ ] 所有"必须不包含"项不存在
- [ ] JSON 格式有效
- [ ] 模型标识格式正确
