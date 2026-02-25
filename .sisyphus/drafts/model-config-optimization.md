# 草稿: oh-my-opencode 模型配置优化

## 用户需求
配置多个模型（Kimi K2.5、Kimi K2 Thinking、GLM-5、GLM-4.7、GLM-4.6V）到 oh-my-opencode，而不是使用通用配置。

## 配置文件位置
`C:\Users\Administrator\.config\opencode\oh-my-opencode.json`

## 当前配置状态
所有智能体和类别都使用 `zai-coding-plan/glm-4.7-free` 模型（共 17 个配置项）

## 模型特性分析

### Kimi K2.5
- **核心优势**：视觉编程、Agent Swarm（1500次并行调用）、多模态
- **适用场景**：前端开发、视频理解、复杂任务批量处理、多智能体协作
- **上下文**：256K tokens
- **套餐**：基础套餐，用量较少
- **模型标识**：`kimi-for-coding/k2p5`

### Kimi K2 Thinking
- **核心优势**：深度推理、数学证明（AIME25: 100%）、工具调用融合
- **适用场景**：数学证明、学术研究、代码调试、复杂问题多步求解
- **上下文**：256K tokens
- **套餐**：基础套餐，用量较少
- **模型标识**：`kimi-for-coding/k2p5-thinking`

### GLM-5
- **核心优势**：复杂软件系统、长程智能体、国产化部署、744B参数
- **适用场景**：企业级Agent、复杂系统工程、国产化AI基础设施
- **上下文**：200K tokens
- **套餐**：pro 套餐，用量充足
- **模型标识**：`zai-coding-plan/glm-5`

### GLM-4.7
- **核心优势**：Agentic Coding（LiveCodeBench: 73.8%）、前端审美、工程化落地
- **适用场景**：代码生成、前端开发、调试修复、长程项目规划
- **上下文**：200K tokens
- **套餐**：pro 套餐，用量充足
- **模型标识**：`zai-coding-plan/glm-4.7`

### GLM-4.6V
- **核心优势**：原生多模态Function Call、图像即参数、文档理解
- **适用场景**：视觉内容分析、文档智能解读、前端UI复现、OCR识别
- **上下文**：128K tokens
- **套餐**：pro 套餐，用量充足
- **模型标识**：`zai-coding-plan/glm-4.6v`

## 推荐配置方案：性能优先（成本优化版）

### 核心策略
- **GLM 系列**（zai-coding-plan，pro 套餐）：主力使用，覆盖大部分场景
- **Kimi 系列**（基础套餐）：精准用在关键位置，发挥 Agent Swarm 和深度推理优势

### 专用智能体配置

| 智能体 | 当前模型 | 推荐模型 | 理由 |
|--------|---------|---------|------|
| **sisyphus** | glm-4.7-free | kimi-for-coding/k2p5 | 主编排器需要 Agent Swarm，价值最高 |
| **hephaestus** | glm-4.7-free | zai-coding-plan/glm-5 | 深度工作者需要长程智能体能力 |
| **prometheus** | glm-4.7-free | zai-coding-plan/glm-4.7 | 战略规划，Agentic Coding 能力强 |
| **oracle** | glm-4.7-free | zai-coding-plan/glm-5 | 架构顾问需要高智商咨询 |
| **librarian** | glm-4.7-free | zai-coding-plan/glm-4.7 | 文档检索，不需要超深度推理 |
| **explore** | glm-4.7-free | zai-coding-plan/glm-4.7 | 快速代码搜索，用量大 |
| **multimodal-looker** | glm-4.7-free | kimi-for-coding/k2p5 | 视觉分析，K2.5 的视觉编程是核心优势 |
| **metis** | glm-4.7-free | zai-coding-plan/glm-4.7 | 计划分析 |
| **momus** | glm-4.7-free | kimi-for-coding/k2p5-thinking | 代码审查需要深度推理，用量少但质量要求高 |
| **atlas** | glm-4.7-free | zai-coding-plan/glm-4.7 | 待办编排 |

### 任务类别配置

