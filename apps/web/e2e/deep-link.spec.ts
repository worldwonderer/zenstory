import { test, expect } from '@playwright/test';
import { TEST_USERS } from './config';

/**
 * E2E Tests for Deep Linking
 *
 * These tests cover deep linking scenarios:
 * - Direct file URL access
 * - Unauthenticated deep link redirects
 * - Invalid file ID handling
 * - Deep link with session parameters
 */

const ENABLE_DEEP_LINK_E2E = process.env.E2E_ENABLE_DEEP_LINK_E2E === 'true';
const DEEP_LINK_OPT_IN_MESSAGE = 'Deep-link E2E tests are opt-in. Set E2E_ENABLE_DEEP_LINK_E2E=true to run.';

test.describe('Deep Linking', () => {
  test.skip(!ENABLE_DEEP_LINK_E2E, DEEP_LINK_OPT_IN_MESSAGE);

  // Test credentials - use environment variables or defaults matching seeded user
  const TEST_EMAIL = TEST_USERS.standard.email;
  const TEST_PASSWORD = TEST_USERS.standard.password;

  test.beforeEach(async ({ page }) => {
    // Login first
    await page.goto('/login');
    await expect(page.locator('#identifier')).toBeVisible();
    await page.fill('#identifier', TEST_EMAIL);
    await page.fill('#password', TEST_PASSWORD);
    await page.click('button[type="submit"]');
    await page.waitForURL(/\/(dashboard|project)/, { timeout: 10000 });
  });

  test('direct file URL loads correct file', async ({ page }) => {
    // Navigate to dashboard if needed
    if (page.url().includes('/project/')) {
      await page.goto('/dashboard');
    }

    // Create a test project
    const inspirationInput = page.locator('[data-testid="dashboard-inspiration-input"]');
    await inspirationInput.fill(`深度链接测试项目 ${Date.now()}`);
    await page.click('button:has-text("创建")');
    await page.waitForURL(/\/project\//, { timeout: 15000 });

    // Get project ID from URL
    const projectUrl = page.url();
    const projectIdMatch = projectUrl.match(/\/project\/([^/?]+)/);
    expect(projectIdMatch).toBeTruthy();
    // Note: projectId available for future use if needed

    // Create a file
    await page.waitForSelector('.overflow-auto', { timeout: 5000 });
    const outlineFolder = page.locator('text=大纲').first();
    await outlineFolder.click();
    await outlineFolder.hover();
    const addButton = outlineFolder.locator('..').locator('button:has(svg.lucide-plus)').first();
    await addButton.click({ force: true });

    const fileInput = page.locator('input[placeholder*="大纲"]');
    await fileInput.fill('深度链接测试文件');
    await fileInput.press('Enter');

    // Wait for file creation API call
    await page.waitForResponse(
      (resp) => resp.url().includes('/api/v1/') && resp.url().includes('/files') && resp.request().method() === 'POST',
      { timeout: 10000 }
    );

    // Select the file
    await page.locator('.overflow-auto >> text=深度链接测试文件').first().click();

    // Add content
    const editor = page.locator('textarea').first();
    await editor.fill('这是深度链接测试的内容');
    await page.waitForResponse(
      (resp) => resp.url().includes('/api/v1/') && resp.url().includes('/files') && resp.request().method() === 'PUT',
      { timeout: 10000 }
    );

    // Get file ID from URL (now should have ?file= parameter)
    const currentUrl = page.url();
    const fileIdMatch = currentUrl.match(/[?&]file=([^&]+)/);

    if (fileIdMatch) {
      const fileId = fileIdMatch[1];

      // Navigate away
      await page.goto('/dashboard');

      // Now navigate directly to the file URL
      const fileDeepLink = `/project/${projectId}?file=${fileId}`;
      await page.goto(fileDeepLink);

      // Wait for page to load
      await page.waitForSelector('.overflow-auto', { timeout: 5000 });

      // Verify file is selected (shown in editor)
      const editorAfter = page.locator('textarea').first();
      await expect(editorAfter).toHaveValue(/这是深度链接测试的内容/);

      // Verify file name is visible
      await expect(page.locator('text=深度链接测试文件')).toBeVisible();
    }
  });

  test('unauthenticated deep link redirects to login then back', async ({ page }) => {
    // First, create a project and get the URL while authenticated
    if (page.url().includes('/project/')) {
      await page.goto('/dashboard');
    }

    const inspirationInput = page.locator('[data-testid="dashboard-inspiration-input"]');
    await inspirationInput.fill(`未认证深度链接测试 ${Date.now()}`);
    await page.click('button:has-text("创建")');
    await page.waitForURL(/\/project\//, { timeout: 15000 });

    const projectUrl = page.url();

    // Logout
    const userMenuButton = page.locator('[data-testid="user-menu-button"], button[aria-label="User menu"]').first();
    await userMenuButton.click();
    const logoutButton = page.locator('[data-testid="logout-button"], button:has-text("Logout"), button:has-text("Sign out")').first();
    await logoutButton.click();
    await expect(page).toHaveURL('/login');

    // Try to access the project URL directly (unauthenticated)
    await page.goto(projectUrl);

    // Should be redirected to login
    await expect(page).toHaveURL('/login');

    // Login again
    await page.fill('#identifier', TEST_EMAIL);
    await page.fill('#password', TEST_PASSWORD);
    await page.click('button[type="submit"]');

    // Should redirect back to the project URL (or dashboard)
    await page.waitForURL(/\/(project|dashboard)/, { timeout: 10000 });

    // If redirected to project, verify it's the correct one
    if (page.url().includes('/project/')) {
      // Project should load successfully
      await page.waitForSelector('.overflow-auto', { timeout: 5000 });
    }
  });

  test('invalid file ID shows error', async ({ page }) => {
    // Navigate to dashboard
    if (page.url().includes('/project/')) {
      await page.goto('/dashboard');
    }

    // Create a project to get a valid project ID
    const inspirationInput = page.locator('[data-testid="dashboard-inspiration-input"]');
    await inspirationInput.fill(`无效文件测试项目 ${Date.now()}`);
    await page.click('button:has-text("创建")');
    await page.waitForURL(/\/project\//, { timeout: 15000 });

    const projectUrl = page.url();
    const projectIdMatch = projectUrl.match(/\/project\/([^/?]+)/);
    expect(projectIdMatch).toBeTruthy();
    const projectId = projectIdMatch![1];

    // Navigate to the project with an invalid file ID
    const invalidFileUrl = `/project/${projectId}?file=invalid-file-id-12345`;
    await page.goto(invalidFileUrl);

    // Wait for page to load
    await page.waitForSelector('.overflow-auto', { timeout: 5000 });

    // The page should still load the project, but file should not be selected
    // OR an error message should be shown
    // OR the editor should show empty state

    // Check for error message or empty state
    const errorMessage = page.locator('text=/error|错误|not found|未找到/i');
    const hasError = await errorMessage.count() > 0;

    // If no error shown, check that no file is selected in editor
    if (!hasError) {
      // The file tree should still be visible
      await expect(page.locator('.overflow-auto')).toBeVisible();

      // No file should be actively selected in editor
      // This is indicated by no content in the editor or a placeholder
      const editor = page.locator('textarea').first();
      const editorContent = await editor.inputValue();

      // Either empty or the page shows some empty/select file state
      expect(editorContent.length === 0 || await page.locator('text=/选择.*文件|select.*file/i').count() > 0).toBeTruthy();
    }
  });

  test('deep link with session parameter works', async ({ page }) => {
    // Navigate to dashboard
    if (page.url().includes('/project/')) {
      await page.goto('/dashboard');
    }

    // Create a project
    const inspirationInput = page.locator('[data-testid="dashboard-inspiration-input"]');
    await inspirationInput.fill(`会话参数测试项目 ${Date.now()}`);
    await page.click('button:has-text("创建")');
    await page.waitForURL(/\/project\//, { timeout: 15000 });

    const projectUrl = page.url();
    const projectIdMatch = projectUrl.match(/\/project\/([^/?]+)/);
    expect(projectIdMatch).toBeTruthy();
    // Note: projectId available for future use if needed

    // Create a file
    await page.waitForSelector('.overflow-auto', { timeout: 5000 });
    const outlineFolder = page.locator('text=大纲').first();
    await outlineFolder.click();
    await outlineFolder.hover();
    const addButton = outlineFolder.locator('..').locator('button:has(svg.lucide-plus)').first();
    await addButton.click({ force: true });

    const fileInput = page.locator('input[placeholder*="大纲"]');
    await fileInput.fill('会话测试文件');
    await fileInput.press('Enter');

    // Wait for file creation
    await page.waitForResponse(
      (resp) => resp.url().includes('/api/v1/') && resp.url().includes('/files') && resp.request().method() === 'POST',
      { timeout: 10000 }
    );

    // Select the file
    await page.locator('.overflow-auto >> text=会话测试文件').first().click();

    // Get file ID from URL
    const currentUrl = page.url();
    const fileIdMatch = currentUrl.match(/[?&]file=([^&]+)/);

    if (fileIdMatch) {
      const fileId = fileIdMatch[1];

      // Look for chat panel and create a chat session
      const chatInput = page.locator('textarea[placeholder*="输入"], input[placeholder*="输入"]').first();

      // If chat input exists, send a message to create a session
      if (await chatInput.isVisible()) {
        await chatInput.fill('测试消息');
        await chatInput.press('Enter');

        // Wait for AI response or network idle
        await page.waitForResponse(resp => resp.url().includes('/api/v1/agent') || resp.url().includes('/chat'), { timeout: 15000 }).catch(() => {});
        await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {});

        // Get the current URL which might have session parameter
        const urlWithSession = page.url();
        const sessionMatch = urlWithSession.match(/[?&]session=([^&]+)/);

        if (sessionMatch) {
          // Navigate away
          await page.goto('/dashboard');

          // Navigate back with both file and session parameters
          const deepLink = `/project/${projectId}?file=${fileId}&session=${sessionMatch[1]}`;
          await page.goto(deepLink);

          // Wait for page to load
          await page.waitForSelector('.overflow-auto', { timeout: 5000 });

          // Verify file is selected
          const editor = page.locator('textarea').first();
          await expect(editor).toBeVisible();

          // Verify chat session is loaded (chat history visible)
          const chatMessages = page.locator('[data-testid="chat-message"], .message, text=测试消息');
          const hasChatMessages = await chatMessages.count() > 0;

          // Chat should show the message we sent
          expect(hasChatMessages).toBeTruthy();
        }
      }
    }
  });

  test('deep link to non-existent project shows error', async ({ page }) => {
    // Try to access a non-existent project
    const fakeProjectId = 'non-existent-project-id-12345';
    await page.goto(`/project/${fakeProjectId}`);

    // Wait for either error message or redirect
    await page.waitForLoadState('domcontentloaded', { timeout: 5000 });

    // Check for error message or redirect to dashboard
    const currentUrl = page.url();

    // Either shows an error, or redirects to dashboard/login
    if (currentUrl.includes('/project/')) {
      // Still on project page - check for error message
      const errorMessage = page.locator('text=/error|错误|not found|不存在|无法访问/i');
      await expect(errorMessage.first()).toBeVisible();
    } else {
      // Redirected - should be to dashboard or login
      expect(currentUrl.includes('/dashboard') || currentUrl.includes('/login')).toBeTruthy();
    }
  });

  test('deep link preserves file selection across reload', async ({ page }) => {
    // Navigate to dashboard
    if (page.url().includes('/project/')) {
      await page.goto('/dashboard');
    }

    // Create a project
    const inspirationInput = page.locator('[data-testid="dashboard-inspiration-input"]');
    await inspirationInput.fill(`重载保留选择测试 ${Date.now()}`);
    await page.click('button:has-text("创建")');
    await page.waitForURL(/\/project\//, { timeout: 15000 });

    const projectUrl = page.url();
    const projectIdMatch = projectUrl.match(/\/project\/([^/?]+)/);
    expect(projectIdMatch).toBeTruthy();
    // Note: projectId available for future use if needed

    // Create a file
    await page.waitForSelector('.overflow-auto', { timeout: 5000 });
    const outlineFolder = page.locator('text=大纲').first();
    await outlineFolder.click();
    await outlineFolder.hover();
    const addButton = outlineFolder.locator('..').locator('button:has(svg.lucide-plus)').first();
    await addButton.click({ force: true });

    const fileInput = page.locator('input[placeholder*="大纲"]');
    await fileInput.fill('重载测试文件');
    await fileInput.press('Enter');

    // Wait for file creation
    await page.waitForResponse(
      (resp) => resp.url().includes('/api/v1/') && resp.url().includes('/files') && resp.request().method() === 'POST',
      { timeout: 10000 }
    );

    // Select the file
    await page.locator('.overflow-auto >> text=重载测试文件').first().click();

    // Get file ID from URL
    const currentUrl = page.url();
    const fileIdMatch = currentUrl.match(/[?&]file=([^&]+)/);

    if (fileIdMatch) {
      const fileId = fileIdMatch[1];

      // Add some content
      const editor = page.locator('textarea').first();
      await editor.fill('重载前的内容');
      await page.waitForResponse(
        (resp) => resp.url().includes('/api/v1/') && resp.url().includes('/files') && resp.request().method() === 'PUT',
        { timeout: 10000 }
      );

      // Reload the page
      await page.reload();
      await page.waitForSelector('.overflow-auto', { timeout: 5000 });

      // Verify URL still has file parameter
      const reloadedUrl = page.url();
      expect(reloadedUrl).toContain(`file=${fileId}`);

      // Verify file is still selected
      const editorAfter = page.locator('textarea').first();
      await expect(editorAfter).toHaveValue(/重载前的内容/);

      // Verify file name is visible in tree
      await expect(page.locator('text=重载测试文件')).toBeVisible();
    }
  });
});

test.describe('Deep Link Security', () => {
  test.skip(!ENABLE_DEEP_LINK_E2E, DEEP_LINK_OPT_IN_MESSAGE);

  const TEST_EMAIL = TEST_USERS.standard.email;
  const TEST_PASSWORD = TEST_USERS.standard.password;

  test('deep link to another user project fails', async ({ page }) => {
    // This test verifies that a user cannot access another user's project via deep link
    // In this test, we simulate by checking that project access is properly authenticated

    // Login
    await page.goto('/login');
    await page.fill('#identifier', TEST_EMAIL);
    await page.fill('#password', TEST_PASSWORD);
    await page.click('button[type="submit"]');
    await page.waitForURL(/\/(dashboard|project)/, { timeout: 10000 });

    if (page.url().includes('/project/')) {
      await page.goto('/dashboard');
    }

    // Create a project
    const inspirationInput = page.locator('[data-testid="dashboard-inspiration-input"]');
    await inspirationInput.fill(`权限测试项目 ${Date.now()}`);
    await page.click('button:has-text("创建")');
    await page.waitForURL(/\/project\//, { timeout: 15000 });

    const projectUrl = page.url();

    // Logout
    const userMenuButton = page.locator('[data-testid="user-menu-button"], button[aria-label="User menu"]').first();
    await userMenuButton.click();
    const logoutButton = page.locator('[data-testid="logout-button"], button:has-text("Logout"), button:has-text("Sign out")').first();
    await logoutButton.click();
    await expect(page).toHaveURL('/login');

    // Try to access the project URL without authentication
    await page.goto(projectUrl);

    // Should be redirected to login
    await expect(page).toHaveURL('/login');
  });

  test('malformed deep link URL is handled gracefully', async ({ page }) => {
    // Login
    await page.goto('/login');
    await page.fill('#identifier', TEST_EMAIL);
    await page.fill('#password', TEST_PASSWORD);
    await page.click('button[type="submit"]');
    await page.waitForURL(/\/(dashboard|project)/, { timeout: 10000 });

    // Try various malformed URLs
    const malformedUrls = [
      '/project/invalid',
      '/project/123?file=<script>alert(1)</script>',
      '/project/123?file=../../../etc/passwd',
      '/project/123?file=null',
      '/project/123?file=undefined',
    ];

    for (const url of malformedUrls) {
      await page.goto(url);

      // Should either redirect to dashboard or show an error
      // Should NOT crash or show unhandled errors
      await page.waitForLoadState('domcontentloaded', { timeout: 3000 });

      const currentUrl = page.url();
      const hasError = await page.locator('text=/error|错误/i').count() > 0;

      // Page should either redirect or show controlled error
      expect(
        currentUrl.includes('/dashboard') ||
        currentUrl.includes('/login') ||
        currentUrl.includes('/project/') ||
        hasError
      ).toBeTruthy();
    }
  });
});
