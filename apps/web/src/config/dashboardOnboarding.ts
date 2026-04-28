import { parseEnvBoolean } from "./env";

/**
 * Dashboard onboarding / guidance feature flags.
 *
 * Defaults are disabled (false) so these panels stay dark-launched until
 * product explicitly re-enables them in a given environment via Vite env vars:
 * - VITE_DASHBOARD_TODAY_ACTION_PLAN_ENABLED
 * - VITE_DASHBOARD_FIRST_DAY_ACTIVATION_GUIDE_ENABLED
 * - VITE_DASHBOARD_COACHMARK_TOUR_ENABLED
 */
export const dashboardOnboardingFlags = {
  todayActionPlanEnabled: parseEnvBoolean(
    import.meta.env.VITE_DASHBOARD_TODAY_ACTION_PLAN_ENABLED,
    false,
  ),
  firstDayActivationGuideEnabled: parseEnvBoolean(
    import.meta.env.VITE_DASHBOARD_FIRST_DAY_ACTIVATION_GUIDE_ENABLED,
    false,
  ),
  coachmarkTourEnabled: parseEnvBoolean(
    import.meta.env.VITE_DASHBOARD_COACHMARK_TOUR_ENABLED,
    false,
  ),
};