| 类别 | 当前模型 | 推荐模型 | 理由 |
|------|---------|---------|------|
| **visual-engineering** | glm-4.7-free | zai-coding-plan/glm-4.6v | 视觉任务专用 |
| **ultrabrain** | glm-4.7-free | zai-coding-plan/glm-5 | 深度逻辑推理 |
| **deep** | glm-4.7-free | zai-coding-plan/glm-5 | 自主问题解决 |
| **artistry** | glm-4.7-free | zai-coding-plan/glm-4.7 | 创造性任务 |
| **quick** | glm-4.7-free | zai-coding-plan/glm-4.7 | 简单快速任务 |
| **unspecified-low** | glm-4.7-free | zai-coding-plan/glm-4.7 | 低难度任务 |
| **unspecified-high** | glm-4.7-free | zai-coding-plan/glm-5 | 高难度任务 |
| **writing** | glm-4.7-free | zai-coding-plan/glm-4.7 | 文档写作 |

### 模型使用比例预估

| 模型 | 配置项数量 | 预估用量 | 原因 |
|------|-----------|----------|------|
| **GLM-5** | 5 项 | ~35% | 高难度任务（hephaestus, oracle, ultrabrain, deep, unspecified-high） |
| **GLM-4.7** | 8 项 | ~50% | 主力模型，覆盖大部分场景 |
| **GLM-4.6V** | 1 项 | ~5% | 视觉专用，用量少 |
| **K2.5** | 2 项 | ~8% | 关键路径（sisyphus, multimodal-looker） |
| **K2 Thinking** | 1 项 | ~2% | 审查任务，用量最少但质量要求最高 |

### 关键决策说明

✅ **Kimi 系列仅用 3 处**：
- `sisyphus` + K2.5：主编排器，Agent Swarm 能力无可替代
- `multimodal-looker` + K2.5：视觉编程是 K2.5 核心优势
- `momus` + K2 Thinking：代码审查需要最严格的深度推理

✅ **GLM 系列覆盖其余 14 处**：
- 充分利用 pro 套餐的充足用量
- GLM-5 处理所有高难度任务
- GLM-4.7 作为通用主力
- GLM-4.6V 专用于视觉

### 完整配置 JSON（可直接复制）

```json
{
  "$schema": "https://raw.githubusercontent.com/code-yeongyu/oh-my-opencode/master/assets/oh-my-opencode.schema.json",
  "agents": {
    "sisyphus": {
      "model": "kimi-for-coding/k2p5",
      "reasoningEffort": "high"
    },
    "hephaestus": {
      "model": "zai-coding-plan/glm-5",
      "variant": "high"
    },
    "prometheus": {
      "model": "zai-coding-plan/glm-4.7",
      "variant": "high"
    },
    "oracle": {
      "model": "zai-coding-plan/glm-5",
      "variant": "max"
    },
    "librarian": {
      "model": "zai-coding-plan/glm-4.7"
    },
    "explore": {
      "model": "zai-coding-plan/glm-4.7"
    },
    "multimodal-looker": {
      "model": "kimi-for-coding/k2p5"
    },
    "metis": {
      "model": "zai-coding-plan/glm-4.7"
    },
    "momus": {
      "model": "kimi-for-coding/k2p5-thinking"
    },
    "atlas": {
      "model": "zai-coding-plan/glm-4.7"
    }
  },
  "categories": {
    "visual-engineering": {
      "model": "zai-coding-plan/glm-4.6v"
    },
    "ultrabrain": {
      "model": "zai-coding-plan/glm-5"
    },
    "deep": {
      "model": "zai-coding-plan/glm-5"
    },
    "artistry": {
      "model": "zai-coding-plan/glm-4.7"
    },
    "quick": {
      "model": "zai-coding-plan/glm-4.7"
    },
    "unspecified-low": {
      "model": "zai-coding-plan/glm-4.7"
    },
    "unspecified-high": {
      "model": "zai-coding-plan/glm-5"
    },
    "writing": {
      "model": "zai-coding-plan/glm-4.7"
    }
  }
}
```

## 用户决策
- [x] 选择性能优先方案（成本优化版）
- [x] 修正 GLM-4.7 模型标识（无 pro 版本）
- [ ] 用户确认最终配置方案

## 下一步
生成工作计划，修改配置文件 `C:\Users\Administrator\.config\opencode\oh-my-opencode.json`
