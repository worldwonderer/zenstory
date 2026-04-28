import { test, expect, Page } from '@playwright/test';
import { TEST_USERS } from './config';
import { SettingsPOM } from './fixtures/page-objects/SettingsPOM';

const TEST_EMAIL = TEST_USERS.standard.email;
const TEST_PASSWORD = TEST_USERS.standard.password;

async function login(page: Page) {
  await page.goto('/login');
  await expect(page.locator('h1')).toContainText('登录');
  await page.locator('#identifier').fill(TEST_EMAIL);
  await page.locator('#password').fill(TEST_PASSWORD);
  await page.locator('button[type="submit"]').click();
  await page.waitForURL(/\/(project|dashboard)/, { timeout: 10000 });
  await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {});
}

test.describe('Dashboard Sidebar Settings Regression', () => {
  let settings: SettingsPOM;

  test.beforeEach(async ({ page }) => {
    settings = new SettingsPOM(page);
    await login(page);
  });

  test('opens settings dialog from dashboard lower-left user panel', async () => {
    await settings.openSettings();
    await expect(settings.settingsDialog).toBeVisible();
  });

  test('closes with close button', async () => {
    await settings.openSettings();
    await settings.closeSettings();
    await expect(settings.settingsDialog).not.toBeVisible();
  });

  test('closes with Escape key', async () => {
    await settings.openSettings();
    await settings.closeSettingsByEscape();
    await expect(settings.settingsDialog).not.toBeVisible();
  });

  test('closes when clicking outside dialog', async () => {
    await settings.openSettings();
    await settings.closeSettingsByBackdropClick();
    await expect(settings.settingsDialog).not.toBeVisible();
  });

  test('switches language, theme, and accent color from sidebar settings entry', async () => {
    await settings.openSettings();
    await settings.switchToTab('general');

    await settings.setLanguage('en');
    expect(await settings.getCurrentLanguage()).toBe('en');

    await settings.setTheme('dark');
    expect(await settings.getCurrentTheme()).toBe('dark');

    const colors = await settings.getAvailableAccentColors();
    expect(colors.length).toBeGreaterThan(0);
    const currentColor = await settings.getCurrentAccentColor();
    const targetColor = colors.find((color) => color !== currentColor) ?? colors[0];
    await settings.setAccentColor(targetColor);
    expect(await settings.getCurrentAccentColor()).toBe(targetColor);
  });

  test('persists language, theme, and accent color after reload', async ({ page }) => {
    await settings.openSettings();
    await settings.switchToTab('general');

    await settings.setLanguage('en');
    await settings.setTheme('dark');

    const colors = await settings.getAvailableAccentColors();
    const currentColor = await settings.getCurrentAccentColor();
    const targetColor = colors.find((color) => color !== currentColor) ?? colors[0];
    await settings.setAccentColor(targetColor);

    await settings.closeSettings();

    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {});

    await settings.openSettings();
    await settings.switchToTab('general');
    expect(await settings.getCurrentLanguage()).toBe('en');
    expect(await settings.getCurrentTheme()).toBe('dark');
    expect(await settings.getCurrentAccentColor()).toBe(targetColor);
  });
});
