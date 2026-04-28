/**
 * Parse boolean-like environment variables with normalization.
 *
 * Supports common truthy/falsy string variants and trims whitespace/newlines
 * to avoid deployment-platform input quirks.
 */
export function parseEnvBoolean(value: unknown, defaultValue: boolean): boolean {
  if (typeof value === "boolean") return value;
  if (typeof value !== "string") return defaultValue;

  const normalized = value.trim().toLowerCase();

  if (["true", "1", "yes", "on"].includes(normalized)) return true;
  if (["false", "0", "no", "off"].includes(normalized)) return false;

  return defaultValue;
}

