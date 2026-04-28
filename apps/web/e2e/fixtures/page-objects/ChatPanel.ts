import { Page, Locator } from '@playwright/test';
import { BasePage } from './BasePage';

/**
 * ChatPanel - Page Object Model for the AI chat panel.
 * Handles sending messages and receiving AI responses.
 */
export class ChatPanel extends BasePage {
  /** Chat message list container */
  private messageList = (): Locator => this.page.getByTestId('message-list');
  /** Chat input textarea */
  private chatInput = (): Locator => this.page.getByTestId('chat-input');
  /** Send message button */
  private sendButton = (): Locator => this.page.getByTestId('send-button');
  /** Individual message elements */
  private messages = (): Locator => this.page.getByTestId('chat-message');
  /** AI response indicator/loading state */
  private aiTypingIndicator = (): Locator => this.page.getByTestId('ai-typing-indicator');
  /** User messages */
  private userMessages = (): Locator => this.page.getByTestId('user-message');
  /** AI assistant messages */
  private aiMessages = (): Locator => this.page.getByTestId('ai-message');

  constructor(page: Page) {
    super(page);
  }

  /**
   * Send a message in the chat.
   * @param message - The message text to send
   */
  async sendMessage(message: string): Promise<void> {
    await this.fillByTestId('chat-input', message);
    await this.clickByTestId('send-button');
  }

  /**
   * Send a message and wait for AI response to complete.
   * @param message - The message text to send
   * @param timeout - Maximum time to wait for response (default: 30000ms)
   */
  async sendMessageAndWaitForResponse(message: string, timeout = 30000): Promise<void> {
    const initialCount = await this.getMessageCount();
    await this.sendMessage(message);
    await this.waitForResponse(timeout);
    // Wait for message count to increase
    await this.page.waitForFunction(
      (initial) => {
        const current = document.querySelectorAll('[data-testid="chat-message"]').length;
        return current > initial;
      },
      initialCount,
      { timeout }
    );
  }

  /**
   * Wait for the AI typing indicator to appear and then disappear.
   * @param timeout - Maximum time to wait (default: 30000ms)
   */
  async waitForResponse(timeout = 30000): Promise<void> {
    // Wait for typing indicator to appear (if it does)
    try {
      await this.aiTypingIndicator().waitFor({ state: 'visible', timeout: 5000 });
    } catch {
      // Typing indicator might not always appear, continue
    }
    // Wait for typing indicator to disappear
    await this.aiTypingIndicator().waitFor({ state: 'hidden', timeout });
  }

  /**
   * Get the message list locator.
   * @returns Locator for the message list
   */
  getMessageList(): Locator {
    return this.messageList();
  }

  /**
   * Get all message elements.
   * @returns Locator for all messages
   */
  getMessages(): Locator {
    return this.messages();
  }

  /**
   * Get the count of messages in the chat.
   * @returns Number of messages
   */
  async getMessageCount(): Promise<number> {
    return this.messages().count();
  }

  /**
   * Get the last message content.
   * @returns The text content of the last message
   */
  async getLastMessageContent(): Promise<string | null> {
    const count = await this.getMessageCount();
    if (count === 0) return null;
    return this.messages().last().textContent();
  }

  /**
   * Get the last AI message content.
   * @returns The text content of the last AI message
   */
  async getLastAIMessageContent(): Promise<string | null> {
    const aiMessageCount = await this.aiMessages().count();
    if (aiMessageCount === 0) return null;
    return this.aiMessages().last().textContent();
  }

  /**
   * Clear the chat input field.
   */
  async clearInput(): Promise<void> {
    await this.chatInput().clear();
  }

  /**
   * Check if the send button is enabled.
   * @returns True if send button is enabled
   */
  async isSendButtonEnabled(): Promise<boolean> {
    return this.sendButton().isEnabled();
  }

  /**
   * Wait for chat panel to be ready.
   */
  async waitForChatReady(): Promise<void> {
    await this.waitForTestId('chat-input');
    await this.waitForTestId('send-button');
  }
}
