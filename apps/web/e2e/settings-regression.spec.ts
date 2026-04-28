import { test, expect } from '@playwright/test';
import { TEST_USERS } from './config';
import { SettingsRegressionPOM } from './fixtures/page-objects/SettingsRegressionPOM';

const TEST_EMAIL = TEST_USERS.standard.email;
const TEST_PASSWORD = TEST_USERS.standard.password;

async function login(page: import('@playwright/test').Page) {
  await page.goto('/login');
  await expect(page.locator('#identifier')).toBeVisible();
  await page.locator('#identifier').fill(TEST_EMAIL);
  await page.locator('#password').fill(TEST_PASSWORD);
  await page.locator('button[type="submit"]').click();
  await page.waitForURL(/\/(project|dashboard)/, { timeout: 10000 });
  await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {});
}

test.describe('Settings Regression (dashboard left-bottom entry)', () => {
  test('language/theme/accent changes from dashboard user panel apply and persist', async ({ page }) => {
    const settings = new SettingsRegressionPOM(page);
    const accentColor = '#8b5cf6';

    await login(page);

    if (!page.url().includes('/dashboard')) {
      await page.goto('/dashboard');
    }
    await expect(page.getByTestId('dashboard-user-panel-toggle').first()).toBeVisible();

    await settings.openGeneralTab();

    await settings.setLanguage('en');
    await settings.expectLanguageStored('en');
    await settings.expectProfileTabLabel('Profile');

    await settings.setTheme('light');
    await settings.expectThemeStored('light');
    await settings.expectHtmlThemeClass('light');

    await settings.setAccentColor(accentColor);
    await settings.expectAccentStored(accentColor);
    await settings.expectAccentPrimaryCssVar(accentColor);
    await settings.expectAccentButtonSelected(accentColor);

    await settings.closeSettings();

    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle').catch(() => {});
    await expect(page.getByTestId('dashboard-user-panel-toggle').first()).toBeVisible();

    await settings.expectLanguageStored('en');
    await settings.expectThemeStored('light');
    await settings.expectHtmlThemeClass('light');
    await settings.expectAccentStored(accentColor);
    await settings.expectAccentPrimaryCssVar(accentColor);

    await settings.openGeneralTab();
    await settings.expectProfileTabLabel('Profile');
    await settings.expectAccentButtonSelected(accentColor);
  });
});
