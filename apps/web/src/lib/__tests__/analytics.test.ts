import { beforeEach, describe, expect, it, vi } from "vitest";

const initMock = vi.fn();
const captureMock = vi.fn();
const identifyMock = vi.fn();
const resetMock = vi.fn();
const captureExceptionMock = vi.fn();
const startExceptionAutocaptureMock = vi.fn();

vi.mock("posthog-js", () => ({
  default: {
    init: initMock,
    capture: captureMock,
    identify: identifyMock,
    reset: resetMock,
    captureException: captureExceptionMock,
    startExceptionAutocapture: startExceptionAutocaptureMock,
  },
}));

describe("analytics", () => {
  beforeEach(() => {
    vi.resetModules();
    initMock.mockReset();
    captureMock.mockReset();
    identifyMock.mockReset();
    resetMock.mockReset();
    captureExceptionMock.mockReset();
    startExceptionAutocaptureMock.mockReset();
    document.title = "Dashboard";
  });

  it("does not initialize when disabled", async () => {
    const analytics = await import("../analytics");

    expect(
      analytics.initAnalytics({
        DEV: false,
        MODE: "test",
        VITE_POSTHOG_ENABLED: "false",
        VITE_POSTHOG_KEY: "phc_test",
      })
    ).toBe(false);
    expect(initMock).not.toHaveBeenCalled();
  });

  it("initializes PostHog and captures events when enabled", async () => {
    const analytics = await import("../analytics");

    expect(
      analytics.initAnalytics({
        DEV: false,
        MODE: "test",
        VITE_POSTHOG_ENABLED: " TRUE \n",
        VITE_POSTHOG_KEY: "phc_test",
        VITE_POSTHOG_HOST: "https://us.i.posthog.com",
      })
    ).toBe(true);

    expect(initMock).toHaveBeenCalledWith(
      "phc_test",
      expect.objectContaining({
        api_host: "https://us.i.posthog.com",
        person_profiles: "identified_only",
        disable_session_recording: true,
      })
    );
    expect(startExceptionAutocaptureMock).toHaveBeenCalledTimes(1);

    analytics.trackEvent("dashboard_view", { source: "test" });
    expect(captureMock).toHaveBeenCalledWith(
      "dashboard_view",
      expect.objectContaining({
        source: "test",
        page_path: window.location.pathname,
        page_title: "Dashboard",
      })
    );
  });

  it("identifies, resets, captures exceptions, and dedupes page views", async () => {
    const analytics = await import("../analytics");

    analytics.initAnalytics({
      DEV: false,
      MODE: "test",
      VITE_POSTHOG_ENABLED: "true",
      VITE_POSTHOG_KEY: "phc_test",
    });

    analytics.identifyUser({
      id: "user-1",
      email: "user@example.com",
      username: "writer",
      is_superuser: false,
    });
    expect(identifyMock).toHaveBeenCalledWith(
      "user-1",
      expect.objectContaining({
        is_superuser: false,
      })
    );
    const identifyPayload = identifyMock.mock.calls[0]?.[1] as Record<string, unknown> | undefined;
    expect(identifyPayload).toBeDefined();
    expect(identifyPayload).not.toHaveProperty("email");
    expect(identifyPayload).not.toHaveProperty("username");

    analytics.trackPageView();
    analytics.trackPageView();
    expect(captureMock).toHaveBeenCalledTimes(1);
    expect(captureMock).toHaveBeenCalledWith(
      "page_view",
      expect.objectContaining({
        path: window.location.pathname,
        search: window.location.search || undefined,
      })
    );

    analytics.captureException(new Error("boom"), { feature_area: "test" });
    expect(captureExceptionMock).toHaveBeenCalledWith(
      expect.any(Error),
      expect.objectContaining({
        feature_area: "test",
        page_path: window.location.pathname,
      })
    );

    analytics.resetAnalytics();
    expect(resetMock).toHaveBeenCalledWith(true);
  });
});
