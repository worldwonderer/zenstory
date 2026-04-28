import { parseEnvBoolean } from "./env";

/**
 * Points feature configuration.
 *
 * `VITE_POINTS_PANEL_ENABLED` controls whether the user-facing
 * points panel is shown in Settings dialog.
 */
export interface PointsConfig {
  panelEnabled: boolean;
}

export const pointsConfig: PointsConfig = {
  // Default enabled. Set false/0/no/off to temporarily hide points panel.
  panelEnabled: parseEnvBoolean(import.meta.env.VITE_POINTS_PANEL_ENABLED, true),
};
