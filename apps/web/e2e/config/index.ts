/**
 * E2E Test Configuration - Barrel Export
 *
 * Centralized exports for all E2E test configuration.
 * Import from this module for consistent configuration access.
 */

// Test users
export {
  TEST_USERS,
  getPoolUser,
  getWorkerUser,
  type TestUser,
  type TestUsersConfig,
} from './test-users';

// Environment configuration
export {
  config,
  getApiBaseUrl,
  isCI,
  getTimeoutMultiplier,
  getAdjustedTimeout,
  type EnvironmentConfig,
  type MockDelaysConfig,
} from './environments';
