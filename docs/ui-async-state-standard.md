# Async Data UI 标准（2026-03）

## 背景问题

多个页面在首屏或后台刷新期间，会短暂展示“空数据占位”，随后又切换到真实列表，形成明显闪烁（Empty → List）。

## 新标准（统一执行）

1. **加载优先（Loading-first）**
   - 正在拉取数据时，不展示空态文案。
   - 特别是 `isFetching && isEmpty` 场景，统一显示加载态。

2. **空态仅在“稳定为空”时出现**
   - 仅当请求结束且确实为空，再展示空态。
   - 避免后台刷新期间空态和内容来回切换。

3. **列表区域优先骨架化**
   - 关键页面列表区使用骨架/Spinner，减少布局跳变和视觉闪烁。

4. **按场景区分空态**
   - “未查询用户 / 未选择条件”与“查询结果为空”语义分离，不混用。

## 本次改造覆盖清单

### 通用组件层
- `apps/web/src/components/admin/AdminPageState.tsx`
  - 新增 `isFetching` 支持
  - 统一为 `isLoading || (isFetching && isEmpty)` 时展示加载态
  - 升级加载态视觉（Spinner + 文案）

### Admin 页面（全量接入 isFetching）
- `AdminDashboard.tsx`
- `UserManagement.tsx`
- `CodeManagement.tsx`
- `PromptManagement.tsx`
- `InspirationManagement.tsx`
- `SubscriptionPlanManagement.tsx`
- `FeedbackManagement.tsx`
- `AuditLogPage.tsx`
- `SubscriptionManagement.tsx`
- `ReferralManagement.tsx`
- `CheckInStatsPage.tsx`
- `QuotaManagement.tsx`
- `PointsManagement.tsx`

### Dashboard / 业务页面
- `DashboardHome.tsx`
  - 项目列表增加 `projectsLoading` 骨架态
  - 精选灵感改为 `isLoading || (isFetching && 空列表)` 时展示骨架
- `BillingPage.tsx`
  - 套餐对比区新增 Catalog pending 骨架，避免“暂无数据”闪现
- `SkillsPage.tsx`
  - 我的技能区新增 `hasLoadedMySkills`，首轮请求前不再直接渲染空态

### Hook 能力
- `useInspirations.ts`
  - `useFeaturedInspirations` 返回 `isFetching`，支持页面做稳定态判断

---

该标准后续可作为所有“列表页/表格页/卡片页”接入规范。
