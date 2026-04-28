import { parseEnvBoolean } from "./env";

/**
 * Materials feature configuration.
 *
 * Keep materials-specific frontend toggles in one place.
 */
export interface MaterialsConfig {
  /**
   * Controls whether relationship-analysis UI is shown in the material detail tree.
   *
   * Backend decomposition can still omit relationships entirely; this flag keeps
   * the detail UI from advertising an empty relationship section by default.
   */
  relationshipsEnabled: boolean;
}

export const materialsConfig: MaterialsConfig = {
  // Default disabled to match backend cost-control posture; enable explicitly when relationship extraction is turned on.
  relationshipsEnabled: parseEnvBoolean(import.meta.env.VITE_MATERIALS_ENABLE_RELATIONSHIPS, false),
};
