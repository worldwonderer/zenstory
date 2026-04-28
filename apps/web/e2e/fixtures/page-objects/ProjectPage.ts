import { Page, Locator } from '@playwright/test';
import { BasePage } from './BasePage';

/**
 * ProjectPage - Page Object Model for the project workspace page.
 * Handles file tree, editor, and chat panel interactions within a project.
 */
export class ProjectPage extends BasePage {
  /** File tree panel container */
  private fileTreePanel = (): Locator => this.page.getByTestId('file-tree');
  /** Editor panel container */
  private editorPanel = (): Locator => this.page.getByTestId('editor-panel');
  /** Chat panel container */
  private chatPanel = (): Locator => this.page.getByTestId('chat-panel');
  /** Project header with title */
  private projectHeader = (): Locator => this.page.getByTestId('project-header');
  /** Create file button */
  private createFileButton = (): Locator => this.page.getByTestId('create-file-button');
  /** Project settings button */
  private settingsButton = (): Locator => this.page.getByTestId('project-settings-button');

  constructor(page: Page) {
    super(page);
  }

  /**
   * Navigate to a specific project by its ID.
   * @param projectId - The project ID to navigate to
   */
  async navigateToProject(projectId: string): Promise<void> {
    await this.navigate(`/projects/${projectId}`);
    await this.waitForTestId('file-tree');
  }

  /**
   * Navigate to a specific file within a project.
   * @param projectId - The project ID
   * @param fileId - The file ID to open
   */
  async navigateToFile(projectId: string, fileId: string): Promise<void> {
    await this.navigate(`/projects/${projectId}?fileId=${fileId}`);
    await this.waitForTestId('editor-panel');
  }

  /**
   * Get the file tree panel locator.
   * @returns Locator for the file tree panel
   */
  getFileTreePanel(): Locator {
    return this.fileTreePanel();
  }

  /**
   * Get the editor panel locator.
   * @returns Locator for the editor panel
   */
  getEditorPanel(): Locator {
    return this.editorPanel();
  }

  /**
   * Get the chat panel locator.
   * @returns Locator for the chat panel
   */
  getChatPanel(): Locator {
    return this.chatPanel();
  }

  /**
   * Click the create file button to open the file creation modal.
   */
  async clickCreateFile(): Promise<void> {
    await this.clickByTestId('create-file-button');
  }

  /**
   * Check if the editor panel is visible.
   * @returns True if editor panel is visible
   */
  async isEditorVisible(): Promise<boolean> {
    return this.isVisibleByTestId('editor-panel');
  }

  /**
   * Check if the chat panel is visible.
   * @returns True if chat panel is visible
   */
  async isChatVisible(): Promise<boolean> {
    return this.isVisibleByTestId('chat-panel');
  }

  /**
   * Open project settings.
   */
  async openSettings(): Promise<void> {
    await this.clickByTestId('project-settings-button');
  }

  /**
   * Get the project title from the header.
   * @returns The project title text
   */
  async getProjectTitle(): Promise<string | null> {
    return this.getTextByTestId('project-header');
  }

  /**
   * Wait for the project workspace to be fully loaded.
   */
  async waitForProjectLoad(): Promise<void> {
    await Promise.all([
      this.waitForTestId('file-tree'),
      this.waitForTestId('editor-panel'),
      this.waitForTestId('chat-panel'),
    ]);
  }
}
