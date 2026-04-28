import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

let mockLanguage = "zh-CN";
let mockResolvedLanguage: string | undefined = "zh-CN";

const mockLoadDashboardPlaceholderBundle = vi.fn();

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    i18n: {
      language: mockLanguage,
      resolvedLanguage: mockResolvedLanguage,
    },
  }),
}));

vi.mock("../../lib/dashboardPlaceholderSource", async () => {
  const actual = await vi.importActual<typeof import("../../lib/dashboardPlaceholderSource")>(
    "../../lib/dashboardPlaceholderSource",
  );

  return {
    ...actual,
    loadDashboardPlaceholderBundle: (...args: Parameters<typeof actual.loadDashboardPlaceholderBundle>) =>
      mockLoadDashboardPlaceholderBundle(...args),
  };
});

import { useDashboardPlaceholders } from "../useDashboardPlaceholders";

describe("useDashboardPlaceholders", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockLanguage = "zh-CN";
    mockResolvedLanguage = "zh-CN";
  });

  it("keeps zh fallback placeholder as-is without adding prefix", async () => {
    mockLoadDashboardPlaceholderBundle.mockResolvedValue(null);

    const { result } = renderHook(() => useDashboardPlaceholders("novel", "一个记者发现谎言会显形"));

    expect(result.current).toBe("一个记者发现谎言会显形");
    expect(result.current.startsWith("灵感：")).toBe(false);

    await waitFor(() => {
      expect(mockLoadDashboardPlaceholderBundle).toHaveBeenCalledWith("zh");
    });
  });

  it("uses offline candidate directly for zh without force prefix", async () => {
    mockLoadDashboardPlaceholderBundle.mockResolvedValue({
      locale: "zh",
      placeholders: {
        novel: ["小镇记者追查豪门丑闻时被总裁堵在墙角"],
        short: ["短篇占位文案"],
        screenplay: ["剧本占位文案"],
      },
    });

    const { result } = renderHook(() => useDashboardPlaceholders("novel", "默认文案"));

    await waitFor(() => {
      expect(result.current).toBe("小镇记者追查豪门丑闻时被总裁堵在墙角");
    });

    expect(result.current.startsWith("灵感：")).toBe(false);
  });

  it("resolves english locale and keeps fallback text", async () => {
    mockLanguage = "en-US";
    mockResolvedLanguage = "en-US";
    mockLoadDashboardPlaceholderBundle.mockResolvedValue(null);

    const { result } = renderHook(() => useDashboardPlaceholders("novel", "Start with a compelling conflict."));

    expect(result.current).toBe("Start with a compelling conflict.");

    await waitFor(() => {
      expect(mockLoadDashboardPlaceholderBundle).toHaveBeenCalledWith("en");
    });
  });
});
