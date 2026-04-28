import { Page, Locator } from '@playwright/test';

/**
 * BasePage - Abstract base class for all Page Object Models.
 * Provides common navigation and interaction methods using data-testid attributes.
 */
export abstract class BasePage {
  constructor(protected page: Page) {}

  /**
   * Navigate to a specific path.
   * Uses a best-effort network-idle wait because some pages keep long-polling connections open.
   * @param path - The URL path to navigate to (e.g., '/login', '/dashboard')
   */
  async navigate(path: string) {
    const attempts = 2;
    for (let attempt = 1; attempt <= attempts; attempt += 1) {
      try {
        await this.page.goto(path, { waitUntil: 'domcontentloaded', timeout: 25000 });
        await this.page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {});
        return;
      } catch (error) {
        if (attempt === attempts) {
          throw error;
        }
        await this.page.waitForTimeout(400 * attempt);
      }
    }
  }

  /**
   * Wait for an element by its data-testid attribute.
   * @param testId - The data-testid value to wait for
   * @param timeout - Maximum time to wait in milliseconds (default: 15000)
   */
  async waitForTestId(testId: string, timeout = 15000) {
    await this.page.getByTestId(testId).waitFor({ timeout });
  }

  /**
   * Click an element by its data-testid attribute.
   * @param testId - The data-testid value of the element to click
   */
  async clickByTestId(testId: string) {
    await this.page.getByTestId(testId).click();
  }

  /**
   * Fill an input field by its data-testid attribute.
   * @param testId - The data-testid value of the input field
   * @param value - The value to fill in
   */
  async fillByTestId(testId: string, value: string) {
    await this.page.getByTestId(testId).fill(value);
  }

  /**
   * Get text content from an element by its data-testid attribute.
   * @param testId - The data-testid value of the element
   */
  async getTextByTestId(testId: string): Promise<string | null> {
    return this.page.getByTestId(testId).textContent();
  }

  /**
   * Check if an element is visible by its data-testid attribute.
   * @param testId - The data-testid value of the element
   */
  async isVisibleByTestId(testId: string): Promise<boolean> {
    return this.page.getByTestId(testId).isVisible();
  }

  /**
   * Wait for URL to match a pattern.
   * @param urlPattern - The URL pattern to wait for (supports glob patterns)
   */
  async waitForURL(urlPattern: string) {
    await this.page.waitForURL(urlPattern);
  }

  /**
   * Get a locator by data-testid attribute.
   * @param testId - The data-testid value
   */
  getLocatorByTestId(testId: string): Locator {
    return this.page.getByTestId(testId);
  }
}
