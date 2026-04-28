# 升级入口分层策略（2026-03）

## 1) 结论（商业化 PM + UIUX）

采用 **“多入口，单路径；弹窗优先，页面兜底”**：

- 多入口：在聊天、灵感复制、设置、权益页都提供升级触点。
- 单路径：所有触点最终收敛到同一升级/权益路径，避免同屏多主决策。
- 分层触达：
  - **强阻断**（配额已耗尽）→ `Modal`（立即可行动）
  - **弱提醒**（接近阈值）→ `Toast/Inline`
  - **深比较**（套餐差异）→ `Pricing Page`

## 2) 架构落地（前端）

### 2.1 配置化策略
- 新增 `apps/web/src/config/upgradeExperience.ts`
- 用 `scenario -> surface/path/source` 映射驱动 UI，不在业务组件硬编码跳转规则。

### 2.2 统一组件
- 新增 `apps/web/src/components/subscription/UpgradePromptModal.tsx`
- 统一视觉、按钮层级、交互行为（主 CTA + 次 CTA）。

### 2.3 已接入场景（第一批）
1. `ChatPanel`：AI 对话额度耗尽（`ERR_QUOTA_AI_CONVERSATIONS_EXCEEDED`）
2. `InspirationGrid`：灵感复制返回 `402` 配额错误

两处均接入统一 Modal，并带 `source` 参数进入 Billing/Pricing，便于后续漏斗分析。

### 2.4 已接入场景（第二批）
3. `SettingsDialog / SubscriptionStatus`：设置页订阅卡片新增主 CTA（升级）+ 次 CTA（兑换码）
4. `BillingPage`：Header 主 CTA 统一为升级方案（带 source），兑换码保留为次动作

## 3) 下一步建议
- 在 Billing/Pricing 读取 `source` 参数，补齐分场景转化漏斗看板。
- 将“80% 阈值提醒”纳入 `upgradeExperience` 配置，统一策略层。
- 把更多配额阻断点（素材上传、技能创建等）迁移到统一组件。
