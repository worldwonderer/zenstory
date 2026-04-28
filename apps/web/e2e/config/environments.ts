/**
 * E2E Test Environment Configuration
 *
 * Centralized configuration for test environments, timeouts, and settings.
 * Environment variables override defaults for CI/CD or custom environments.
 */

export interface MockDelaysConfig {
  fast: number;
  normal: number;
  slow: number;
  ai: number;
}

export interface EnvironmentConfig {
  baseUrl: string;
  apiBaseUrl: string;
  apiTimeout: number;
  uiTimeout: number;
  mockDelays: MockDelaysConfig;
}

/**
 * Test environment configuration
 * Values can be overridden via environment variables
 */
export const config: EnvironmentConfig = {
  /**
   * Base URL for the application under test
   * Override with E2E_BASE_URL environment variable
   */
  baseUrl: process.env.E2E_BASE_URL || 'http://127.0.0.1:5173',

  /**
   * Base URL for the API server
   * Override with E2E_API_URL environment variable
   * Defaults to localhost:8000 for local development
   */
  apiBaseUrl: process.env.E2E_API_URL || 'http://127.0.0.1:8000',

  /**
   * Default timeout for API operations (ms)
   * Used for network requests, backend operations
   */
  apiTimeout: 60000,

  /**
   * Default timeout for UI operations (ms)
   * Used for element interactions, assertions
   */
  uiTimeout: 15000,

  /**
   * Simulated delays for mock services (ms)
   * Use these to simulate realistic API response times
   */
  mockDelays: {
    fast: 100,
    normal: 500,
    slow: 2000,
    ai: 5000,
  },
} as const;

/**
 * Get the API base URL
 * Returns the configured apiBaseUrl with /api/v1 path appended
 */
export function getApiBaseUrl(): string {
  return `${config.apiBaseUrl}/api/v1`;
}

/**
 * Check if running in CI environment
 */
export function isCI(): boolean {
  return process.env.CI === 'true' || process.env.CI === '1';
}

/**
 * Get timeout multiplier for CI environments
 * CI often needs longer timeouts due to resource constraints
 */
export function getTimeoutMultiplier(): number {
  return isCI() ? 2 : 1;
}

/**
 * Get adjusted timeout for current environment
 * @param baseTimeout - Base timeout in ms
 * @returns Adjusted timeout with CI multiplier applied
 */
export function getAdjustedTimeout(baseTimeout: number): number {
  return baseTimeout * getTimeoutMultiplier();
}
