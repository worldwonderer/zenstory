# zenstory 权益体系重设计（2026-02）

## 1. 目标与原则

### 目标
- 让用户 10 秒内看懂“我买了能多做什么”。
- 提升付费转化（Free -> Paid）与年付占比。
- 支持长篇创作、AI Agent 深度协作，不再被“对话次数”口径限制。

### 设计原则
- 价值导向：按“可完成任务”售卖，不按抽象参数售卖。
- 单位统一：统一为「创作额度」「Agent 执行额度」「项目容量」。
- 路径清晰：全站升级入口统一主 CTA，减少重复按钮和分散链路。
- 可扩展：支持 Free / Pro / Max / Team 分层并兼容旧字段。

---

## 2. 主流竞品（2026-02-20 观测）

> 注：以下为官方公开页面信息快照，价格可能随地区与税费变化。

| 产品 | 个人入门付费锚点 | 分层方式 | 对用户可感知卖点 |
|---|---:|---|---|
| ChatGPT | Plus $20/月 | Free/Plus/Pro/Business/Enterprise | 更高模型限额、速度、工具能力 |
| Claude | Pro $20/月；Max $100/$200 | Free/Pro/Max | 明确“5x/20x”用量分层，进阶用户易理解 |
| Google AI (Google One) | AI Pro $19.99/月 | 存储 + AI 组合包 | 2TB + AI credits，权益打包感强 |
| Perplexity | Pro $20/月（Enterprise Pro $40/seat） | Pro/Enterprise/Max | 研究/文件/模型访问分层，任务化描述 |
| Notion | Business $20/seat 含 Notion AI | AI 并入高阶套餐 | AI 不再单独 add-on，减少决策成本 |
| Sudowrite（写作垂类） | $10/$22/$44 | 按 credits 分层 | 明确“可写作量”+ rollover，适合长篇作者 |

### 竞品共性
- “$20/月”是个人 AI 订阅强锚点。
- 高阶层普遍采用倍数化（5x/20x）或 credit 包。
- 企业层核心不是更聪明，而是协作、权限、审计、数据安全。
- 写作垂类更强调“可产出量”而非“消息次数”。

---

## 3. zenstory 当前痛点（产品视角）

- 指标口径偏技术化：`每日对话次数` 难映射到“我能写完多少内容”。
- 档位过少：仅 Free/Pro，无法承接中重度用户的升级阶梯。
- 升级路径分散：兑换码/积分兑换/开通按钮在多个位置重复，决策负担大。
- 长篇创作不友好：上下文、Agent 执行、素材处理配额不足以支撑长期项目。
- 邀请与积分价值感弱：奖励与核心写作价值（额度、效率）关联不够强。

---

## 4. 新权益架构（建议）

## 4.1 权益单位重构（面向用户文案）

把旧指标映射为 3 个核心单位：

1. 创作额度（Writing Credits / 月）
- 覆盖：AI 对话、改写、续写、润色等文本生成消耗。
- 展示：`本月剩余可创作约 X 万字`（估算值）。

2. Agent 执行额度（Agent Runs / 月）
- 覆盖：多步任务（规划、资料检索、批量改写、交付打包）。
- 展示：`本月可执行 N 次深度任务`。

3. 项目容量（Active Projects + Context）
- 覆盖：活跃项目数、上下文窗口、素材库容量。
- 展示：`可同时推进 N 个长篇项目`。

## 4.2 新套餐分层（建议价格带）

### Free（体验版）
- 适合：轻度尝试用户
- 建议：
  - 活跃项目：1
  - 创作额度：中低（如 10 万字估算/月）
  - Agent 执行：低（如 20 次/月）
  - 素材上传/拆解：低
  - 导出：TXT/MD
- 目标：让用户“能完成一次完整写作闭环”，而不是只能试两下。

### Pro（创作者版）
- 价格锚点：39-59 CNY/月（建议 49 CNY 保持）
- 适合：稳定日更、长篇作者
- 建议：
  - 活跃项目：5
  - 创作额度：Free 的 5x
  - Agent 执行：Free 的 5x
  - 更大上下文 + 更多素材配额
  - 导出：TXT/MD/DOCX/PDF
  - 优先队列
- 卖点文案：`把“卡配额”变成“稳定产出”`。

### Max（工作室版）
- 价格锚点：99-149 CNY/月
- 适合：重度创作、多项目并行、工作室
- 建议：
  - 活跃项目：20 或无限
  - 创作额度：Pro 的 4x-6x
  - Agent 执行：Pro 的 5x
  - 长上下文与高并发任务
  - 批量导出/交付包
  - 高级优先支持
- 卖点文案：`多线并行 + 重度 Agent 协作`。

