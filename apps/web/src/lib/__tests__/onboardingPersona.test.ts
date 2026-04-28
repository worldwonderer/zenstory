import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  getPersonaOnboardingData,
  PERSONA_ONBOARDING_STORAGE_KEY_PREFIX,
  savePersonaOnboardingData,
  shouldRequirePersonaOnboarding,
} from "../onboardingPersona";

const NOW = Date.parse("2026-03-06T16:00:00Z");

describe("onboardingPersona gate", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(Date, "now").mockReturnValue(NOW);
    localStorage.clear();
  });

  it("requires onboarding for newly registered users within rollout window", () => {
    const shouldShow = shouldRequirePersonaOnboarding({
      id: "user-new",
      created_at: "2026-03-06T08:00:00Z",
    });

    expect(shouldShow).toBe(true);
  });

  it("treats naive created_at timestamps (missing timezone suffix) as UTC", () => {
    const parseSpy = vi.spyOn(Date, "parse");

    const shouldShow = shouldRequirePersonaOnboarding({
      id: "user-new-naive",
      created_at: "2026-03-06T08:00:00",
    });

    expect(shouldShow).toBe(true);
    expect(parseSpy).toHaveBeenCalledWith("2026-03-06T08:00:00Z");
  });

  it("does not require onboarding for users created before rollout date", () => {
    const shouldShow = shouldRequirePersonaOnboarding({
      id: "user-old",
      created_at: "2026-03-01T08:00:00Z",
    });

    expect(shouldShow).toBe(false);
  });

  it("does not require onboarding for users outside new-user time window", () => {
    const shouldShow = shouldRequirePersonaOnboarding({
      id: "user-not-new",
      created_at: "2026-02-20T08:00:00Z",
    });

    expect(shouldShow).toBe(false);
  });

  it("does not require onboarding after data has been saved", () => {
    savePersonaOnboardingData("user-completed", {
      selected_personas: ["explorer"],
      selected_goals: ["finishBook"],
      experience_level: "beginner",
      skipped: false,
    });

    const shouldShow = shouldRequirePersonaOnboarding({
      id: "user-completed",
      created_at: "2026-03-06T08:00:00Z",
    });

    expect(shouldShow).toBe(false);
  });

  it("treats malformed saved payload as incomplete and still shows onboarding", () => {
    localStorage.setItem(
      `${PERSONA_ONBOARDING_STORAGE_KEY_PREFIX}:user-malformed`,
      JSON.stringify({
        version: 1,
        completed_at: "2026-03-06T09:00:00Z",
        selected_personas: ["explorer"],
        selected_goals: "finishBook",
        experience_level: "beginner",
        skipped: false,
      })
    );

    expect(getPersonaOnboardingData("user-malformed")).toBeNull();
    expect(
      shouldRequirePersonaOnboarding({
        id: "user-malformed",
        created_at: "2026-03-06T08:00:00Z",
      })
    ).toBe(true);
  });

  it("does not require onboarding for missing id or invalid created_at", () => {
    expect(
      shouldRequirePersonaOnboarding({
        id: "",
        created_at: "2026-03-06T08:00:00Z",
      })
    ).toBe(false);

    expect(
      shouldRequirePersonaOnboarding({
        id: "user-invalid-date",
        created_at: "not-a-date",
      })
    ).toBe(false);
  });

  it("does not require onboarding for users with future created_at timestamp", () => {
    expect(
      shouldRequirePersonaOnboarding({
        id: "user-future",
        created_at: "2026-03-10T08:00:00Z",
      })
    ).toBe(false);
  });

  it("saves onboarding payload with stable schema fields", () => {
    const saved = savePersonaOnboardingData("user-save", {
      selected_personas: ["builder", "strategist"],
      selected_goals: ["publishFast"],
      experience_level: "advanced",
      skipped: true,
    });

    expect(saved).not.toBeNull();
    expect(saved?.version).toBe(1);
    expect(typeof saved?.completed_at).toBe("string");
    expect(saved?.selected_personas).toEqual(["builder", "strategist"]);
    expect(saved?.selected_goals).toEqual(["publishFast"]);
    expect(saved?.experience_level).toBe("advanced");
    expect(saved?.skipped).toBe(true);
  });

  it("returns null when saving with empty user id", () => {
    const saved = savePersonaOnboardingData("", {
      selected_personas: ["explorer"],
      selected_goals: [],
      experience_level: "beginner",
      skipped: true,
    });

    expect(saved).toBeNull();
  });
});
