# PostHog Frontend Analytics Design

## Goal

Add a minimal, production-safe frontend analytics layer to `apps/web` using direct PostHog Cloud in phase 1.

## Why this approach

The fastest way to gain behavior visibility is to connect the web app directly to PostHog Cloud. To avoid future lock-in and reduce business-code churn, PostHog calls will be wrapped in a small local analytics module instead of being scattered across the app.

## Architecture

- Add `posthog-js`
- Create `src/lib/analytics.ts` as the app-facing wrapper
- Initialize PostHog at app bootstrap
- Track page views from a route-aware React component
- Identify/reset users from auth lifecycle events
- Capture exceptions both automatically and manually
- Keep replay disabled by default
- Dual-write upgrade funnel events to the existing backend path and PostHog

## Privacy boundaries

Allowed:
- ids
- page paths
- destinations
- action names
- non-sensitive metadata

Forbidden:
- prompt text
- editor content
- uploaded file contents
- arbitrary user-generated text bodies

## Phase 1 event scope

- `page_view`
- auth lifecycle events
- key business events around project/file/chat flows
- upgrade funnel events
- frontend exceptions

## Rollout notes

- Environment variables control enablement and host/key
- Default host points at PostHog Cloud
- The wrapper keeps later migration to a reverse proxy or backend relay low-cost

