# E2E Testing Guide

This guide provides comprehensive documentation for the zenstory E2E test suite using Playwright.

## Suite taxonomy

The browser suite is intentionally split by **release signal**, not only by page name.

| Suite class | Purpose | Typical filenames | CI expectation |
|---|---|---|---|
| Smoke | Release-blocking critical path checks | `smoke.spec.ts`, `prod-bundle-smoke.spec.ts`, auth critical-path specs | Must stay fast and reliable; PR-blocking |
| Regression | Core product workflows against the app/backend | `projects.spec.ts`, `files.spec.ts`, `chat.spec.ts`, `settings.spec.ts` | Important, but may be selectively sharded or subset on PRs |
| Mocked browser regression | Frontend browser checks with mocked/high-cost dependencies | `*.mocked.spec.ts` | Useful for UI confidence; not a substitute for full-flow E2E |
| Specialized signals | Non-primary regression signals | `accessibility.spec.ts`, `visual.spec.ts`, `performance.spec.ts`, `security.spec.ts`, `mobile.spec.ts` | Report separately; interpret differently from core product failures |

### Current classification guidance

- **Smoke**
  - `smoke.spec.ts`
  - `prod-bundle-smoke.spec.ts`
  - auth happy-path coverage used to prove users can still enter the product
- **Regression**
  - projects / files / chat / materials / settings / subscription / referral / points / versions / inspirations
- **Mocked**
  - any browser suite with `mocked` in the filename
- **Specialized**
  - accessibility / visual / performance / security / mobile

When adding a new browser test, decide its class first. If a scenario is mostly proving the UI contract under mocked data, prefer `*.mocked.spec.ts`. If it protects release-critical behavior, keep it in smoke or clearly document why it belongs in regression.

## Lane ownership and promotion policy

The browser suite is also split by **execution lane**:

Canonical maintainer governance note:

- `docs/advanced/e2e-lane-governance-2026-04.md`

| Lane | Suites | Owner role | Notes |
|---|---|---|---|
| `default required` | auth, session, projects, points, onboarding-persona, public-skills, referral, security, subscription, settings, settings-regression, smoke | web functional gate owner | Must stay PR-stable |
| `nightly` | versions, skills, skills-flow | web nightly owner + supporting backend contract owner | Requires dedicated seeded states |
| `permanent opt-in` | visual, performance, large-document, concurrent, voice interaction | specialized suite owner | Does not block default PR gate |

### Fixture / state ownership

| Concern | Owner role |
|---|---|
| seeded quota personas | subscription/quota owner |
| seeded version-rich project fixtures | versions owner |
| voice configured/unconfigured env | voice owner |
| visual baselines | visual regression owner |

### Promotion rules

#### opt-in -> nightly
- 7 consecutive days green
- failure rate under 5%
- no manual steps
- clean-environment reproducibility
- seeded fixtures documented

#### nightly -> default required
- 14 consecutive days green
- failure rate under 1%
- fits PR runtime budget
- no unstable external dependency
- failures are diagnosable and reproducible

## Table of Contents

