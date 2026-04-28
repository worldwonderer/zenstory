# Materials Paid Entitlements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Turn Materials Library into a paid-member feature with free-user teaser access, paid-user full workspace access, and a 5-per-month material decomposition quota.

**Architecture:** Move materials access from plan-name hardcoding to entitlement + quota semantics. Split “feature not included” from “quota exhausted” all the way through backend API, frontend state, and subscription/billing surfaces. Keep the user-facing unit singular: 素材拆解次数.

**Tech Stack:** FastAPI + SQLModel backend, React + TanStack Query + Vitest frontend, markdown docs under `docs/`.

---

### Task 1: Fix backend source-of-truth entitlements

**Files:**
- Modify: `apps/server/services/subscription/defaults.py`
- Modify: `apps/server/api/subscription.py`
- Test: `apps/server/tests/test_api/test_subscription.py`
- Test: `apps/server/tests/test_api/test_subscription_plans_catalog.py`

**Step 1: Write failing tests for free=0 / paid=5**

Add assertions that:
- free catalog tier shows `material_decompositions_monthly = 0`
- paid tier shows `material_decompositions_monthly = 5`

**Step 2: Run tests to verify they fail**

Run:

```bash
cd apps/server
.venv/bin/pytest \
  tests/test_api/test_subscription.py \
  tests/test_api/test_subscription_plans_catalog.py -q
```

**Step 3: Implement minimal config changes**

- set free material decompositions to `0`
- set paid material decompositions to `5`
- add `materials_library_access` to the normalized entitlement response

**Step 4: Run tests to verify they pass**

Run the same command and confirm PASS.

### Task 2: Remove hardcoded paid unlimited bypass

**Files:**
- Modify: `apps/server/core/permissions.py`
- Modify: `apps/server/services/quota_service.py`
- Test: `apps/server/tests/test_services/test_quota_service.py`

**Step 1: Write failing tests**

Add tests proving:
- paid users are governed by configured quota values
- logic no longer branches on `plan.name == "pro"`

**Step 2: Run tests to verify failure**

```bash
cd apps/server
.venv/bin/pytest tests/test_services/test_quota_service.py -q
```

**Step 3: Implement minimal backend logic**

- replace plan-name bypass with entitlement/quota-driven checks
- preserve unlimited behavior only when a limit is explicitly `-1`

**Step 4: Re-run tests**

Expect PASS.

### Task 3: Split feature-not-included vs quota-exhausted

**Files:**
- Modify: `apps/server/core/error_codes.py`
- Modify: `apps/server/core/permissions.py`
- Modify: `apps/server/api/materials/upload.py`
- Test: `apps/server/tests/test_api/test_materials.py`
- Test: `apps/server/tests/test_api/test_materials_retry.py`

**Step 1: Write failing tests**

Add coverage for:
- free upload/retry → `ERR_FEATURE_NOT_INCLUDED`
- paid sixth attempt → `ERR_QUOTA_EXCEEDED`

**Step 2: Run tests**

```bash
cd apps/server
.venv/bin/pytest \
  tests/test_api/test_materials.py \
  tests/test_api/test_materials_retry.py -q
```

**Step 3: Implement minimal logic**

- introduce / wire `ERR_FEATURE_NOT_INCLUDED`
- keep `ERR_QUOTA_EXCEEDED` for paid exhaustion only

**Step 4: Re-run tests**

Expect PASS.

### Task 4: Lock charging semantics for upload / decompose / retry

**Files:**
- Modify: `apps/server/api/materials/upload.py`
- Modify: `apps/server/services/quota_service.py`
- Test: `apps/server/tests/test_api/test_materials.py`
- Test: `apps/server/tests/test_api/test_materials_retry.py`

**Step 1: Write failing tests**

Cover:
- consume 1 count when effective decomposition job is created
- compensatory retry after system failure does not double-charge

**Step 2: Run tests**

Use the same backend materials test command.

**Step 3: Implement minimal logic**

