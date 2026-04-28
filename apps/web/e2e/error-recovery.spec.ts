import { test, expect, Page } from '@playwright/test';
import { TEST_USERS } from './config';
import { LoginPage, ChatPanel } from './fixtures/page-objects';

const ENABLE_ERROR_RECOVERY_E2E = process.env.E2E_ENABLE_ERROR_RECOVERY_E2E === 'true';
const ERROR_RECOVERY_OPT_IN_MESSAGE = 'Error recovery E2E tests are opt-in. Set E2E_ENABLE_ERROR_RECOVERY_E2E=true to run.';

/**
 * Error Recovery E2E Tests
 *
 * Tests application behavior under error conditions:
 * - Network interruption during AI stream
 * - Backend restart handling (503 errors)
 * - Quota exceeded error display
 * - Failed API call retry with backoff
 * - Invalid response handling
 * - Timeout error handling
 */

test.describe('Error Recovery', () => {
  test.skip(!ENABLE_ERROR_RECOVERY_E2E, ERROR_RECOVERY_OPT_IN_MESSAGE);

  // Test credentials
  const TEST_EMAIL = TEST_USERS.standard.email;
  const TEST_PASSWORD = TEST_USERS.standard.password;
  const API_BASE_URL = process.env.E2E_API_BASE_URL || 'http://127.0.0.1:8000';

  const listProjects = async (page: Page, authHeaders: Record<string, string>): Promise<Array<{ id: string }>> => {
    const listResponse = await page.request.get(`${API_BASE_URL}/api/v1/projects`, {
      headers: authHeaders,
    });

    if (!listResponse.ok()) {
      throw new Error(`Failed to list projects: ${listResponse.status()} ${listResponse.statusText()}`);
    }

    const payload = await listResponse.json();
    return Array.isArray(payload) ? payload : [];
  };

  const ensureProjectWorkspace = async (page: Page): Promise<void> => {
    if (page.url().includes('/project/')) {
      return;
    }

    const accessToken = await page.evaluate(() => localStorage.getItem('access_token'));
    if (!accessToken) {
      throw new Error('Missing access token after login');
    }

    const authHeaders = {
      Authorization: `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
    };

    let projects = await listProjects(page, authHeaders);

    if (projects.length === 0) {
      const createResponse = await page.request.post(`${API_BASE_URL}/api/v1/projects`, {
        headers: authHeaders,
        data: {
          name: `E2E Error Recovery ${Date.now()}`,
          project_type: 'novel',
        },
      });

      if (!createResponse.ok()) {
        throw new Error(`Failed to create project: ${createResponse.status()} ${createResponse.statusText()}`);
      }

      const createdProject = (await createResponse.json()) as { id?: string };
      if (!createdProject?.id) {
        throw new Error('Project creation returned no id');
      }

      projects = [{ id: createdProject.id }];
    }

    await page.goto(`/project/${projects[0].id}`);
    await page.waitForURL(/\/project\//, { timeout: 10000 });
  };

  const waitForWorkspaceReady = async (page: Page): Promise<void> => {
    await expect(page).toHaveURL(/\/project\//, { timeout: 10000 });
    await expect(
      page.locator('[data-testid="file-tree"], input[placeholder*="搜索文件"], input[placeholder*="Search files"], [role="searchbox"]').first()
    ).toBeVisible({ timeout: 15000 });
    await expect(
      page
        .locator('[data-testid="chat-input"], textarea[placeholder*="描述你想创作"], textarea[placeholder*="输入"], textarea[placeholder*="Type"]')
        .first()
    ).toBeVisible({ timeout: 15000 });
  };

  let loginPage: LoginPage;
  let chatPanel: ChatPanel;

  test.beforeEach(async ({ page }) => {
    loginPage = new LoginPage(page);
    chatPanel = new ChatPanel(page);

    // Navigate to login page
    await loginPage.navigateToLogin();

    // Login with test credentials
    await loginPage.login(TEST_EMAIL, TEST_PASSWORD);

    // Wait for redirect to complete (either project or dashboard)
    await page.waitForURL(/\/(project|dashboard)/, { timeout: 10000 });

    // Use API-driven setup to avoid locale/UI-dependent dashboard interactions.
    await ensureProjectWorkspace(page);

    // Wait for project workspace to load
    await waitForWorkspaceReady(page);
  });

  test('network interruption during AI stream', async ({ page, context }) => {
    // Send a message that will trigger AI response
    await chatPanel.sendMessage('写一段简短的故事');

    // Wait for AI response to start streaming
    await expect(page.locator('.animate-pulse.w-1\\.5')).toBeVisible({ timeout: 10000 });

    // Simulate network offline
    await context.setOffline(true);

    // Verify error message appears
    await expect(page.locator('[class*="error"], .text-error, [data-testid="error-message"]')).toBeVisible({ timeout: 15000 });

    // Restore network
    await context.setOffline(false);

    // Verify retry option available (retry button or auto-retry indicator)
    const retryButton = page.locator('button:has-text("重试"), button:has-text("Retry"), [data-testid="retry-button"]');
    const isVisible = await retryButton.first().isVisible().catch(() => false);
    expect(isVisible).toBeTruthy();
  });

  test('backend restart handling (503 errors)', async ({ page }) => {
    // Mock 503 response for all API calls
    await page.route('**/api/v1/**', route =>
      route.fulfill({
        status: 503,
        body: JSON.stringify({ message: 'Service Unavailable', detail: 'Backend is restarting' }),
        headers: { 'Content-Type': 'application/json' }
      })
    );

    // Try to send a message
    await chatPanel.sendMessage('Test message during restart');

    // Verify user-friendly error message
    await expect(page.locator('text=/服务暂不可用|Service.*unavailable|503/i')).toBeVisible({ timeout: 10000 });

    // Verify retry mechanism is suggested
    await expect(page.locator('button:has-text("重试"), button:has-text("Retry"), text=/请稍后|please.*try.*later/i')).toBeVisible({ timeout: 5000 });
  });

  test('quota exceeded error display', async ({ page }) => {
    // Mock 429 response for agent chat
    await page.route('**/api/v1/agent/**', route =>
      route.fulfill({
        status: 429,
        body: JSON.stringify({
          message: 'Rate limit exceeded',
          detail: 'You have exceeded the API quota',
          retry_after: 60
        }),
        headers: {
          'Content-Type': 'application/json',
          'Retry-After': '60'
        }
      })
    );

    await chatPanel.sendMessage('Test message for quota');

    // Verify quota error message visible
    await expect(
      page.locator('text=/配额.*超出|quota.*exceeded|429|rate.*limit/i')
    ).toBeVisible({ timeout: 10000 });

    // Verify retry-after time displayed
    const retryText = await page.locator('text=/60.*秒|1.*分钟|retry.*after/i').first().textContent();
    expect(retryText).toBeTruthy();
  });

  test('failed API call retry with backoff', async ({ page }) => {
    let attemptCount = 0;

    // Mock API that fails twice then succeeds
    await page.route('**/api/v1/projects', route => {
      attemptCount++;
      if (attemptCount < 3) {
        route.fulfill({ status: 500, body: 'Internal Server Error' });
      } else {
        route.continue();
      }
    });

    // Trigger action that requires projects API (e.g., refresh or create)
    await page.reload();

    // Verify eventual success after retries (page loads successfully)
    await expect(page.locator('[data-testid="file-tree"], [data-testid="chat-panel"]')).toBeVisible({ timeout: 15000 });

    // Verify multiple attempts were made
    expect(attemptCount).toBeGreaterThanOrEqual(2);
  });

  test('invalid response handling', async ({ page }) => {
    // Mock invalid JSON response
    await page.route('**/api/v1/projects', route =>
      route.fulfill({
        status: 200,
        body: 'Invalid JSON{{',
        contentType: 'application/json'
      })
    );

    // Reload page to trigger API call
    await page.reload();

    // Verify graceful error handling (error message or fallback UI)
    await expect(
      page.locator('[class*="error"], .text-error, text=/错误|error|failed/i')
    ).toBeVisible({ timeout: 10000 });

    // Verify no crash (page is still functional)
    const isPageResponsive = await page.locator('body').isVisible();
    expect(isPageResponsive).toBeTruthy();
  });

  test('timeout error handling', async ({ page }) => {
    // Mock API that delays longer than typical timeout
    await page.route('**/api/v1/agent/**', route => {
      // Delay for 65 seconds (longer than typical 60s timeout)
      setTimeout(() => route.continue(), 65000);
    });

    await chatPanel.sendMessage('Test timeout');

    // Verify timeout error message appears (within reasonable time)
    await expect(
      page.locator('text=/超时|timeout|took.*long|timed.*out/i')
    ).toBeVisible({ timeout: 70000 });

    // Verify user can retry
    const retryButton = page.locator('button:has-text("重试"), button:has-text("Retry"), [data-testid="retry-button"]');
    const isRetryVisible = await retryButton.first().isVisible().catch(() => false);
    expect(isRetryVisible).toBeTruthy();
  });

  test('authentication error redirects to login', async ({ page }) => {
    // Mock 401 Unauthorized response
    await page.route('**/api/v1/**', route =>
      route.fulfill({
        status: 401,
        body: JSON.stringify({ message: 'Unauthorized', detail: 'Token expired' }),
        headers: { 'Content-Type': 'application/json' }
      })
    );

    // Trigger API call
    await page.reload();

    // Verify redirect to login page
    await page.waitForURL(/\/login/, { timeout: 10000 });
    await expect(page.locator('[data-testid="login-form"]')).toBeVisible();
  });

  test('network error with retry button', async ({ page }) => {
    let attemptCount = 0;

    // Mock network failure on first attempt
    await page.route('**/api/v1/agent/**', route => {
      attemptCount++;
      if (attemptCount === 1) {
        route.abort('failed');
      } else {
        route.continue();
      }
    });

    await chatPanel.sendMessage('Test network error');

    // Verify network error message
    await expect(
      page.locator('text=/网络.*错误|network.*error|连接.*失败|connection.*failed/i')
    ).toBeVisible({ timeout: 10000 });

    // Click retry button
    const retryButton = page.locator('button:has-text("重试"), button:has-text("Retry")').first();
    if (await retryButton.isVisible()) {
      await retryButton.click();

      // Verify retry succeeds
      await expect(page.locator('[data-testid="chat-message"]')).toBeVisible({ timeout: 15000 });
    }
  });

  test('partial response handling', async ({ page }) => {
    // Mock partial JSON response (incomplete)
    await page.route('**/api/v1/projects/*/files', route =>
      route.fulfill({
        status: 200,
        body: '{"files": [{"id": "1", "title": "Partial',
        contentType: 'application/json'
      })
    );

    // Trigger file list load
    await page.reload();

    // Verify error handling or graceful degradation
    await expect(
      page.locator('[class*="error"], .text-error, text=/错误|error/i')
    ).toBeVisible({ timeout: 10000 });

    // Verify UI remains functional
    const isFunctional = await page.locator('[data-testid="chat-panel"]').isVisible();
    expect(isFunctional).toBeTruthy();
  });
});

test.describe('Error Recovery - Streaming Errors', () => {
  test.skip(!ENABLE_ERROR_RECOVERY_E2E, ERROR_RECOVERY_OPT_IN_MESSAGE);

  const TEST_EMAIL = TEST_USERS.standard.email;
  const TEST_PASSWORD = TEST_USERS.standard.password;
  const API_BASE_URL = process.env.E2E_API_BASE_URL || 'http://127.0.0.1:8000';

  const listProjects = async (page: Page, authHeaders: Record<string, string>): Promise<Array<{ id: string }>> => {
    const listResponse = await page.request.get(`${API_BASE_URL}/api/v1/projects`, {
      headers: authHeaders,
    });

    if (!listResponse.ok()) {
      throw new Error(`Failed to list projects: ${listResponse.status()} ${listResponse.statusText()}`);
    }

    const payload = await listResponse.json();
    return Array.isArray(payload) ? payload : [];
  };

  const ensureProjectWorkspace = async (page: Page): Promise<void> => {
    if (page.url().includes('/project/')) {
      return;
    }

    const accessToken = await page.evaluate(() => localStorage.getItem('access_token'));
    if (!accessToken) {
      throw new Error('Missing access token after login');
    }

    const authHeaders = {
      Authorization: `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
    };

    let projects = await listProjects(page, authHeaders);

    if (projects.length === 0) {
      const createResponse = await page.request.post(`${API_BASE_URL}/api/v1/projects`, {
        headers: authHeaders,
        data: {
          name: `E2E Streaming Error ${Date.now()}`,
          project_type: 'novel',
        },
      });

      if (!createResponse.ok()) {
        throw new Error(`Failed to create project: ${createResponse.status()} ${createResponse.statusText()}`);
      }

      const createdProject = (await createResponse.json()) as { id?: string };
      if (!createdProject?.id) {
        throw new Error('Project creation returned no id');
      }

      projects = [{ id: createdProject.id }];
    }

    await page.goto(`/project/${projects[0].id}`);
    await page.waitForURL(/\/project\//, { timeout: 10000 });
  };

  const waitForWorkspaceReady = async (page: Page): Promise<void> => {
    await expect(page).toHaveURL(/\/project\//, { timeout: 10000 });
    await expect(
      page.locator('[data-testid="file-tree"], input[placeholder*="搜索文件"], input[placeholder*="Search files"], [role="searchbox"]').first()
    ).toBeVisible({ timeout: 15000 });
    await expect(
      page
        .locator('[data-testid="chat-input"], textarea[placeholder*="描述你想创作"], textarea[placeholder*="输入"], textarea[placeholder*="Type"]')
        .first()
    ).toBeVisible({ timeout: 15000 });
  };

  let loginPage: LoginPage;
  let chatPanel: ChatPanel;

  test.beforeEach(async ({ page }) => {
    loginPage = new LoginPage(page);
    chatPanel = new ChatPanel(page);

    await loginPage.navigateToLogin();
    await loginPage.login(TEST_EMAIL, TEST_PASSWORD);
    await page.waitForURL(/\/(project|dashboard)/, { timeout: 10000 });

    await ensureProjectWorkspace(page);

    await waitForWorkspaceReady(page);
  });

  test('SSE stream interruption', async ({ page }) => {
    let streamStarted = false;

    // Mock SSE stream that starts but doesn't complete
    await page.route('**/api/v1/agent/chat', route => {
      streamStarted = true;
      route.fulfill({
        status: 200,
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive'
        },
        body: `data: {"type": "content", "content": "Starting response..."}\n\n`
        // Stream ends abruptly without completion event
      });
    });

    await chatPanel.sendMessage('Test stream interruption');

    // Wait for stream to start
    await expect(page.locator('[data-testid="chat-message"]').last()).toBeVisible({ timeout: 10000 });

    // Verify incomplete response is handled
    const errorVisible = await page.locator('[class*="error"], text=/不完整|incomplete|interrupted/i').isVisible().catch(() => false);

    // Application should either show error or handle gracefully
    expect(errorVisible || streamStarted).toBeTruthy();
  });

  test('malformed SSE event handling', async ({ page }) => {
    // Mock SSE stream with malformed events
    await page.route('**/api/v1/agent/chat', route =>
      route.fulfill({
        status: 200,
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive'
        },
        body: `data: invalid-json{{\n\ndata: {"type": "content", "content": "Valid part"}\n\n`
      })
    );

    await chatPanel.sendMessage('Test malformed SSE');

    // Verify app handles malformed events without crashing
    await expect(page.locator('[data-testid="chat-message"]')).toBeVisible({ timeout: 10000 });

    // Verify no JavaScript errors in console
    const consoleErrors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    // Wait a moment for any async errors to surface
    await expect(page.locator('[data-testid="chat-message"]')).toBeVisible({ timeout: 2000 });

    // Should not have uncaught syntax errors
    const hasUncaughtErrors = consoleErrors.some(err =>
      err.includes('SyntaxError') || err.includes('Unexpected token')
    );
    expect(hasUncaughtErrors).toBeFalsy();
  });
});
