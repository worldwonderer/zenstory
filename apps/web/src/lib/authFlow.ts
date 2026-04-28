export const PLAN_INTENTS = ["free", "pro"] as const;

export type PlanIntent = (typeof PLAN_INTENTS)[number];

const PLAN_INTENT_SET = new Set<string>(PLAN_INTENTS);

/**
 * Normalize plan intent query param into a known value.
 *
 * Unknown values are treated as null to avoid unsafe redirects.
 */
export function normalizePlanIntent(rawPlan: string | null | undefined): PlanIntent | null {
  if (!rawPlan) return null;
  const normalized = rawPlan.trim().toLowerCase();
  if (!PLAN_INTENT_SET.has(normalized)) return null;
  return normalized as PlanIntent;
}