### Team（后续）
- seat 计费，含协作权限、审计、组织素材库、SSO（可后置）。

---

## 5. 价格与转化策略

## 5.1 定价结构
- 月付：Free / Pro / Max。
- 年付：默认 15%-20% 折扣。
- 新用户首月策略（二选一）：
  - 7 天全量试用；或
  - 首月体验价（如 9.9/19.9）。

## 5.2 触发式升级（in-product）
- 触发时机：命中配额阈值 80% / 100%、执行高价值功能前。
- 触发文案：只说“差多少可完成任务”，不说底层参数。
- 付款页固定展示：
  - 当前用量
  - 升级后增量（+X 项目、+Y 次 Agent、+Z 导出格式）
  - 单一主按钮 `升级到 Pro/Max`

## 5.3 邀请与积分重做
- 邀请双向奖励：
  - 邀请人：获得「创作额度包 / Agent 包」
  - 被邀请人：首月折扣或 7 天 Pro
- 积分兑换优先改为“权益包”：
  - 不是只兑换 Pro 天数，而是可兑换 `本月 Agent +50`、`创作额度 +30%` 等。

---

## 6. 与现有后端字段兼容方案

当前字段（`features`）保留，并新增标准化字段：

- `writing_credits_monthly`
- `agent_runs_monthly`
- `active_projects_limit`
- `context_tokens_limit`
- `material_storage_mb`
- `batch_exports_monthly`
- `priority_queue_level`
- `entitlements_version` (v2)

兼容映射（示例）：
- `ai_conversations_per_day` -> `writing_credits_monthly`（通过换算器）
- `max_projects` -> `active_projects_limit`
- `context_window_tokens` -> `context_tokens_limit`

建议新增接口：
- `GET /api/v1/subscription/catalog`
  - 返回前端可直接渲染的套餐卡、对比项、推荐标签、CTA 文案。

---

## 7. 前端信息架构与文案规范

- 顶部只保留一个主动作：`升级到 Pro/Max`。
- 次动作统一收敛到二级入口：`使用兑换码`。
- 套餐卡每张只回答三件事：
  - 适合谁
  - 每月可完成什么
  - 多少钱
- 禁止出现多个语义重叠按钮（如“解锁 Pro”“兑换 Pro会员”“兑换码”同级并列）。

---

## 8. 指标与实验（8 周）

核心指标：
- 支付转化率（访客 -> 付费）
- 升级漏斗完成率（查看权益页 -> 支付成功）
- 首周留存、首月续费率、年付占比
- ARPPU / MRR

A/B 建议：
- A：技术参数型文案；B：任务产出型文案。
- A：两档（Free/Pro）；B：三档（Free/Pro/Max）。
- A：积分兑天数；B：积分兑权益包。

目标（建议）：
- 付费转化 +20%~35%
- 年付占比 +8%~15%
- 因配额导致流失率 -20%

---

## 9. 落地节奏

### P0（1-2 周）
- 前端统一升级入口与文案。
- 后端补 `catalog` 接口（可先静态配置）。
- 事件埋点补齐。

### P1（2-3 周）
- 新套餐上线（Free/Pro/Max）与迁移脚本。
- 权益包（积分/邀请）上线。

### P2（3-4 周）
- 动态配额优化（按行为推荐升级）。
- Team 版需求验证。

---

## 10. 风险与控制

- 风险：旧用户对权益变更敏感。
- 控制：
  - 老用户权益保护期（30-60 天）
  - 清晰迁移公告（“你多了什么，不会少什么”）
  - 可回退开关：`entitlements_version`

---

## 11. 参考来源

- OpenAI ChatGPT Plus / Business 价格与权益：
  - https://help.openai.com/en/articles/6950777-what-is-chatgpt-plus%3F.eps
  - https://openai.com/business/chatgpt-pricing/
- Anthropic Claude Pro / Max：
  - https://support.anthropic.com/en/articles/8325610-how-much-does-claude-pro-cost
  - https://www.anthropic.com/max
  - https://support.anthropic.com/en/articles/11049744-how-much-does-the-max-plan-cost
- Google One / Google AI Pro：
  - https://one.google.com/plans
- Perplexity Pro / Enterprise：
  - https://www.perplexity.ai/enterprise/pricing
  - https://www.perplexity.ai/help-center/en/articles/11187416-which-perplexity-subscription-plan-is-right-for-you
- Notion Pricing：
  - https://www.notion.com/pricing
  - https://www.notion.com/help/2025-pricing-changes
- Sudowrite Pricing（写作垂类）：
  - https://sudowrite.com/pricing
  - https://docs.sudowrite.com/plans--account/wBnmhtSyMcWtk2BLzifGkz/what-plans-are-available/mwfVvj2rGcKYs1BQy4Pdcb

