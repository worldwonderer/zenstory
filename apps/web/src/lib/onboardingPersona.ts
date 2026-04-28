export const PERSONA_ONBOARDING_STORAGE_KEY_PREFIX = 'zenstory_onboarding_persona_v1';
const PERSONA_ONBOARDING_ROLLOUT_AT = Date.parse('2026-03-05T16:00:00Z');
const PERSONA_ONBOARDING_NEW_USER_WINDOW_MS = 7 * 24 * 60 * 60 * 1000;

export type PersonaExperienceLevel = 'beginner' | 'intermediate' | 'advanced';

export interface PersonaOnboardingData {
  version: 1;
  completed_at: string;
  selected_personas: string[];
  selected_goals: string[];
  experience_level: PersonaExperienceLevel;
  skipped: boolean;
}

export interface PersonaOnboardingGateUser {
  id: string;
  created_at?: string | null;
}

const buildStorageKey = (userId: string): string =>
  `${PERSONA_ONBOARDING_STORAGE_KEY_PREFIX}:${userId}`;

const isStringArray = (value: unknown): value is string[] =>
  Array.isArray(value) && value.every((item) => typeof item === 'string');

const isExperienceLevel = (value: unknown): value is PersonaExperienceLevel =>
  value === 'beginner' || value === 'intermediate' || value === 'advanced';

export const getPersonaOnboardingData = (userId: string): PersonaOnboardingData | null => {
  if (!userId) return null;

  try {
    const raw = localStorage.getItem(buildStorageKey(userId));
    if (!raw) return null;

    const parsed = JSON.parse(raw) as Partial<PersonaOnboardingData>;

    if (
      parsed.version !== 1 ||
      typeof parsed.completed_at !== 'string' ||
      !isStringArray(parsed.selected_personas) ||
      !isStringArray(parsed.selected_goals) ||
      !isExperienceLevel(parsed.experience_level) ||
      typeof parsed.skipped !== 'boolean'
    ) {
      return null;
    }

    return parsed as PersonaOnboardingData;
  } catch {
    return null;
  }
};

export const hasCompletedPersonaOnboarding = (userId: string): boolean =>
  Boolean(getPersonaOnboardingData(userId));

const hasExplicitTimezone = (value: string): boolean =>
  /([zZ]|[+-]\d{2}:?\d{2})$/.test(value.trim());

const parseCreatedAtTimestamp = (createdAt: string): number | null => {
  const trimmed = createdAt.trim();
  if (!trimmed) return null;

  // Backend may return naive UTC timestamps (e.g. "2026-03-11T09:00:00") without timezone suffix.
  // Date.parse(...) treats such values as *local* time which can become "future" timestamps in UTC-
  // timezones and incorrectly skip onboarding. Treat missing timezone as UTC.
  const normalized = hasExplicitTimezone(trimmed) ? trimmed : `${trimmed}Z`;

  const timestamp = Date.parse(normalized);
  if (!Number.isFinite(timestamp)) return null;
  return timestamp;
};

const isNewUserAfterRollout = (createdAt: string | null | undefined): boolean => {
  if (!createdAt) return false;

  const createdTimestamp = parseCreatedAtTimestamp(createdAt);
  if (createdTimestamp === null) return false;

  if (createdTimestamp < PERSONA_ONBOARDING_ROLLOUT_AT) return false;

  const accountAge = Date.now() - createdTimestamp;
  return accountAge >= 0 && accountAge <= PERSONA_ONBOARDING_NEW_USER_WINDOW_MS;
};

export const shouldRequirePersonaOnboarding = (
  user: PersonaOnboardingGateUser | null | undefined
): boolean => {
  if (!user?.id) return false;
  if (hasCompletedPersonaOnboarding(user.id)) return false;

  return isNewUserAfterRollout(user.created_at);
};

export const savePersonaOnboardingData = (
  userId: string,
  data: Omit<PersonaOnboardingData, 'version' | 'completed_at'>
): PersonaOnboardingData | null => {
  if (!userId) return null;

  const payload: PersonaOnboardingData = {
    version: 1,
    completed_at: new Date().toISOString(),
    selected_personas: data.selected_personas,
    selected_goals: data.selected_goals,
    experience_level: data.experience_level,
    skipped: data.skipped,
  };

  try {
    localStorage.setItem(buildStorageKey(userId), JSON.stringify(payload));
    return payload;
  } catch {
    return null;
  }
};
