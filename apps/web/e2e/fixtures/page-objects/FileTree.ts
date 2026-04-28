import { Page, Locator } from '@playwright/test';
import { BasePage } from './BasePage';

/**
 * FileTree - Page Object Model for the file tree component.
 * Handles file and folder operations within the project workspace.
 */
export class FileTree extends BasePage {
  /** File tree container */
  private treeContainer = (): Locator => this.page.getByTestId('file-tree');
  /** Individual file items */
  private fileItems = (): Locator => this.page.getByTestId('file-item');
  /** Folder items */
  private folderItems = (): Locator => this.page.getByTestId('folder-item');
  /** Create file button */
  private createFileButton = (): Locator => this.page.getByTestId('create-file-button');
  /** Create folder button */
  private createFolderButton = (): Locator => this.page.getByTestId('create-folder-button');
  /** File creation modal */
  private createFileModal = (): Locator => this.page.getByTestId('create-file-modal');
  /** File name input in modal */
  private fileNameInput = (): Locator => this.page.getByTestId('file-name-input');
  /** File type selector */
  private fileTypeSelect = (): Locator => this.page.getByTestId('file-type-select');
  /** Submit file creation button */
  private submitFileButton = (): Locator => this.page.getByTestId('submit-file-button');
  /** File context menu */
  private fileContextMenu = (): Locator => this.page.getByTestId('file-context-menu');
  /** Delete file option in context menu */
  private deleteFileOption = (): Locator => this.page.getByTestId('delete-file-option');
  /** Rename file option in context menu */
  private renameFileOption = (): Locator => this.page.getByTestId('rename-file-option');

  constructor(page: Page) {
    super(page);
  }

  /**
   * Open the create file modal.
   */
  async openCreateFileModal(): Promise<void> {
    await this.clickByTestId('create-file-button');
    await this.waitForTestId('create-file-modal');
  }

  /**
   * Create a new file with the given name and type.
   * @param name - The file name
   * @param type - The file type (outline, draft, character, lore, material)
   */
  async createFile(name: string, type: string): Promise<void> {
    await this.openCreateFileModal();
    await this.fillByTestId('file-name-input', name);
    await this.fileTypeSelect().selectOption(type);
    await this.clickByTestId('submit-file-button');
    // Wait for the file to appear in the tree
    await this.waitForFileByName(name);
  }

  /**
   * Create a new folder with the given name.
   * @param name - The folder name
   */
  async createFolder(name: string): Promise<void> {
    await this.clickByTestId('create-folder-button');
    await this.fillByTestId('file-name-input', name);
    await this.clickByTestId('submit-file-button');
  }

  /**
   * Click on a file to select/open it.
   * @param fileName - The name of the file to click
   */
  async clickFileByName(fileName: string): Promise<void> {
    await this.fileItems()
      .filter({ hasText: fileName })
      .first()
      .click();
  }

  /**
   * Right-click on a file to open context menu.
   * @param fileName - The name of the file
   */
  async rightClickFileByName(fileName: string): Promise<void> {
    await this.fileItems()
      .filter({ hasText: fileName })
      .first()
      .click({ button: 'right' });
    await this.waitForTestId('file-context-menu');
  }

  /**
   * Delete a file by name using context menu.
   * @param fileName - The name of the file to delete
   */
  async deleteFile(fileName: string): Promise<void> {
    await this.rightClickFileByName(fileName);
    await this.clickByTestId('delete-file-option');
  }

  /**
   * Rename a file using context menu.
   * @param oldName - Current file name
   * @param newName - New file name
   */
  async renameFile(oldName: string, newName: string): Promise<void> {
    await this.rightClickFileByName(oldName);
    await this.clickByTestId('rename-file-option');
    await this.fillByTestId('file-name-input', newName);
    await this.clickByTestId('submit-file-button');
  }

  /**
   * Get all file item locators.
   * @returns Locator for all file items
   */
  getFileItems(): Locator {
    return this.fileItems();
  }

  /**
   * Get all folder item locators.
   * @returns Locator for all folder items
   */
  getFolderItems(): Locator {
    return this.folderItems();
  }

  /**
   * Check if a file with the given name exists.
   * @param fileName - The file name to check
   * @returns True if file exists
   */
  async hasFile(fileName: string): Promise<boolean> {
    const count = await this.fileItems()
      .filter({ hasText: fileName })
      .count();
    return count > 0;
  }

  /**
   * Wait for a file to appear in the tree.
   * @param fileName - The file name to wait for
   * @param timeout - Maximum wait time (default: 10000ms)
   */
  async waitForFileByName(fileName: string, timeout = 10000): Promise<void> {
    await this.fileItems()
      .filter({ hasText: fileName })
      .first()
      .waitFor({ timeout });
  }

  /**
   * Expand a folder by clicking on it.
   * @param folderName - The folder name to expand
   */
  async expandFolder(folderName: string): Promise<void> {
    await this.folderItems()
      .filter({ hasText: folderName })
      .first()
      .click();
  }

  /**
   * Get the count of files in the tree.
   * @returns Number of file items
   */
  async getFileCount(): Promise<number> {
    return this.fileItems().count();
  }
}
