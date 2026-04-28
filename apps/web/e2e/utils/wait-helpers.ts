import { Page, expect } from '@playwright/test';

/**
 * Waits for AI response streaming to complete
 * @param page - Playwright Page object
 * @param timeout - Maximum wait time in milliseconds (default: 30000)
 */
export async function waitForAIResponse(page: Page, timeout = 30000) {
  // Wait for streaming to start
  await page.waitForSelector('[data-testid="streaming-cursor"]', { timeout });

  // Wait for streaming to complete
  await page.waitForSelector('[data-testid="streaming-cursor"]', {
    state: 'hidden',
    timeout
  });
}

/**
 * Waits for a toast message to appear
 * @param page - Playwright Page object
 * @param message - Toast message text to wait for
 * @param timeout - Maximum wait time in milliseconds (default: 5000)
 */
export async function waitForToast(page: Page, message: string, timeout = 5000) {
  await page.waitForSelector(`text="${message}"`, { timeout });
}

/**
 * Waits for a modal to open
 * @param page - Playwright Page object
 * @param timeout - Maximum wait time in milliseconds (default: 5000)
 */
export async function waitForModal(page: Page, timeout = 5000) {
  await page.waitForSelector('[data-testid="modal-overlay"]', { timeout });
}

/**
 * Waits for a modal to close
 * @param page - Playwright Page object
 * @param timeout - Maximum wait time in milliseconds (default: 5000)
 */
export async function waitForModalClose(page: Page, timeout = 5000) {
  await page.waitForSelector('[data-testid="modal-overlay"]', {
    state: 'hidden',
    timeout
  });
}

/**
 * Wait for an element to contain specific text
 */
export async function waitForText(
  page: Page,
  selector: string,
  text: string,
  timeout: number = 5000
): Promise<void> {
  await page.locator(selector).waitFor({ state: 'visible', timeout });
  await expect(page.locator(selector)).toContainText(text, { timeout });
}

/**
 * Wait for an element count to match expected
 */
export async function waitForCount(
  page: Page,
  selector: string,
  expectedCount: number,
  timeout: number = 5000
): Promise<void> {
  await expect(page.locator(selector)).toHaveCount(expectedCount, { timeout });
}

/**
 * Wait for an element to be enabled (not disabled)
 */
export async function waitForEnabled(
  page: Page,
  selector: string,
  timeout: number = 5000
): Promise<void> {
  await page.locator(selector).waitFor({ state: 'visible', timeout });
  await expect(page.locator(selector)).toBeEnabled({ timeout });
}

/**
 * Wait for an element to be hidden or removed
 */
export async function waitForHidden(
  page: Page,
  selector: string,
  timeout: number = 5000
): Promise<void> {
  await page.locator(selector).waitFor({ state: 'hidden', timeout });
}

/**
 * Wait for URL to match pattern
 */
export async function waitForURL(
  page: Page,
  pattern: RegExp | string,
  timeout: number = 10000
): Promise<void> {
  await page.waitForURL(pattern, { timeout });
}
