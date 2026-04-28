import posthog from "posthog-js";
import logger from "./logger";
import type { User } from "../contexts/AuthContext";
import { parseEnvBoolean } from "../config/env";

export interface AnalyticsEnv {
  DEV: boolean;
  MODE?: string;
  VITE_POSTHOG_ENABLED?: string;
  VITE_POSTHOG_KEY?: string;
  VITE_POSTHOG_HOST?: string;
}

export type AnalyticsProperties = Record<string, unknown>;

interface AnalyticsInitStatus {
  enabled: boolean;
  hasKey: boolean;
  host: string;
  reason?: "disabled_flag" | "missing_key";
}

const DEFAULT_POSTHOG_HOST = "https://us.i.posthog.com";
const PAGE_VIEW_EVENT = "page_view";
const PAGEVIEW_DEDUPE_WINDOW_MS = 1000;

let isInitialized = false;
let lastPageViewKey: string | null = null;
let lastPageViewAt = 0;

declare global {
  interface Window {
    __zenstoryPosthog?: typeof posthog;
    __zenstoryAnalyticsStatus?: AnalyticsInitStatus;
  }
}

function isBrowser(): boolean {
  return typeof window !== "undefined";
}

export function isAnalyticsEnabled(env: AnalyticsEnv = import.meta.env): boolean {
  return parseEnvBoolean(env.VITE_POSTHOG_ENABLED, false) && Boolean(env.VITE_POSTHOG_KEY?.trim());
}

export function getAnalyticsHost(env: AnalyticsEnv = import.meta.env): string {
  return env.VITE_POSTHOG_HOST?.trim() || DEFAULT_POSTHOG_HOST;
}

function getCommonProperties(): AnalyticsProperties {
  if (!isBrowser()) return {};

  return {
    page_path: window.location.pathname,
    page_url: window.location.href,
    page_title: document.title,
    referrer: document.referrer || undefined,
    app_env: import.meta.env.MODE,
  };
}

function shouldSkipPageView(pageViewKey: string): boolean {
  const now = Date.now();
  const shouldSkip =
    lastPageViewKey === pageViewKey && now - lastPageViewAt < PAGEVIEW_DEDUPE_WINDOW_MS;

  lastPageViewKey = pageViewKey;
  lastPageViewAt = now;
  return shouldSkip;
}

function setAnalyticsStatus(status: AnalyticsInitStatus): void {
  if (isBrowser() && import.meta.env.DEV) {
    window.__zenstoryAnalyticsStatus = status;
  }
}

export function initAnalytics(env: AnalyticsEnv = import.meta.env): boolean {
  if (!isBrowser()) return false;
  if (isInitialized) return true;

  const enabledFlag = parseEnvBoolean(env.VITE_POSTHOG_ENABLED, false);
  const apiKey = env.VITE_POSTHOG_KEY?.trim();
  if (!enabledFlag) {
    const status = {
      enabled: false,
      hasKey: Boolean(apiKey),
      host: getAnalyticsHost(env),
      reason: "disabled_flag" as const,
    };
    setAnalyticsStatus(status);
    logger.info("[analytics] PostHog disabled", {
      reason: status.reason,
      enabled_flag: env.VITE_POSTHOG_ENABLED ?? null,
      has_key: status.hasKey,
    });
    return false;
  }
  if (!apiKey) {
    const status = {
      enabled: false,
      hasKey: false,
      host: getAnalyticsHost(env),
      reason: "missing_key" as const,
    };
    setAnalyticsStatus(status);
    logger.warn("[analytics] PostHog disabled", {
      reason: status.reason,
    });
    return false;
  }

  posthog.init(
    apiKey,
    {
      api_host: getAnalyticsHost(env),
      defaults: "2026-01-30",
      internal_or_test_user_hostname: undefined,
      person_profiles: "identified_only",
      autocapture: false,
      capture_pageview: false,
      disable_session_recording: true,
      request_batching: !env.DEV,
    } as unknown as Parameters<typeof posthog.init>[1]
  );
  posthog.startExceptionAutocapture();
  isInitialized = true;
  setAnalyticsStatus({
    enabled: true,
    hasKey: true,
    host: getAnalyticsHost(env),
  });
  if (env.DEV && isBrowser()) {
    window.__zenstoryPosthog = posthog;
  }

  logger.info("[analytics] PostHog initialized", {
    host: getAnalyticsHost(env),
  });

  return true;
}

export function trackEvent(eventName: string, properties: AnalyticsProperties = {}): void {
  if (!isInitialized || !isBrowser()) return;
  const normalizedEventName = eventName.trim();
  if (!normalizedEventName) return;

  posthog.capture(normalizedEventName, {
    ...getCommonProperties(),
    ...properties,
  });
}

export function trackPageView(properties: AnalyticsProperties = {}): void {
  if (!isInitialized || !isBrowser()) return;

  const pageViewKey = `${window.location.pathname}${window.location.search}${window.location.hash}`;
  if (shouldSkipPageView(pageViewKey)) return;

  trackEvent(PAGE_VIEW_EVENT, {
    path: window.location.pathname,
    search: window.location.search || undefined,
    hash: window.location.hash || undefined,
    ...properties,
  });
}

export function identifyUser(user: Pick<User, "id" | "email" | "username" | "is_superuser">): void {
  if (!isInitialized) return;

  posthog.identify(user.id, {
    is_superuser: user.is_superuser,
  });
}

export function resetAnalytics(): void {
  if (!isInitialized) return;

  posthog.reset(true);
  lastPageViewKey = null;
  lastPageViewAt = 0;
}

export function captureException(
  error: unknown,
  additionalProperties: AnalyticsProperties = {}
): void {
  if (!isInitialized) return;

  posthog.captureException(error, {
    ...getCommonProperties(),
    ...additionalProperties,
  });
}