- centralize the charging point
- document retry compensation assumptions inline

**Step 4: Re-run tests**

Expect PASS.

### Task 5: Add free teaser state to MaterialsPage

**Files:**
- Modify: `apps/web/src/pages/MaterialsPage.tsx`
- Test: `apps/web/src/pages/__tests__/MaterialsPage.test.tsx`

**Step 1: Write failing UI tests**

Add tests that free users:
- see teaser content
- see upgrade CTA
- do not see a real usable workspace state

**Step 2: Run tests**

```bash
cd apps/web
pnpm exec vitest run src/pages/__tests__/MaterialsPage.test.tsx
```

**Step 3: Implement minimal UI state split**

- branch page rendering into free teaser vs paid workspace
- reuse existing upgrade modal patterns where possible

**Step 4: Re-run tests**

Expect PASS.

### Task 6: Implement paid remaining-count and exhausted state

**Files:**
- Modify: `apps/web/src/pages/MaterialsPage.tsx`
- Possibly modify: `apps/web/src/lib/subscriptionApi.ts`
- Test: `apps/web/src/pages/__tests__/MaterialsPage.test.tsx`

**Step 1: Write failing tests**

Add tests that paid users:
- see `本月剩余 X / 5`
- on exhaustion see restore messaging
- do not get an upgrade modal

**Step 2: Run tests**

```bash
cd apps/web
pnpm exec vitest run src/pages/__tests__/MaterialsPage.test.tsx
```

**Step 3: Implement minimal state handling**

- map `ERR_QUOTA_EXCEEDED` to exhausted UX
- keep browse-only access for existing materials

**Step 4: Re-run tests**

Expect PASS.

### Task 7: Update pricing / billing entitlement copy

**Files:**
- Modify: `apps/web/src/lib/subscriptionEntitlements.ts`
- Modify: `apps/web/src/types/subscription.ts`
- Modify: `apps/web/src/pages/PricingPage.tsx`
- Test: `apps/web/src/pages/__tests__/PricingPage.test.tsx`

**Step 1: Write failing tests**

Ensure:
- free shows `0 次/月`
- paid shows `5 次/月`
- wording is “素材拆解次数”

**Step 2: Run tests**

```bash
cd apps/web
pnpm exec vitest run src/pages/__tests__/PricingPage.test.tsx
```

**Step 3: Implement minimal copy / type updates**

Update entitlement formatting and display labels.

**Step 4: Re-run tests**

Expect PASS.

### Task 8: Add docs + analytics

**Files:**
- Modify: `docs/user-guide/materials.md`
- Modify: `docs/user-guide/billing-benefits.md`
- Modify: `docs/reference/faq.md`
- Modify: `apps/web/src/pages/MaterialsPage.tsx`

**Step 1: Update docs**

Document:
- free teaser-only access
- paid 5 times/month
- exhausted users recover next month

**Step 2: Add frontend event hooks**

At minimum:
- `materials_teaser_exposed`
- `materials_upgrade_clicked`
- `materials_upload_blocked_free`
- `materials_quota_exhausted_paid`
- `materials_decompose_started`

**Step 3: Verify manually**

- open free teaser
- click upgrade CTA
- exhaust paid quota

### Task 9: Full regression run

**Files:**
- No code change required; verification only

**Step 1: Run backend suite**

```bash
cd apps/server && .venv/bin/pytest \
  tests/test_services/test_quota_service.py \
  tests/test_api/test_subscription.py \
  tests/test_api/test_subscription_plans_catalog.py \
  tests/test_api/test_materials.py \
  tests/test_api/test_materials_retry.py -q
```

**Step 2: Run frontend suite**

```bash
cd apps/web && pnpm exec vitest run \
  src/pages/__tests__/MaterialsPage.test.tsx \
  src/pages/__tests__/PricingPage.test.tsx
```

**Step 3: Manual smoke check**

- free teaser flow
- paid first successful decomposition
- paid sixth blocked attempt
- pricing/billing copy consistency
