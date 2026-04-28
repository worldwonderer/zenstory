export type UpgradeTriggerStage =
  | "normal"
  | "reminder_50"
  | "reminder_80"
  | "blocked";

export interface UpgradeUsageSnapshot {
  used: number;
  limit: number;
}

export function resolveUpgradeTriggerStage({
  used,
  limit,
}: UpgradeUsageSnapshot): UpgradeTriggerStage {
  if (limit <= 0 || limit === -1) return "normal";

  const ratio = used / limit;
  if (ratio >= 1) return "blocked";
  if (ratio >= 0.8) return "reminder_80";
  if (ratio >= 0.5) return "reminder_50";
  return "normal";
}

export function buildStagedUpgradeSource(
  baseSource: string,
  stage: UpgradeTriggerStage
): string {
  const normalizedBase = baseSource.trim();
  if (!normalizedBase) return "";
  if (stage === "normal") return normalizedBase;
  return `${normalizedBase}:${stage}`;
}
