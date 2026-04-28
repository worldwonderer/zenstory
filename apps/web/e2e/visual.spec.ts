import { test, expect } from '@playwright/test';
import { TEST_USERS } from './config';

/**
 * Visual Regression Tests
 *
 * Snapshot tests for key UI components and layouts.
 * Run with: pnpm exec playwright test visual.spec.ts
 * Update snapshots: pnpm exec playwright test visual.spec.ts --update-snapshots
 */

const VISUAL_REGRESSION_E2E_ENABLED = process.env.E2E_ENABLE_VISUAL_REGRESSION_E2E === 'true';

test.skip(
  !VISUAL_REGRESSION_E2E_ENABLED,
  'Visual regression requires committed baseline snapshots. Set E2E_ENABLE_VISUAL_REGRESSION_E2E=true to run/update them.'
);

test.describe('Visual Regression', () => {
  const TEST_EMAIL = TEST_USERS.standard.email;
  const TEST_PASSWORD = TEST_USERS.standard.password;

  test.beforeEach(async ({ page }) => {
    // Login using testids
    await page.goto('/login');
    await page.getByTestId('email-input').fill(TEST_EMAIL);
    await page.getByTestId('password-input').fill(TEST_PASSWORD);
    await page.getByTestId('login-submit').click();
    await page.waitForURL('**/dashboard');
  });

  test('dashboard matches snapshot', async ({ page }) => {
    await page.goto('/dashboard');
    // Wait for content to load
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveScreenshot('dashboard.png', {
      maxDiffPixels: 100,
    });
  });

  test('project page layout', async ({ page }) => {
    // Navigate to dashboard first
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');

    // Find and click on first project card
    const projectCard = page.getByTestId('project-card').first();
    if (await projectCard.isVisible()) {
      await projectCard.click();
      await page.waitForURL(/\/project\//, { timeout: 5000 });
      await page.waitForLoadState('networkidle');

      await expect(page).toHaveScreenshot('project-page.png', {
        fullPage: true,
        maxDiffPixels: 100,
      });
    } else {
      // Skip if no projects available
      test.skip();
    }
  });

  test('chat panel empty state', async ({ page }) => {
    // Navigate to project page
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');

    const projectCard = page.getByTestId('project-card').first();
    if (await projectCard.isVisible()) {
      await projectCard.click();
      await page.waitForURL(/\/project\//, { timeout: 5000 });
      await page.waitForLoadState('networkidle');

      // Take snapshot of chat panel in empty state
      await expect(page.getByTestId('chat-panel')).toHaveScreenshot('chat-empty.png', {
        maxDiffPixels: 100,
      });
    } else {
      test.skip();
    }
  });

  test('chat panel with messages', async ({ page }) => {
    // Navigate to project page
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');

    const projectCard = page.getByTestId('project-card').first();
    if (await projectCard.isVisible()) {
      await projectCard.click();
      await page.waitForURL(/\/project\//, { timeout: 5000 });
      await page.waitForLoadState('networkidle');

      // Send test message using chat-input
      const chatInput = page.getByTestId('chat-input');
      if (await chatInput.isVisible()) {
        await chatInput.fill('Test message');
        await page.getByTestId('send-button').click();

        // Wait for message to appear and streaming to complete
        // Wait for streaming cursor to disappear (indicates completion)
        await expect(page.locator('.animate-pulse.w-1\\.5')).not.toBeVisible({ timeout: 10000 }).catch(() => {
          // Streaming may have completed too fast or not started, continue with screenshot
        });

        await expect(page.getByTestId('chat-panel')).toHaveScreenshot('chat-with-messages.png', {
          maxDiffPixels: 100,
        });
      } else {
        test.skip();
      }
    } else {
      test.skip();
    }
  });

  test('mobile layout at 375px', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');

    await expect(page).toHaveScreenshot('mobile-layout.png', {
      fullPage: true,
      maxDiffPixels: 100,
    });
  });
});
