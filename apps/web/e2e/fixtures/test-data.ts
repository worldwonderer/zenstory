/**
 * E2E Test Data Fixtures
 *
 * Reusable test data constants for E2E testing.
 * Use these constants across all E2E tests to ensure consistency.
 *
 * Note: Test users have been moved to config/test-users.ts
 * Import TEST_USERS from '../config' for test user data.
 */

// Re-export test users from config for backward compatibility
export { TEST_USERS, TEST_USERS as TEST_USER_DATA } from '../config';
import { TEST_USERS } from '../config';

/**
 * @deprecated Use TEST_USERS.standard instead
 */
export const TEST_USER = TEST_USERS.standard;

/**
 * @deprecated Use TEST_USERS.admin instead
 */
export const TEST_ADMIN_USER = TEST_USERS.admin;

/**
 * Standard test project for E2E project-related tests
 */
export const TEST_PROJECT = {
  name: 'E2E Test Project',
  description: 'Project for E2E testing',
} as const;

/**
 * Standard test file for E2E file-related tests
 */
export const TEST_FILE = {
  name: 'Test Chapter',
  file_type: 'draft',
  content: 'This is test content for E2E testing.\n\nWith multiple paragraphs.',
} as const;

/**
 * Standard test character for E2E character-related tests
 */
export const TEST_CHARACTER = {
  name: 'Test Character',
  traits: ['brave', 'intelligent'],
  background: 'A test character for E2E testing',
} as const;

/**
 * Standard test skill for E2E skill-related tests
 */
export const TEST_SKILL = {
  name: 'Test Skill',
  description: 'A test skill for E2E testing',
  triggers: ['test-trigger', 'example-trigger'],
  instructions: 'This is a test instruction for the skill.',
} as const;

/**
 * Standard test novel material for E2E material-related tests
 */
export const TEST_MATERIAL_NOVEL = {
  title: 'Test Novel for Materials',
  filename: 'test-novel.txt',
  chapters: 10,
  characters: 5,
  plots: 8,
} as const;
