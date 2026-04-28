import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  loadDashboardPlaceholderBundle,
  normalizeDashboardPlaceholderLocale,
} from "../lib/dashboardPlaceholderSource";

const SUPPORTED_TYPES = ["novel", "short", "screenplay"] as const;
type SupportedType = (typeof SUPPORTED_TYPES)[number];

function isSupportedType(value: string): value is SupportedType {
  return (SUPPORTED_TYPES as readonly string[]).includes(value);
}

function pickCandidate(candidates: string[], type: SupportedType): string | null {
  if (candidates.length === 0) {
    return null;
  }
  const daySeed = Math.floor(Date.now() / 86_400_000);
  const index = Math.abs(daySeed + type.length) % candidates.length;
  return candidates[index] ?? candidates[0] ?? null;
}

export function useDashboardPlaceholders(activeTab: string, fallbackPlaceholder: string): string {
  const { i18n } = useTranslation();

  const locale = useMemo(
    () => normalizeDashboardPlaceholderLocale(i18n.resolvedLanguage ?? i18n.language),
    [i18n.language, i18n.resolvedLanguage],
  );
  const selectionKey = `${locale}:${activeTab}:${fallbackPlaceholder}`;

  const [asyncPlaceholder, setAsyncPlaceholder] = useState<{ key: string; value: string } | null>(null);

  useEffect(() => {
    if (!isSupportedType(activeTab)) {
      return;
    }

    let cancelled = false;

    void loadDashboardPlaceholderBundle(locale).then((bundle) => {
      if (cancelled || !bundle) {
        return;
      }

      const candidate = pickCandidate(bundle.placeholders[activeTab], activeTab);
      if (!candidate) {
        return;
      }

      setAsyncPlaceholder({ key: selectionKey, value: candidate });
    });

    return () => {
      cancelled = true;
    };
  }, [activeTab, locale, selectionKey]);

  if (asyncPlaceholder?.key === selectionKey) {
    return asyncPlaceholder.value;
  }

  return fallbackPlaceholder;
}
