import { Page, Locator } from '@playwright/test';
import { BasePage } from './BasePage';

/**
 * AdminPage - Page Object Model for the admin dashboard.
 * Handles user management and system administration tasks.
 */
export class AdminPage extends BasePage {
  /** Admin dashboard container */
  private adminContainer = (): Locator => this.page.getByTestId('admin-container');
  /** User management table */
  private userTable = (): Locator => this.page.getByTestId('user-table');
  /** User table rows */
  private userRows = (): Locator => this.page.getByTestId('user-row');
  /** Admin navigation sidebar */
  private adminSidebar = (): Locator => this.page.getByTestId('admin-sidebar');
  /** Settings panel */
  private settingsPanel = (): Locator => this.page.getByTestId('admin-settings-panel');
  /** User search input */
  private userSearchInput = (): Locator => this.page.getByTestId('user-search-input');
  /** Add user button */
  private addUserButton = (): Locator => this.page.getByTestId('add-user-button');
  /** Statistics overview */
  private statsOverview = (): Locator => this.page.getByTestId('stats-overview');

  constructor(page: Page) {
    super(page);
  }

  /**
   * Navigate to the admin dashboard.
   */
  async navigateToAdmin(): Promise<void> {
    await this.navigate('/admin');
    await this.waitForTestId('admin-container');
  }

  /**
   * Get the user management table locator.
   * @returns Locator for the user table
   */
  getUserTable(): Locator {
    return this.userTable();
  }

  /**
   * Get all user row locators.
   * @returns Locator for all user rows
   */
  getUserRows(): Locator {
    return this.userRows();
  }

  /**
   * Get the count of users in the table.
   * @returns Number of user rows
   */
  async getUserCount(): Promise<number> {
    return this.userRows().count();
  }

  /**
   * Search for a user by name or email.
   * @param query - Search query (name or email)
   */
  async searchUser(query: string): Promise<void> {
    await this.fillByTestId('user-search-input', query);
    // Wait for search results to update by checking response in table
    await expect(this.userRows().first()).toBeVisible({ timeout: 5000 });
  }

  /**
   * Click on a user row by username.
   * @param username - The username to find and click
   */
  async clickUserByUsername(username: string): Promise<void> {
    await this.userRows()
      .filter({ hasText: username })
      .first()
      .click();
  }

  /**
   * Open the add user modal.
   */
  async openAddUserModal(): Promise<void> {
    await this.clickByTestId('add-user-button');
    await this.waitForTestId('add-user-modal');
  }

  /**
   * Navigate to a specific admin section.
   * @param section - Section name (users, settings, logs, etc.)
   */
  async navigateToSection(section: string): Promise<void> {
    await this.page.getByTestId(`nav-${section}`).click();
  }

  /**
   * Check if the admin container is visible.
   * @returns True if admin container is visible
   */
  async isAdminVisible(): Promise<boolean> {
    return this.isVisibleByTestId('admin-container');
  }

  /**
   * Check if user table is visible.
   * @returns True if user table is visible
   */
  async isUserTableVisible(): Promise<boolean> {
    return this.isVisibleByTestId('user-table');
  }

  /**
   * Get statistics from the overview panel.
   * @returns Object with statistic values
   */
  async getStats(): Promise<{ [key: string]: string }> {
    const stats: { [key: string]: string } = {};
    const statElements = await this.page.getByTestId(/stat-/).all();

    for (const element of statElements) {
      const testId = await element.getAttribute('data-testid');
      if (testId) {
        const key = testId.replace('stat-', '');
        stats[key] = (await element.textContent()) || '';
      }
    }

    return stats;
  }

  /**
   * Wait for admin dashboard to fully load.
   */
  async waitForAdminLoad(): Promise<void> {
    await Promise.all([
      this.waitForTestId('admin-container'),
      this.waitForTestId('admin-sidebar'),
    ]);
  }
}
