import { Page, Locator } from '@playwright/test';
import { BasePage } from './BasePage';

/**
 * DashboardPage - Page Object Model for the dashboard/home page.
 * Handles project listing and creation workflows.
 */
export class DashboardPage extends BasePage {
  /** Individual project card elements */
  private projectCards = (): Locator => this.page.getByTestId('project-card');
  /** Inspiration textarea used for quick project creation */
  private inspirationInput = (): Locator => this.page.getByTestId('dashboard-inspiration-input');
  /** Quick create project button */
  private createProjectButton = (): Locator => this.page.getByTestId('create-project-button');

  constructor(page: Page) {
    super(page);
  }

  /**
   * Navigate to the dashboard page.
   */
  async navigateToDashboard(): Promise<void> {
    await this.navigate('/dashboard');
    await this.waitForTestId('create-project-button');
  }

  /**
   * Create a new project with the given details.
   * @param name - Project name
   * @param description - Project description (optional)
   */
  async createProject(name: string, description?: string): Promise<void> {
    // Dashboard quick-create now uses an inspiration prompt (not a name/description modal).
    // Keep the method signature for backwards compatibility with existing tests.
    const prompt = description ? `${name}\n${description}` : name;
    await this.inspirationInput().fill(prompt);
    await this.createProjectButton().click();
    // Quick create navigates directly into the new project.
    await this.page.waitForURL(/\/project\//, { timeout: 15000 });
  }

  /**
   * Get all project card elements.
   * @returns Locator for all project cards
   */
  getProjectCards(): Locator {
    return this.projectCards();
  }

  /**
   * Get the count of visible project cards.
   * @returns Number of project cards
   */
  async getProjectCount(): Promise<number> {
    return this.projectCards().count();
  }

  /**
   * Click on a project card by its name.
   * @param projectName - The name of the project to click
   */
  async clickProjectByName(projectName: string): Promise<void> {
    await this.projectCards()
      .filter({ hasText: projectName })
      .first()
      .click();
  }

  /**
   * Check if a project with the given name exists.
   * @param projectName - The project name to search for
   * @returns True if project card with the name exists
   */
  async hasProject(projectName: string): Promise<boolean> {
    const count = await this.projectCards()
      .filter({ hasText: projectName })
      .count();
    return count > 0;
  }

  /**
   * Wait for project grid to be populated.
   * @param minCount - Minimum number of projects to wait for
   */
  async waitForProjects(minCount = 1): Promise<void> {
    await this.page.waitForFunction(
      (min) => document.querySelectorAll('[data-testid="project-card"]').length >= min,
      minCount
    );
  }
}
