import { Page, Locator, expect } from '@playwright/test';

/**
 * Asserts that an element is visible
 * @param locator - Playwright Locator for the element
 */
export async function assertElementVisible(locator: Locator) {
  await expect(locator).toBeVisible();
}

/**
 * Asserts that an element is hidden
 * @param locator - Playwright Locator for the element
 */
export async function assertElementHidden(locator: Locator) {
  await expect(locator).toBeHidden();
}

/**
 * Asserts that a toast message is visible
 * @param page - Playwright Page object
 * @param message - Expected toast message text
 */
export async function assertToastMessage(page: Page, message: string) {
  await expect(page.locator(`text="${message}"`)).toBeVisible();
}

/**
 * Asserts that no console errors occurred during page load
 * @param page - Playwright Page object
 */
export async function assertNoConsoleErrors(page: Page) {
  const errors: string[] = [];

  page.on('console', msg => {
    if (msg.type() === 'error') {
      errors.push(msg.text());
    }
  });

  // Wait for page to be fully loaded
  await page.waitForLoadState('domcontentloaded', { timeout: 5000 });

  expect(errors).toHaveLength(0);
}

/**
 * Asserts that the current URL contains a specific path
 * @param page - Playwright Page object
 * @param path - Expected URL path segment
 */
export async function assertUrlContains(page: Page, path: string) {
  expect(page.url()).toContain(path);
}
