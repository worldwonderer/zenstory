# E2E Lane Governance — 2026-04

这份文档是当前 zenstory E2E 的**维护者视角治理说明**，目标不是再解释如何跑测试，而是回答：

- 现在哪些 lane 是 release signal
- 每条 lane 背后有哪些 focused server contract 在兜底
- 什么 suite 值得 promotion，什么不值得
- 收尾阶段还剩哪些缺口值得继续补

> 当前结论：default / nightly 背后的高价值 backend contract 基本已经收口，接下来应以治理、稳定性数据和 promotion 纪律为主，而不是继续无边界扩面。

---

## 1. 当前 lane 拆分

| Lane | 角色 | 当前内容 |
| --- | --- | --- |
| `smoke` | 最快 release signal | 登录、项目进入、基础文件树/对话可用 |
| `default` | PR required 主门禁 | auth / session / projects / points / onboarding-persona / public-skills / referral / security / subscription / settings / settings-regression / smoke |
| `nightly` | 成本更高但高价值回归 | versions / skills / skills-flow |
| `release` | 昂贵或环境敏感信号 | visual / performance / large-document / concurrent / voice interaction |
| `full` | 手工 / 分支级总回归 | 所有当前自动化入口 |

---

## 2. 当前 focused server contract 映射

这些 focused contract 的意义是：**浏览器 suite 不再是唯一保护这些后端面的地方**。

| Web 依赖面 | Focused server contract |
| --- | --- |
| auth / session / projects / smoke | `apps/server/tests/e2e/test_auth_projects_contract_e2e.py` |
| versions | `apps/server/tests/e2e/test_versions_contract_e2e.py` |
| subscription / quota / redeem / voice | `apps/server/tests/e2e/test_subscription_voice_contract_e2e.py` |
| billing catalog / public-skills | `apps/server/tests/e2e/test_billing_public_skills_contract_e2e.py` |
| points | `apps/server/tests/e2e/test_points_contract_e2e.py` |
| skills | `apps/server/tests/e2e/test_skills_contract_e2e.py` |
| materials library | `apps/server/tests/e2e/test_materials_contract_e2e.py` |

### 现在的判断

对于当前 `default` / `nightly` 主链路来说，上表已经覆盖了绝大多数高价值 backend surface。

换句话说：

- **再继续补 focused contract 的收益已经明显下降**
- 继续扩面前，应该先问：这个 surface 是不是当前 lane 真依赖、而且还没有 focused contract？

---

## 3. Promotion 纪律

### opt-in → nightly

必须同时满足：

1. 连续 7 天 green
2. failure rate < 5%
3. 无人工步骤
4. clean environment 可复现
5. 对应 backend contract 已存在，或明确说明不需要

### nightly → default

必须同时满足：

1. 连续 14 天 green
2. failure rate < 1%
3. fits PR runtime budget
4. 不依赖不稳定外部服务 / 录音 / baseline 人工维护
5. 失败可诊断、可复现、可 owner 化

---

## 4. Failure triage 纪律

以后遇到失败，先归类，不要直接改代码。

### A. Runner / Infra
例：
- GitHub Actions 秒失败
- 账户 billing / spending limit
- browser install / runner image 问题

处理：
- 先跑 `scripts/ci/diagnose-gha-failfast.sh <run-id>`
- 没有 runner 真开始执行，就不要按代码回归处理

### B. Backend contract
例：
- response shape 变化
- quota / status / catalog / list semantics 漂移

处理：
- 先看 focused server e2e 是否已失败
- 如果 server contract 已失败，优先修后端或更新契约

### C. Browser interaction / wait / selector
例：
- strict mode violation
- post-click waitForResponse race
- duplicated text / selector 太宽

处理：
- 优先收窄 selector
- 先注册 waiter 再 click
- 尽量对 rendered state 断言，而不是只盯网络

### D. 特殊信号 / 环境敏感
例：
- visual baseline
- voice 录音链路
- performance

处理：
- 默认不升主门禁
- 单独统计稳定性，不要污染 default 判断

---

## 5. 当前还值得补什么

### 高优先级：治理，不是扩面

当前最值得做的不是再补更多 contract，而是把已有体系治理好：

1. 固化 lane owner
2. 固化 promotion checklist
3. 固化 flaky 分类方式
4. 保持 focused contract ↔ browser lane 对照表同步

### 中优先级：只有在准备 promotion 时才补

以下 surface **只有在对应 browser suite 准备升权重时**才值得补：

- project dashboard / writing stats
- materials batch-import 的更细 contract
- file-search 之外的新文件树交互 contract
- chat 里更细的非流式 UI contract

### 低优先级：暂不建议继续补

- visual
- performance
- large-document
- real voice interaction

原因：
- 这些主要瓶颈不是 backend contract 不足
- 而是 baseline / 环境 / 成本 / 运行时稳定性

---

## 6. 目前不值得做的事

以下事情现在不建议做：

1. **把 opt-in suite 直接拉进 default**
2. **为了“覆盖率好看”而继续补低 ROI contract**
3. **把 focused contract 文件重新并回大而全 e2e**
4. **在 GitHub billing 未恢复前，用 hosted failure 误判为代码回归**

---

## 7. 当前 hosted-runner 状态

当前状态需要分成两层看：

### 已完成的真机证明

`Zenstory Browser Lanes` 已经有过一次**真正成功的 hosted-runner 证明**：

- success run: `24024210090`

这说明：

- `default` / `nightly` 的 lane 设计本身是可在 GitHub-hosted runner 上跑通的
- 当前 lane 体系不是“只在本地绿”的状态

### 当前的 infra blocker

在此之后，新的 dedicated reruns 多次出现“秒失败未启动”的情况，原因明确为：

- GitHub Actions account billing / spending limit

也就是说：

- 这是**新的 hosted rerun blocker**
- 不是对前面成功真机证明的推翻
- 也不应被当成代码回归

这类失败的处理原则：

- 记录为 infra blocker
- 标注“job not started”
- 不作为代码失败统计
- billing 恢复后，再决定是否补做最新分支的 hosted rerun

---

## 8. 收尾判定

可以认为当前 E2E modernization 已进入“收尾阶段”，当以下条件成立时可收口：

1. `default` / `nightly` lane 定义稳定
2. lane-facing focused server contracts 已覆盖主链路
3. 已有至少一次成功的 hosted-runner 证明；后续 rerun 若被 billing 阻断，单独记录为 infra 问题
4. 剩余缺口明确标注为：
   - opt-in
   - lower priority
   - governance backlog

如果继续投入，优先级应是：

1. lane 治理
2. billing 恢复后的 hosted rerun（可选但有价值）
3. promotion 数据积累

而不是继续无差别扩测试面。
