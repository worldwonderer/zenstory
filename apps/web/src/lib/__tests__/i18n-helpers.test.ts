import { describe, expect, it, vi, beforeEach } from "vitest";

describe("i18n helpers", () => {
  beforeEach(() => {
    vi.resetModules();
    localStorage.clear();
  });

  it("normalizes locale variants to supported locales", async () => {
    const { normalizeLocale } = await import("../i18n-helpers");

    expect(normalizeLocale("zh-CN")).toBe("zh");
    expect(normalizeLocale("zh-TW")).toBe("zh");
    expect(normalizeLocale("en-US")).toBe("en");
    expect(normalizeLocale("EN-gb")).toBe("en");
    expect(normalizeLocale(undefined)).toBe("zh");
    expect(normalizeLocale("fr-FR")).toBe("zh");
  });

  it("reads locale from zenstory-language localStorage key", async () => {
    localStorage.setItem("zenstory-language", "en");
    const { getLocale, getLocaleCode } = await import("../i18n-helpers");

    expect(getLocale()).toBe("en");
    expect(getLocaleCode()).toBe("en-US");
  });
});
