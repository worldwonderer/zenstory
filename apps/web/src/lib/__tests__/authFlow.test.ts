import { describe, expect, it } from "vitest";
import { normalizePlanIntent } from "../authFlow";

describe("normalizePlanIntent", () => {
  it("returns normalized value for known plans", () => {
    expect(normalizePlanIntent("PRO")).toBe("pro");
    expect(normalizePlanIntent(" free ")).toBe("free");
  });

  it("returns null for unknown plan values", () => {
    expect(normalizePlanIntent("enterprise")).toBeNull();
    expect(normalizePlanIntent("studio")).toBeNull();
    expect(normalizePlanIntent("")).toBeNull();
    expect(normalizePlanIntent(null)).toBeNull();
    expect(normalizePlanIntent(undefined)).toBeNull();
  });
});
