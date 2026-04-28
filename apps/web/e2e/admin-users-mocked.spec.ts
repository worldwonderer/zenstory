import { expect, test, type Page } from '@playwright/test';

const adminUser = {
  id: 'admin-1',
  username: 'admin',
  email: 'admin@example.com',
  email_verified: true,
  is_active: true,
  is_superuser: true,
  created_at: '2026-03-01T00:00:00Z',
  updated_at: '2026-03-01T00:00:00Z',
};

const baseUser = {
  id: 'user-1',
  username: 'writer',
  email: 'writer@example.com',
  email_verified: true,
  is_active: true,
  is_superuser: false,
  created_at: '2026-03-01T00:00:00Z',
  updated_at: '2026-03-01T00:00:00Z',
};

async function bootstrapAdminSession(page: Page) {
  await page.route('**/api/auth/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(adminUser),
    });
  });

  await page.route('**/api/auth/refresh', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        access_token: 'mock-access-token',
        refresh_token: 'mock-refresh-token',
        user: adminUser,
      }),
    });
  });

  await page.route('**/api/v1/projects**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
    });
  });

  await page.route('**/api/v1/materials/library-summary**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
    });
  });

  await page.addInitScript((user) => {
    localStorage.setItem('access_token', 'mock-access-token');
    localStorage.setItem('refresh_token', 'mock-refresh-token');
    localStorage.setItem('token_type', 'bearer');
    localStorage.setItem('user', JSON.stringify(user));
    localStorage.setItem('auth_validated_at', Date.now().toString());
  }, adminUser);
}

test.describe('Admin users (mocked)', () => {
  test('can search, edit, and delete a user', async ({ page }) => {
    await bootstrapAdminSession(page);

    const searchedTerms: string[] = [];
    let updatePayload: Record<string, unknown> | null = null;
    let deleteCalled = 0;

    await page.route('**/api/admin/users**', async (route) => {
      const request = route.request();
      const url = new URL(request.url());

      if (request.method() === 'GET') {
        const search = url.searchParams.get('search');
        if (search) {
          searchedTerms.push(search);
        }

        const items = search && search !== 'writer' ? [] : [baseUser];
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ items }),
        });
        return;
      }

      if (request.method() === 'PUT') {
        updatePayload = request.postDataJSON() as Record<string, unknown>;
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ...baseUser,
            ...updatePayload,
            updated_at: '2026-03-08T00:00:00Z',
          }),
        });
        return;
      }

      if (request.method() === 'DELETE') {
        deleteCalled += 1;
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ message: 'deleted' }),
        });
        return;
      }

      await route.continue();
    });

    await page.goto('/admin/users');
    const row = page.locator('table tbody tr', { hasText: 'writer@example.com' }).first();
    await expect(row).toBeVisible();

    await page.locator('input[placeholder*="搜索"], input[placeholder*="Search"]').fill('writer');
    await page.getByRole('button', { name: /搜索|search/i }).click();
    await expect.poll(() => searchedTerms.includes('writer')).toBe(true);

    await row.locator('button').first().click();
    const editModal = page.locator('.fixed.inset-0.z-50').first();
    await editModal.locator('input[type="text"]').fill('writer-updated');
    await editModal.getByRole('button', { name: /保存|save/i }).click();

    await expect.poll(() => updatePayload).not.toBeNull();
    expect(updatePayload).toMatchObject({
      username: 'writer-updated',
      email: 'writer@example.com',
      is_active: true,
      is_superuser: false,
    });

    await row.locator('button').nth(1).click();
    const deleteModal = page.locator('.fixed.inset-0.z-50').last();
    await deleteModal.getByRole('button', { name: /确认|confirm/i }).click();
    await expect.poll(() => deleteCalled).toBe(1);
  });
});
