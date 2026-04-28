import { describe, expect, it } from "vitest";

import {
  buildStagedUpgradeSource,
  resolveUpgradeTriggerStage,
} from "../upgradeTriggerStrategy";

describe("upgradeTriggerStrategy", () => {
  it("returns normal stage when usage is below 50%", () => {
    expect(resolveUpgradeTriggerStage({ used: 4, limit: 20 })).toBe("normal");
  });

  it("returns reminder_50 stage when usage reaches 50%", () => {
    expect(resolveUpgradeTriggerStage({ used: 10, limit: 20 })).toBe("reminder_50");
  });

  it("returns reminder_80 stage when usage reaches 80%", () => {
    expect(resolveUpgradeTriggerStage({ used: 16, limit: 20 })).toBe("reminder_80");
  });

  it("returns blocked stage when usage reaches limit", () => {
    expect(resolveUpgradeTriggerStage({ used: 20, limit: 20 })).toBe("blocked");
  });

  it("builds staged source suffix", () => {
    expect(buildStagedUpgradeSource("settings_subscription_upgrade", "reminder_80")).toBe(
      "settings_subscription_upgrade:reminder_80"
    );
    expect(buildStagedUpgradeSource("settings_subscription_upgrade", "normal")).toBe(
      "settings_subscription_upgrade"
    );
  });
});
