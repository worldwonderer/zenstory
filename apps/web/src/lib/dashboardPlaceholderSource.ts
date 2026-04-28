import { logger } from "./logger";

export const DASHBOARD_PLACEHOLDER_VERSION = 1;

const SUPPORTED_TYPES = ["novel", "short", "screenplay"] as const;
const SUPPORTED_LOCALES = ["zh", "en"] as const;

type SupportedType = (typeof SUPPORTED_TYPES)[number];
export type DashboardPlaceholderLocale = (typeof SUPPORTED_LOCALES)[number];

export interface DashboardPlaceholderFilePayload {
  version: number;
  locale: DashboardPlaceholderLocale;
  generated_at: string;
  placeholders: Record<SupportedType, string[]>;
}

export interface DashboardPlaceholderBundle {
  locale: DashboardPlaceholderLocale;
  placeholders: Record<SupportedType, string[]>;
}

const placeholderCache = new Map<DashboardPlaceholderLocale, Promise<DashboardPlaceholderBundle | null>>();

export function normalizeDashboardPlaceholderLocale(language: string | undefined): DashboardPlaceholderLocale {
  const normalized = (language ?? "").toLowerCase();
  if (normalized.startsWith("en")) {
    return "en";
  }
  return "zh";
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function isSupportedLocale(value: unknown): value is DashboardPlaceholderLocale {
  return typeof value === "string" && (SUPPORTED_LOCALES as readonly string[]).includes(value);
}

function sanitizePlaceholders(payload: unknown): DashboardPlaceholderBundle | null {
  if (!payload || typeof payload !== "object") {
    return null;
  }

  const candidate = payload as Partial<DashboardPlaceholderFilePayload>;

  if (candidate.version !== DASHBOARD_PLACEHOLDER_VERSION || !isSupportedLocale(candidate.locale)) {
    return null;
  }

  if (!candidate.placeholders || typeof candidate.placeholders !== "object") {
    return null;
  }

  const normalized: Record<SupportedType, string[]> = {
    novel: [],
    short: [],
    screenplay: [],
  };

  for (const type of SUPPORTED_TYPES) {
    const values = (candidate.placeholders as Record<string, unknown>)[type];
    if (!Array.isArray(values)) {
      return null;
    }
    const cleaned = values.filter(isNonEmptyString).map((entry) => entry.trim());
    if (cleaned.length === 0) {
      return null;
    }
    normalized[type] = cleaned;
  }

  return {
    locale: candidate.locale,
    placeholders: normalized,
  };
}

async function fetchDashboardPlaceholderBundle(locale: DashboardPlaceholderLocale): Promise<DashboardPlaceholderBundle | null> {
  const fileName = `dashboard-placeholders.v${DASHBOARD_PLACEHOLDER_VERSION}.${locale}.json`;
  const path = `/generated/${fileName}`;

  try {
    const response = await fetch(path, { cache: "no-store" });
    if (!response.ok) {
      logger.warn("Dashboard placeholder file unavailable", { locale, status: response.status, path });
      return null;
    }

    const data: unknown = await response.json();
    const sanitized = sanitizePlaceholders(data);
    if (!sanitized) {
      logger.warn("Dashboard placeholder file validation failed", { locale, path });
      return null;
    }
    if (sanitized.locale !== locale) {
      logger.warn("Dashboard placeholder locale mismatch", {
        requestedLocale: locale,
        payloadLocale: sanitized.locale,
        path,
      });
      return null;
    }

    return sanitized;
  } catch (error) {
    logger.warn("Dashboard placeholder file load failed", { locale, path, error });
    return null;
  }
}

export function loadDashboardPlaceholderBundle(locale: DashboardPlaceholderLocale): Promise<DashboardPlaceholderBundle | null> {
  const cached = placeholderCache.get(locale);
  if (cached) {
    return cached;
  }

  const request = fetchDashboardPlaceholderBundle(locale);
  placeholderCache.set(locale, request);
  return request;
}
