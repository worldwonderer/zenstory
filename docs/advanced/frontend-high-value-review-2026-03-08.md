# 前端高价值落地 QA / Review 记录（2026-03-08）

## 背景
针对「登录注册转化优化、商业化入口交互柔化（硬跳转改模态/过渡）、首屏体验与可用性修复」相关前端补丁，执行聚焦 QA 与代码评审。

## 评审范围（关键落地点）
- 首页与首屏转化：`apps/web/src/pages/HomePage.tsx`
- 登录/注册/验证链路：
  - `apps/web/src/pages/Login.tsx`
  - `apps/web/src/pages/Register.tsx`
  - `apps/web/src/pages/VerifyEmail.tsx`
  - `apps/web/src/lib/authFlow.ts`
- 商业化入口与归因：
  - `apps/web/src/pages/PricingPage.tsx`
  - `apps/web/src/config/upgradeExperience.ts`
  - `apps/web/src/components/subscription/UpgradePromptModal.tsx`
- 公共首屏导航可用性：`apps/web/src/components/PublicHeader.tsx`

## 验证结论
- 类型检查：通过
- 目标文件 Lint：通过
- 目标测试集：通过（8 files / 34 tests）
- 本轮未发现阻断发布的 P0 缺陷

## 本轮补充落地（PublicHeader 打开 AI 漫剧 token 传递稳定性）
- 已将 `PublicHeader` 中打开漫画站后的 token 传递从固定 `setTimeout(1000)` 改为握手/重试机制：
  - 首次发送 + 固定间隔重试（`postMessage`）
  - 收到 `ready`（`zenstory_READY` / `zenstory_AUTH_READY`）后立即再发送一次
  - 收到 `ack`（`zenstory_AUTH_ACK` / `zenstory_ACK`）后立即停止重试并清理监听器/定时器
  - 增加超时清理与组件卸载清理，避免监听器泄漏
- 已补齐 `PublicHeader` 相关测试：
  - 有 token：会重试发送并在 ack 后停止
  - 无 token：只打开新窗口，不发送认证消息
  - ready 信号：触发立即发送认证消息

## 本轮补充落地（VerifyEmail 转化入口 planIntent 透传）
- `VerifyEmail` 页面的回流入口已统一保持 `plan` 参数透传，避免付费链路丢失意图：
  - 正常验证码输入态「返回登录」
  - 缺失邮箱保护态「去注册」「返回登录」
- 补齐测试覆盖上述跳转行为，确保 `plan=pro/studio` 在页面回流时持续携带。

## 本轮补充落地（首页项目类型卡片 source 归因补齐）
- 首页 `project type card` 入口（示例：小说/短篇/剧本卡片）已补齐商业化归因参数：
  - 未登录 + 可注册：跳转 `/register?...&source=home_project_type_card`
  - 未登录 + 禁用注册：跳转 `/login?...&source=home_project_type_card`
- 同时保持 `plan` 参数透传，避免首页卡片入口在付费意图路径中丢失上下文。
- 卡片容器从 clickable `div` 升级为语义化 `button`，补齐键盘可达性与 `focus-visible` 高亮反馈。
- 补齐 `HomePage` 单测覆盖该入口在注册开启/关闭两种配置下的行为。

## 本轮补充落地（素材库卡片键盘可达性）
- 素材库列表卡片新增可访问交互语义：`role="button"` + `tabIndex=0` + `Enter/Space` 键盘触发详情跳转。
- 增加 `focus-visible` 焦点样式，提升键盘用户可见性与可操作性。
- 补齐 `MaterialsPage` 测试，验证键盘触发可正确进入素材详情页。

## 本轮补充落地（MaterialsPage.test.tsx act 警告清理）
- `MaterialsPage.test.tsx` 中上传与重试交互改为显式 `act(async () => ...)` 包裹，覆盖：
  - 打开上传弹窗
  - 触发文件选择 `change`
  - 点击确认上传
  - 点击失败素材「重试」
- 目标：消除 Vitest 输出中的 React `act(...)` 警告噪音，保持测试日志干净可读。
- 结果：`src/pages/__tests__/MaterialsPage.test.tsx` 运行通过且无 `act` warning 输出。

## 风险与建议（非阻断）
1. **首页 CTA source 归因覆盖（已处理）**
   - 首页关键入口（Hero、Pricing teaser、底部 CTA、项目类型卡片）已统一带 `source`，漏斗归因盲区已明显收敛。
   - 后续建议：继续细分 `source`（例如按卡片类型拆分）以支持更精细的商业化分析。

2. **跨站点 postMessage 固定延时风险（已修复）**
   - 原风险：`PublicHeader` 使用 `setTimeout(1000)` 单次发送 token，慢启动场景可能丢消息。
   - 当前状态：已替换为握手 + 重试 + 超时清理机制，本项从风险列表中下调为已处理项。

3. **验证码倒计时为前端本地计时**
   - `VerifyEmail` 的 TTL/cooldown 本地计时与服务端真实过期时刻可能存在偏差。
   - 建议：后端返回剩余秒数或过期时间戳并以前端显示对齐。

## 发布说明（建议）
- 已完成登录/注册计划意图透传（`plan` 参数）并在注册后验证、登录后跳转中保持一致。
- 商业化升级入口已形成「场景来源 -> Pricing/Billing」的基础归因链路。
- 首屏/导航/核心页面相关单测与 lint/typecheck 全部通过，回归风险可控。

## 本次执行的验证命令
```bash
cd apps/web && npx tsc --noEmit

cd apps/web && npx eslint \
  src/pages/HomePage.tsx \
  src/pages/PricingPage.tsx \
  src/pages/Login.tsx \
  src/pages/Register.tsx \
  src/pages/VerifyEmail.tsx \
  src/components/PublicHeader.tsx \
  src/components/subscription/UpgradePromptModal.tsx \
  src/config/upgradeExperience.ts \
  src/lib/authFlow.ts \
  src/pages/__tests__/HomePage.test.tsx \
  src/pages/__tests__/PricingPage.test.tsx \
  src/pages/__tests__/PricingPageAttribution.test.tsx \
  src/pages/__tests__/Register.test.tsx \
  src/pages/__tests__/VerifyEmail.test.tsx \
  src/components/__tests__/PublicHeader.test.tsx \
  src/lib/__tests__/authFlow.test.ts \
  src/config/__tests__/upgradeExperience.test.ts

cd apps/web && npm run test:run -- \
  src/pages/__tests__/HomePage.test.tsx \
  src/pages/__tests__/PricingPage.test.tsx \
  src/pages/__tests__/PricingPageAttribution.test.tsx \
  src/pages/__tests__/Register.test.tsx \
  src/pages/__tests__/VerifyEmail.test.tsx \
  src/components/__tests__/PublicHeader.test.tsx \
  src/lib/__tests__/authFlow.test.ts \
  src/config/__tests__/upgradeExperience.test.ts
```

## 本次补充修复验证命令（PublicHeader 专项）
```bash
cd apps/web && npx tsc --noEmit

cd apps/web && npx eslint \
  src/components/PublicHeader.tsx \
  src/components/__tests__/PublicHeader.test.tsx

cd apps/web && npm run test:run -- \
  src/components/__tests__/PublicHeader.test.tsx
```

## 本次补充修复验证命令（MaterialsPage act 警告专项）
```bash
cd apps/web && npx tsc --noEmit

cd apps/web && npx eslint \
  src/pages/__tests__/MaterialsPage.test.tsx

cd apps/web && npm run test:run -- \
  src/pages/__tests__/MaterialsPage.test.tsx
```