1. [Running Tests](#running-tests)
2. [Writing New Tests](#writing-new-tests)
3. [Test Data Management](#test-data-management)
4. [Mock System Usage](#mock-system-usage)
5. [Debugging Failed Tests](#debugging-failed-tests)
6. [Visual Regression Workflow](#visual-regression-workflow)
7. [CI/CD Integration](#cicd-integration)

---

## Running Tests

### Prerequisites

Ensure the test environment is properly configured:

```bash
# Recommended: one command to bootstrap local zenstory E2E
cd <repo-root>
pnpm e2e:zenstory:local
```

This local entrypoint reuses the repository's Lite E2E orchestration to:
- initialize a SQLite test database
- seed the regular/admin E2E users expected by `auth.setup.ts`
- start backend/frontend on localhost
- force localhost into `NO_PROXY` / `no_proxy` so proxy-heavy shells do not break Playwright health checks
- disable async vector indexing noise during local E2E runs
- run the smoke-focused Chromium suite by default for fast local confidence

If you want the full browser regression instead of the stable local suite:

```bash
cd <repo-root>
pnpm e2e:zenstory:local:full
```

If you prefer to prepare things manually, use the steps below:

```bash
# Install Playwright browsers
cd apps/web
pnpm exec playwright install

# Verify backend database has test user seeded
cd apps/server
python scripts/seed_test_user.py
```

Key environment variables:

- `E2E_BASE_URL` - frontend base URL (default `http://127.0.0.1:5173`)
- `E2E_API_URL` - backend base URL (default `http://127.0.0.1:8000`)
- `E2E_TEST_EMAIL`
- `E2E_TEST_PASSWORD`
- `E2E_TEST_USERNAME`

`auth.setup.ts` now reads the API base from shared e2e config instead of hardcoding localhost. Keep all environment-sensitive values flowing through `e2e/config/`.

### Local Execution

Run all E2E tests:

```bash
cd apps/web
pnpm test:e2e
```

If your shell exports `HTTP_PROXY` / `HTTPS_PROXY`, the Playwright configs now append `127.0.0.1,localhost` to `NO_PROXY` / `no_proxy` automatically so localhost health checks stay direct.

Run with Playwright UI (interactive mode):

```bash
pnpm test:e2e:ui
```

Run in headed mode (see browser actions):

```bash
pnpm test:e2e:headed
```

Run in debug mode (step-through with inspector):

```bash
pnpm test:e2e:debug
```

### Specific Browser Testing

Run tests on a specific browser:

```bash
# Chromium only (default for PRs)
pnpm test:e2e:chromium

# All browsers (main/develop branches)
pnpm test:e2e:all-browsers
```

Available browser projects (configured in `playwright.config.ts`):
- `chromium` - Headless Chrome (CI default)
- `chromium-headed` - Chrome with UI and slow motion
- `firefox` - Headless Firefox
- `webkit` - Headless Safari

### Smoke Tests

Run fast critical-path tests (used on PRs):

```bash
pnpm test:smoke
```

Smoke tests cover:
- User login
- Project creation
- File creation
- Chat message sending
- Project export
- Production bundle / stale chunk sanity via `prod-bundle-smoke.spec.ts`

### Dashboard Coachmark Tour

The dashboard coachmark tour is feature-flagged. To run its Playwright spec, enable the frontend flag when launching Playwright:

```bash
cd apps/web
VITE_DASHBOARD_COACHMARK_TOUR_ENABLED=true pnpm exec playwright test e2e/dashboard-coachmark.spec.ts --project=chromium
```

### Debug Mode

The debug mode opens Playwright Inspector for step-through debugging:

```bash
# Debug specific test file
pnpm exec playwright test auth.spec.ts --debug

# Debug with headed browser
pnpm exec playwright test --project=chromium-headed --debug
```

---

## Writing New Tests

### Test Patterns and Best Practices

#### 1. Use Page Object Models (POMs)

Always use Page Object Models for maintainable tests:

```typescript
import { test, expect } from '@playwright/test';
import { LoginPage } from './fixtures/page-objects/LoginPage';
import { DashboardPage } from './fixtures/page-objects/DashboardPage';

test.describe('Project Management', () => {
  let loginPage: LoginPage;
  let dashboardPage: DashboardPage;

  test.beforeEach(async ({ page }) => {
    loginPage = new LoginPage(page);
    dashboardPage = new DashboardPage(page);

    await loginPage.navigateToLogin();
    await loginPage.loginAndWaitForDashboard(
      process.env.E2E_TEST_EMAIL || 'e2e-test@zenstory.local',
      process.env.E2E_TEST_PASSWORD || 'E2eTestPassword123!'
    );
  });

  test('user can create a project', async ({ page }) => {
    await dashboardPage.createProject('Test Project', 'Test description');
    await expect(page.getByTestId('project-card').filter({ hasText: 'Test Project' })).toBeVisible();
  });
});
```

#### 2. Use data-testid Attributes

All interactive elements should have `data-testid` attributes:

```typescript
// Good - uses testid
await page.getByTestId('login-submit').click();

// Avoid - fragile CSS selectors
await page.locator('button.btn-primary').click();
```

#### 3. Wait for Network Idle

After navigation or major actions, wait for network requests to complete:

```typescript
await page.goto('/dashboard');
await page.waitForLoadState('networkidle');
```

#### 4. Use Unique Test Data

Generate unique names to avoid test conflicts:

```typescript
import { generateUniqueName } from './utils/test-helpers';

test('create unique project', async ({ page }) => {
  const projectName = generateUniqueName('test-project');
  // => 'test-project-2026-02-14T12-34-56-abc123'

  await dashboardPage.createProject(projectName, 'Description');
});
```

#### 5. Parallel Test Execution

Configure tests to run in parallel when possible:

```typescript
test.describe.configure({ mode: 'parallel' });

test.describe('Independent Tests', () => {
  // These tests can run in parallel
});
```

### Using Page Object Models

Page Object Models encapsulate page interactions in reusable classes.

## Maintenance rules

1. Do not leave `.new`, `.bak`, or shadow spec files in `e2e/`; finish the migration or delete the draft.
2. Keep mocked tests explicitly named with `mocked` in the filename.
3. Prefer shared config/runtime values from `e2e/config/` over hardcoded URLs.
4. When an incident drives a new browser regression (for example stale deploy chunks), classify it explicitly as smoke or specialized and document why.

#### Creating a New Page Object

```typescript
// fixtures/page-objects/MyNewPage.ts
import { BasePage } from './BasePage';
import { Page } from '@playwright/test';

export class MyNewPage extends BasePage {
  constructor(page: Page) {
    super(page);
  }

  async navigateToMyPage() {
    await this.navigate('/my-page');
  }

  async performAction(value: string) {
    await this.fillByTestId('action-input', value);
    await this.clickByTestId('action-button');
  }

  async waitForResult() {
    await this.waitForTestId('result-display');
  }
}
```

#### Available BasePage Methods

```typescript
// Navigation
await page.navigate('/path');
await page.waitForURL('/pattern');

// Element interactions by testid
await page.clickByTestId('button-id');
await page.fillByTestId('input-id', 'value');
await page.waitForTestId('element-id');
const text = await page.getTextByTestId('element-id');
const isVisible = await page.isVisibleByTestId('element-id');

// Get locator for advanced operations
const locator = page.getLocatorByTestId('element-id');
```

### Using Helper Utilities

#### Test Helpers (`utils/test-helpers.ts`)

```typescript
import {
  generateUniqueName,
  timestamp,
  randomString,
  waitFor
} from './utils/test-helpers';

// Generate unique test data
const projectName = generateUniqueName('project');
// => 'project-2026-02-14T12-34-56-abc123'

// Get timestamp
const ts = timestamp();
// => '2026-02-14T12-34-56'

// Generate random string
const id = randomString(8);
// => 'k9x2mp4q'

// Wait for custom condition
await waitFor(
  async () => {
    const element = await page.$('.loaded');
    return element !== null;
  },
  { timeout: 10000, interval: 200 }
);
```

#### API Helpers (`utils/api-helpers.ts`)

Direct API operations for test setup:

```typescript
import { createProject, deleteProject, createFile } from './utils/api-helpers';

test.beforeEach(async ({ request }) => {
  // Create test project via API
  const project = await createProject(request, {
    title: 'Setup Project',
    description: 'Created via API'
  });

  // Create test file
  await createFile(request, project.id, {
    title: 'Test File',
    file_type: 'draft'
  });
});

test.afterEach(async ({ request }) => {
  // Cleanup
  await deleteProject(request, project.id);
});
```

### Example Test Template

Complete test file template:

```typescript
import { test, expect } from '@playwright/test';
import { LoginPage } from './fixtures/page-objects/LoginPage';
import { DashboardPage } from './fixtures/page-objects/DashboardPage';
import { generateUniqueName } from './utils/test-helpers';

test.describe('Feature Name', () => {
  // Configure test mode
  test.describe.configure({ mode: 'parallel' });

  let loginPage: LoginPage;
  let dashboardPage: DashboardPage;

  test.beforeEach(async ({ page }) => {
    // Initialize page objects
    loginPage = new LoginPage(page);
    dashboardPage = new DashboardPage(page);

    // Login
    await loginPage.navigateToLogin();
    await loginPage.loginAndWaitForDashboard(
      process.env.E2E_TEST_EMAIL || 'e2e-test@zenstory.local',
      process.env.E2E_TEST_PASSWORD || 'E2eTestPassword123!'
    );
  });

  test('should perform action successfully', async ({ page }) => {
    // Arrange
    const testName = generateUniqueName('test-item');

    // Act
    await dashboardPage.performAction(testName);

    // Assert
    await expect(page.getByTestId('result')).toBeVisible();
    await expect(page.getByTestId('result')).toContainText(testName);
  });

  test('should handle error gracefully', async ({ page }) => {
    // Test error scenario
    await dashboardPage.triggerError();

    // Verify error message
    await expect(page.getByTestId('error-message')).toBeVisible();
  });
});
```

---

## Test Data Management

### Test Users Configuration

Test users are defined in `config/test-users.ts`:

```typescript
import { TEST_USERS, getPoolUser, getWorkerUser } from './config/test-users';

// Standard test user
const standardUser = TEST_USERS.standard;
// => { email: 'e2e-test@zenstory.local', password: 'E2eTestPassword123!', username: 'e2e-test-user' }

// Admin test user
const adminUser = TEST_USERS.admin;
// => { email: 'test-admin@zenstory.test', password: 'TestAdmin123!', username: 'test-admin' }

// Pool users for parallel test isolation
const poolUser = getPoolUser(0); // Index 0-4 available

// Worker-specific user (for parallel workers)
const workerUser = getWorkerUser(workerIndex);
```

### Environment Variables

Configure tests via environment variables:

```bash
# Test credentials
export E2E_TEST_EMAIL=e2e-test@zenstory.local
export E2E_TEST_PASSWORD=E2eTestPassword123!
export E2E_TEST_USERNAME=e2e_test_user

# Custom base URL
export E2E_BASE_URL=http://localhost:5173

# CI mode
export CI=true
```

Environment variables are loaded in this priority:
1. Process environment (`export E2E_TEST_EMAIL=...`)
2. `.env` file in project root
3. Default values in `config/test-users.ts`

### Data Isolation Strategies

#### 1. Unique Identifiers

Always generate unique names for test data:

```typescript
import { generateUniqueName } from './utils/test-helpers';

const projectName = generateUniqueName('project');
const fileName = generateUniqueName('file');
```

#### 2. Pool Users for Parallel Tests

Use different users for parallel tests:

```typescript
import { test } from '@playwright/test';
import { getWorkerUser } from './config/test-users';

test('parallel test', async ({ page, workerIndex }) => {
  const user = getWorkerUser(workerIndex);

  // Each worker uses a different user
  await loginPage.login(user.email, user.password);
});
```

#### 3. API Cleanup

Always cleanup test data:

```typescript
import { createProject, deleteProject } from './utils/api-helpers';

test.describe('With cleanup', () => {
  let projectId: string;

  test.beforeEach(async ({ request }) => {
    const project = await createProject(request, { title: 'Test' });
    projectId = project.id;
  });

  test.afterEach(async ({ request }) => {
    if (projectId) {
      await deleteProject(request, projectId);
    }
  });

  test('uses the project', async ({ page }) => {
    // Test implementation
  });
});
```

---

## Mock System Usage

The test suite uses MSW (Mock Service Worker) for API mocking.

### MSW Configuration

Mock handlers are in `mocks/handlers.ts`:

```typescript
import { http, HttpResponse } from 'msw';

// Mock AI chat endpoint
export const agentStreamHandler = http.post('/api/v1/agent/stream', () => {
  const stream = new ReadableStream({
    start(controller) {
      const encoder = new TextEncoder();

      // Send pre-recorded events
      chatDefaultResponse.forEach((event) => {
        const eventData = `data: ${JSON.stringify(event)}\n\n`;
        controller.enqueue(encoder.encode(eventData));
      });

      controller.close();
    },
  });

  return new HttpResponse(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
    },
  });
});
```

### Error Scenario Mocking

Mock error responses with `mocks/error-handlers.ts`:

```typescript
import { http, HttpResponse, delay } from 'msw';

// Network error
export const networkErrorHandler = http.get('/api/v1/projects', () => {
  return HttpResponse.error();
});

// Server error
export const serverErrorHandler = http.get('/api/v1/projects', () => {
  return new HttpResponse(null, { status: 500 });
});

// Timeout
export const timeoutHandler = http.get('/api/v1/projects', async () => {
  await delay('infinite');
});
```

### AI Response Mocking

Mock AI responses to avoid real API calls:

```typescript
// mocks/responses/chat-default.json
[
  { "type": "text", "content": "Hello" },
  { "type": "text", "content": ", " },
  { "type": "text", "content": "I'm here to help!" }
]
```

Use in tests:

```typescript
test('mocked AI chat', async ({ page }) => {
  // MSW automatically intercepts /api/v1/agent/stream
  await chatPanel.sendMessage('Hello');
  await expect(page.getByTestId('ai-message')).toContainText("I'm here to help!");
});
```

### Delay Simulation

Simulate realistic delays:

```typescript
import { http, HttpResponse, delay } from 'msw';
import { config } from './config/environments';

export const slowHandler = http.get('/api/v1/projects', async () => {
  // Use configured delay
  await delay(config.mockDelays.slow); // 2000ms

  return HttpResponse.json({ projects: [] });
});

// Delay options
await delay(100); // Fixed delay
await delay('infinite'); // Never respond
await delay(0); // Immediate (no delay)
```

---

## Debugging Failed Tests

### Playwright Inspector

The Playwright Inspector provides step-through debugging:

```bash
# Open inspector
pnpm exec playwright test --debug

# Debug specific test
pnpm exec playwright test auth.spec.ts --debug
```

Features:
- Step through test execution
- Inspect element selectors
- View page state at each step
- Time-travel debugging

### Trace Viewer

Traces are automatically captured on failed tests. View them:

```bash
# Open trace viewer
pnpm exec playwright show-trace trace.zip

# Or view HTML report
pnpm exec playwright show-report
```

Trace includes:
- Screenshots at each action
- DOM snapshots
- Network requests
- Console logs
- Source code location

### Screenshot Analysis

Failed tests automatically capture screenshots:

```
test-results/
  └── test-name/
      └── test-failed-1.png
```

Configure screenshot behavior in `playwright.config.ts`:

```typescript
export default defineConfig({
  use: {
    // Screenshot on failure (default)
    screenshot: 'only-on-failure',

    // Screenshot on every action
    screenshot: 'on',

    // Disable screenshots
    screenshot: 'off',

    // Full page screenshots
    screenshot: { mode: 'only-on-failure', fullPage: true },
  },
});
```

### Common Issues and Solutions

#### 1. Timeout Errors

```
Error: Timeout of 30000ms exceeded.
```

**Solutions:**
- Increase timeout: `await page.click('#button', { timeout: 60000 })`
- Wait for specific condition: `await page.waitForSelector('.loaded')`
- Check if element exists: `await expect(page.locator('#button')).toBeVisible()`

#### 2. Element Not Found

```
Error: locator.click: Element is not attached to the DOM
```

**Solutions:**
- Wait for element: `await page.waitForSelector('#button')`
- Use testid: `await page.getByTestId('button').click()`
- Check if visible: `await expect(page.locator('#button')).toBeVisible()`

#### 3. Flaky Tests

**Causes:**
- Race conditions
- Network delays
- Animation timing

**Solutions:**
- Use explicit waits: `await page.waitForLoadState('networkidle')`
- Avoid `waitForTimeout()`, use specific conditions instead
- Use `expect().toBeVisible()` instead of `isVisible()`

#### 4. Authentication Issues

```
Error: Authentication failed: 401 Unauthorized
```

**Solutions:**
- Verify test user exists: `python apps/server/scripts/seed_test_user.py`
- Check environment variables: `E2E_TEST_EMAIL`, `E2E_TEST_PASSWORD`
- Verify auth state file: `playwright/.auth/user.json`

#### 5. Network Errors

```
Error: net::ERR_CONNECTION_REFUSED
```

**Solutions:**
- Start backend server: `cd apps/server && python main.py`
- Start frontend: `cd apps/web && pnpm dev`
- Check port availability: 5173 (frontend), 8000 (backend)

### Debug Logging

Enable verbose logging:

```bash
# Enable Playwright debug
DEBUG=pw:* pnpm test:e2e

# Enable API debug
DEBUG=pw:api pnpm test:e2e

# Enable browser debug
DEBUG=pw:browser pnpm test:e2e
```

---

## Visual Regression Workflow

Visual regression tests ensure UI consistency across changes.

### Running Visual Tests

```bash
# Run visual regression tests
pnpm exec playwright test visual.spec.ts

# Run on specific browser
pnpm exec playwright test visual.spec.ts --project=chromium
```

### Updating Snapshots

When UI changes are intentional, update snapshots:

```bash
# Update all snapshots
pnpm exec playwright test visual.spec.ts --update-snapshots

# Update specific test
pnpm exec playwright test visual.spec.ts -g "dashboard" --update-snapshots
```

Snapshots are saved to:
```
e2e/
  └── visual.spec.ts-snapshots/
      ├── dashboard.png
      ├── project-page.png
      ├── chat-empty.png
      └── chat-with-messages.png
```

### Reviewing Diffs

When a visual test fails, Playwright generates a diff:

```bash
# View HTML report with diffs
pnpm exec playwright show-report
```

The report shows:
- Expected (baseline snapshot)
- Actual (current render)
- Diff (highlighted differences)

### Threshold Configuration

Configure comparison thresholds:

```typescript
test('dashboard matches snapshot', async ({ page }) => {
  await page.goto('/dashboard');
  await page.waitForLoadState('networkidle');

  await expect(page).toHaveScreenshot('dashboard.png', {
    // Allow up to 100 different pixels
    maxDiffPixels: 100,

    // Allow up to 0.01% difference
    maxDiffPixelRatio: 0.01,

    // Full page screenshot
    fullPage: true,

    // Mask dynamic content
    mask: [page.locator('.timestamp')],
  });
});
```

### Best Practices

#### 1. Use Stable Selectors

```typescript
// Bad - dynamic timestamps cause flaky snapshots
await expect(page.locator('.chat')).toHaveScreenshot('chat.png');

// Good - mask dynamic content
await expect(page.locator('.chat')).toHaveScreenshot('chat.png', {
  mask: [page.locator('.timestamp'), page.locator('.user-avatar')],
});
```

#### 2. Wait for Stability

```typescript
// Wait for animations to complete
await page.goto('/dashboard');
await page.waitForLoadState('networkidle');
await page.waitForTimeout(500); // Additional buffer

await expect(page).toHaveScreenshot('dashboard.png');
```

#### 3. Test Key States

```typescript
test('button states', async ({ page }) => {
  await page.goto('/form');

  const button = page.getByTestId('submit-button');

  // Default state
  await expect(button).toHaveScreenshot('button-default.png');

  // Hover state
  await button.hover();
  await expect(button).toHaveScreenshot('button-hover.png');

  // Disabled state
  await page.evaluate(() => {
    document.querySelector('[data-testid="submit-button"]').disabled = true;
  });
  await expect(button).toHaveScreenshot('button-disabled.png');
});
```

---

## CI/CD Integration

### GitHub Actions Workflow

E2E tests run in GitHub Actions (`.github/workflows/test.yml`).

#### On Pull Requests

Smoke tests run on all PRs:

```yaml
smoke-test:
  runs-on: ubuntu-latest
  if: github.event_name == 'pull_request'
  steps:
    - name: Run smoke tests
      run: cd apps/web && pnpm exec playwright test smoke.spec.ts
```

Smoke tests complete in ~2 minutes and cover critical paths.

#### On Main Branch Pushes

Full test suite runs on main/develop branches:

```yaml
e2e-test:
  strategy:
    matrix:
      browser: [chromium, firefox, webkit]
      shard: [1/4, 2/4, 3/4, 4/4]
```

All browsers, all tests, 4 shards per browser.

#### Nightly Runs

Full suite runs nightly at 2 AM UTC:

```yaml
on:
  schedule:
    - cron: '0 2 * * *'  # 2 AM UTC daily
```

### Sharding Strategy

Tests are sharded across 4 parallel runners per browser:

```yaml
matrix:
  shard: [1/4, 2/4, 3/4, 4/4]
```

Benefits:
- Faster test execution (4x speedup)
- Parallel resource utilization
- Isolated failure reporting

Each shard runs ~1/4 of tests, determined automatically by Playwright.

### Smoke Tests vs Full Suite

| Test Type | When | Duration | Coverage |
|-----------|------|----------|----------|
| **Smoke** | PRs | ~2 min | Critical paths (5 tests) |
| **Full** | Main/develop, nightly | ~15 min | All tests (40+ tests, 3 browsers) |

Smoke test coverage:
- User authentication
- Project creation
- File creation
- Chat messaging
- Project export

### Running CI Locally

Test CI workflow locally with `act`:

```bash
# Install act (GitHub Actions local runner)
brew install act

# Run smoke tests locally
pnpm test:ci-local

# Run all CI jobs
pnpm test:ci-local:all
```

### CI Environment Variables

CI tests use specific environment variables:

```yaml
env:
  CI: true
  E2E_TEST_EMAIL: e2e-test@zenstory.local
  E2E_TEST_PASSWORD: E2eTestPassword123!
  E2E_TEST_USERNAME: e2e_test_user
```

### Viewing CI Results

Failed tests upload artifacts:

```yaml
- name: Upload Playwright report
  uses: actions/upload-artifact@v4
  if: failure()
  with:
    name: playwright-report
    path: apps/web/playwright-report/
    retention-days: 7
```

Download and view:
1. Go to Actions tab in GitHub
2. Select failed workflow run
3. Download `playwright-report` artifact
4. Open `index.html` in browser

### Test Result Requirements

All tests must pass for CI to succeed:

```yaml
test-summary:
  needs: [backend-test, frontend-test, e2e-test]
  if: always()
  steps:
    - name: Check test results
      run: |
        if [[ "${{ needs.backend-test.result }}" != "success" ||
              "${{ needs.frontend-test.result }}" != "success" ||
              "${{ needs.e2e-test.result }}" != "success" ]]; then
          echo "::error::One or more test suites failed"
          exit 1
        fi
```

---

## Additional Resources

### Project Structure

```
apps/web/e2e/
├── config/                    # Test configuration
│   ├── test-users.ts         # Test user definitions
│   ├── environments.ts       # Environment config
│   └── index.ts              # Config exports
├── fixtures/                  # Test fixtures
│   ├── page-objects/         # Page Object Models
│   │   ├── BasePage.ts       # Base POM class
│   │   ├── LoginPage.ts      # Login page POM
│   │   ├── DashboardPage.ts  # Dashboard POM
│   │   ├── ProjectPage.ts    # Project page POM
│   │   ├── ChatPanel.ts      # Chat panel POM
│   │   └── index.ts          # POM exports
│   └── test-data.ts          # Test data fixtures
├── mocks/                     # MSW mock handlers
│   ├── handlers.ts           # Default handlers
│   ├── error-handlers.ts     # Error scenario mocks
│   ├── responses/            # Mock response data
│   └── index.ts              # Mock exports
├── utils/                     # Test utilities
│   ├── test-helpers.ts       # General helpers
│   ├── api-helpers.ts        # API operation helpers
│   ├── wait-helpers.ts       # Waiting utilities
│   └── assertion-helpers.ts  # Custom assertions
├── auth.setup.ts             # Authentication setup
├── smoke.spec.ts             # Smoke tests
├── visual.spec.ts            # Visual regression tests
├── auth.spec.ts              # Authentication tests
├── projects.spec.ts          # Project management tests
├── files.spec.ts             # File operations tests
├── chat.spec.ts              # Chat functionality tests
├── versions.spec.ts          # Version history tests
├── export.spec.ts            # Export functionality tests
├── voice.spec.ts             # Voice input tests
├── materials.spec.ts         # Material management tests
├── skills.spec.ts            # Skills system tests
├── public-skills.spec.ts     # Public skills tests
├── admin.spec.ts             # Admin panel tests
├── session.spec.ts           # Session management tests
├── performance.spec.ts       # Performance tests
├── error-recovery.spec.ts    # Error recovery tests
├── mobile.spec.ts            # Mobile responsive tests
└── accessibility.spec.ts     # Accessibility tests
```

### Configuration Files

- `playwright.config.ts` - Playwright configuration
- `config/test-users.ts` - Test user definitions
- `config/environments.ts` - Environment settings
- `.github/workflows/test.yml` - CI workflow

### Useful Commands Reference

```bash
# Run tests
pnpm test:e2e                    # All tests
pnpm test:e2e:ui                 # With UI
pnpm test:e2e:headed             # Headed mode
pnpm test:e2e:debug              # Debug mode
pnpm test:smoke                  # Smoke tests only
pnpm test:e2e:chromium           # Chromium only
pnpm test:e2e:all-browsers       # All browsers

# Debug and troubleshoot
pnpm exec playwright test --debug            # Inspector
pnpm exec playwright show-report             # HTML report
pnpm exec playwright show-trace trace.zip    # Trace viewer
DEBUG=pw:* pnpm test:e2e                     # Verbose logs

# Visual regression
pnpm exec playwright test visual.spec.ts                  # Run
pnpm exec playwright test visual.spec.ts --update-snapshots  # Update

# CI
pnpm test:ci-local               # Run smoke tests locally
pnpm test:ci-local:all           # Run all CI jobs locally
```

### Getting Help

- Playwright docs: https://playwright.dev
- Project issues: Check GitHub Issues
- Test failures: Check `playwright-report/` for detailed traces
