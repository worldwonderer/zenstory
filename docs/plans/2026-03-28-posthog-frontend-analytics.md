# PostHog Frontend Analytics Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add PostHog-backed frontend analytics to the web app with route tracking, auth identify/reset, exception capture, and key business events.

**Architecture:** Introduce a thin analytics wrapper over `posthog-js`, initialize it at bootstrap, instrument route/auth/error integration centrally, and dual-write existing upgrade funnel events to PostHog while preserving backend analytics.

**Tech Stack:** React 19, Vite 7, TypeScript, Vitest, React Router 7, posthog-js

---

### Task 1: Add analytics dependency and configuration

**Files:**
- Modify: `apps/web/package.json`
- Modify: `apps/web/.env.example`

**Steps:**
1. Add `posthog-js` dependency.
2. Add PostHog env keys to the example env file.
3. Keep replay disabled by default and host configurable.

### Task 2: Add analytics wrapper and root initialization

**Files:**
- Create: `apps/web/src/lib/analytics.ts`
- Modify: `apps/web/src/main.tsx`

**Steps:**
1. Implement safe no-op behavior when env is disabled or key is missing.
2. Initialize PostHog with direct cloud host and exception autocapture.
3. Expose track/identify/reset/exception/page-view helpers.

### Task 3: Track route changes and auth lifecycle

**Files:**
- Create: `apps/web/src/components/RouteChangeTracker.tsx`
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/contexts/AuthContext.tsx`

**Steps:**
1. Add a route-aware component that emits page view events.
2. Mount the tracker under `BrowserRouter`.
3. Identify authenticated users after login/session restore.
4. Reset PostHog on logout.

### Task 4: Integrate business events and upgrade funnel dual-write

**Files:**
- Modify: `apps/web/src/lib/upgradeAnalytics.ts`
- Modify: selected high-value pages/components for minimal event coverage

**Steps:**
1. Reuse existing upgrade event semantics.
2. Send PostHog events alongside the existing backend queue.
3. Add a small number of high-value app events without sensitive payloads.

### Task 5: Add tests and verify

**Files:**
- Create/modify: `apps/web/src/lib/__tests__/*`
- Create/modify: route/auth integration tests as needed

**Steps:**
1. Add wrapper tests with mocked `posthog-js`.
2. Add route tracking and auth identify/reset coverage where practical.
3. Run targeted tests, lint, and build/typecheck.
