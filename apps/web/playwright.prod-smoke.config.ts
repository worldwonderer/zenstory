import { defineConfig, devices } from '@playwright/test'

const LOCALHOST_NO_PROXY_ENTRIES = ['127.0.0.1', 'localhost']

function ensureLocalNoProxy() {
  const merged = Array.from(
    new Set(
      [process.env.NO_PROXY, process.env.no_proxy]
        .filter(Boolean)
        .flatMap((value) => value!.split(','))
        .map((value) => value.trim())
        .filter(Boolean)
        .concat(LOCALHOST_NO_PROXY_ENTRIES)
    )
  ).join(',')

  process.env.NO_PROXY = merged
  process.env.no_proxy = merged
}

ensureLocalNoProxy()

export default defineConfig({
  testDir: './e2e',
  testMatch: /.*prod-bundle-smoke\.spec\.ts/,
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? [['github'], ['html']] : 'html',
  timeout: 30000,
  expect: {
    timeout: 10000,
  },
  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://127.0.0.1:4173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    actionTimeout: 10000,
    navigationTimeout: 15000,
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
