/**
 * E2E Test User Configuration
 *
 * Centralized test user definitions for E2E testing.
 * Supports standard users, admin users, and a pool for parallel test isolation.
 */

export interface TestUser {
  email: string;
  password: string;
  username: string;
}

export interface TestUsersConfig {
  standard: TestUser;
  skills: TestUser;
  admin: TestUser;
  pool: TestUser[];
}

const standardEmail = process.env.E2E_TEST_EMAIL || 'e2e-test@zenstory.local';
const standardPassword = process.env.E2E_TEST_PASSWORD || 'E2eTestPassword123!';
const standardUsername = process.env.E2E_TEST_USERNAME || 'e2e_test_user';

const skillsEmail = process.env.E2E_TEST_SKILLS_EMAIL || 'e2e-skills@zenstory.local';
const skillsPassword = process.env.E2E_TEST_SKILLS_PASSWORD || 'E2eSkillsPassword123!';
const skillsUsername = process.env.E2E_TEST_SKILLS_USERNAME || 'e2e_skills_user';

const adminEmail = process.env.E2E_TEST_ADMIN_EMAIL || 'test-admin@zenstory.test';
const adminPassword = process.env.E2E_TEST_ADMIN_PASSWORD || 'TestAdmin123!';
const adminUsername = process.env.E2E_TEST_ADMIN_USERNAME || 'test_admin';

/**
 * Test users for E2E authentication and testing
 */
export const TEST_USERS: TestUsersConfig = {
  /**
   * Standard test user for general E2E tests
   */
  standard: {
    email: standardEmail,
    password: standardPassword,
    username: standardUsername,
  },

  /**
   * Dedicated user for custom-skill creation flows.
   * This user should be seeded with available skill quota / paid entitlements.
   */
  skills: {
    email: skillsEmail,
    password: skillsPassword,
    username: skillsUsername,
  },

  /**
   * Admin test user for tests requiring elevated permissions
   */
  admin: {
    email: adminEmail,
    password: adminPassword,
    username: adminUsername,
  },

  /**
   * Pool of test users for parallel test isolation
   * Each test can use a unique user to avoid data conflicts
   */
  pool: Array.from({ length: 5 }, (_, i): TestUser => ({
    email: `e2e-pool-${i}@zenstory.local`,
    password: `PoolTest${i}!Aa`,
    username: `e2e-pool-user-${i}`,
  })),
} as const;

/**
 * Get a test user from the pool by index
 * @param index - Pool index (0-4)
 * @returns Test user from the pool
 */
export function getPoolUser(index: number): TestUser {
  if (index < 0 || index >= TEST_USERS.pool.length) {
    throw new Error(
      `Pool index ${index} out of range. Available indices: 0-${TEST_USERS.pool.length - 1}`
    );
  }
  return TEST_USERS.pool[index];
}

/**
 * Get a unique test user based on test worker index
 * @param workerIndex - Playwright test worker index
 * @returns Test user for this worker
 */
export function getWorkerUser(workerIndex: number): TestUser {
  return getPoolUser(workerIndex % TEST_USERS.pool.length);
}
