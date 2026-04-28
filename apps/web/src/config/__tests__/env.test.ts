import { describe, expect, it } from "vitest";

import { parseEnvBoolean } from "../env";

describe("parseEnvBoolean", () => {
  it("parses truthy strings with whitespace/newline", () => {
    expect(parseEnvBoolean("true\n", false)).toBe(true);
    expect(parseEnvBoolean(" TRUE ", false)).toBe(true);
    expect(parseEnvBoolean("1", false)).toBe(true);
    expect(parseEnvBoolean("yes", false)).toBe(true);
    expect(parseEnvBoolean("on", false)).toBe(true);
  });

  it("parses falsy strings with whitespace/newline", () => {
    expect(parseEnvBoolean("false\n", true)).toBe(false);
    expect(parseEnvBoolean(" FALSE ", true)).toBe(false);
    expect(parseEnvBoolean("0", true)).toBe(false);
    expect(parseEnvBoolean("no", true)).toBe(false);
    expect(parseEnvBoolean("off", true)).toBe(false);
  });

  it("falls back to default for unknown/non-string inputs", () => {
    expect(parseEnvBoolean("maybe", true)).toBe(true);
    expect(parseEnvBoolean("maybe", false)).toBe(false);
    expect(parseEnvBoolean(undefined, true)).toBe(true);
    expect(parseEnvBoolean(null, false)).toBe(false);
  });
});

