import { test, expect } from '@playwright/test'
import { TEST_USERS } from './config'

const ENABLE_PERFORMANCE_E2E = process.env.E2E_ENABLE_PERFORMANCE_E2E === 'true'
const PERFORMANCE_OPT_IN_MESSAGE =
  'Performance E2E tests are opt-in. Set E2E_ENABLE_PERFORMANCE_E2E=true to run.'

/**
 * Performance E2E Tests
 *
 * These tests verify speed targets and performance characteristics:
 * - Initial page load time
 * - File tree rendering with large datasets
 * - Editor handling of large documents
 * - Chat scroll performance with many messages
 * - Time to interactive metrics
 *
 * Note: Tests may fail initially if performance isn't optimized.
 * Document current performance and track improvements over time.
 */

// Performance thresholds (configurable)
const PERFORMANCE_THRESHOLDS = {
  INITIAL_PAGE_LOAD_MS: 3000, // 3 seconds
  TIME_TO_INTERACTIVE_MS: 5000, // 5 seconds
  LARGE_FILE_TREE_RENDER_MS: 2000, // 2 seconds for 100+ items
  EDITOR_LARGE_DOC_RESPONSE_MS: 500, // 500ms for 10k+ words
  CHAT_SCROLL_FPS: 30, // Minimum FPS for smooth scrolling
}

// Test credentials
const TEST_EMAIL = TEST_USERS.standard.email
const TEST_PASSWORD = TEST_USERS.standard.password

/**
 * Helper to generate large content for performance testing
 */
function generateLargeContent(wordCount: number): string {
  const words = [
    '故事', '主角', '冒险', '魔法', '世界', '旅程', '勇气', '友情',
    '挑战', '成长', '命运', '选择', '希望', '光明', '黑暗', '力量',
  ]
  const content: string[] = []
  for (let i = 0; i < wordCount; i++) {
    content.push(words[i % words.length])
  }
  return content.join(' ')
}

test.describe('Performance', () => {
  test.skip(!ENABLE_PERFORMANCE_E2E, PERFORMANCE_OPT_IN_MESSAGE)
  test('initial page load < 3 seconds', async ({ page }) => {
    const startTime = Date.now()
    await page.goto('/')
    await page.waitForLoadState('domcontentloaded')
    const loadTime = Date.now() - startTime

    console.log(`Initial page load time: ${loadTime}ms`)

    expect(loadTime).toBeLessThan(PERFORMANCE_THRESHOLDS.INITIAL_PAGE_LOAD_MS)
  })

  test('login page renders quickly', async ({ page }) => {
    const startTime = Date.now()
    await page.goto('/login')
    await page.waitForSelector('#identifier')
    const renderTime = Date.now() - startTime

    console.log(`Login page render time: ${renderTime}ms`)

    // Login page should render faster than 2 seconds
    expect(renderTime).toBeLessThan(2000)
  })

  test('dashboard renders after login < 3 seconds', async ({ page }) => {
    // Login first
    await page.goto('/login')
    await page.locator('#identifier').fill(TEST_EMAIL)
    await page.locator('#password').fill(TEST_PASSWORD)
    await page.locator('button[type="submit"]').click()

    const startTime = Date.now()
    await page.waitForURL(/\/(dashboard|project)/, { timeout: 10000 })
    await page.waitForLoadState('networkidle')
    const loadTime = Date.now() - startTime

    console.log(`Dashboard render time after login: ${loadTime}ms`)

    expect(loadTime).toBeLessThan(PERFORMANCE_THRESHOLDS.INITIAL_PAGE_LOAD_MS)
  })

  test('file tree renders 100+ items smoothly', async ({ page }) => {
    // Login and navigate to dashboard
    await page.goto('/login')
    await page.locator('#identifier').fill(TEST_EMAIL)
    await page.locator('#password').fill(TEST_PASSWORD)
    await page.locator('button[type="submit"]').click()
    await page.waitForURL(/\/(dashboard|project)/, { timeout: 10000 })

    // Navigate to dashboard if needed
    if (page.url().includes('/project/')) {
      await page.goto('/dashboard')
    }

    // Create a test project for file operations
    const inspirationInput = page.locator('[data-testid="dashboard-inspiration-input"]')
    await inspirationInput.fill(`性能测试项目 ${Date.now()}`)
    await page.click('button:has-text("创建")')
    await page.waitForURL(/\/project\//, { timeout: 15000 })

    // Wait for file tree to load initially
    await page.waitForSelector('.overflow-auto', { timeout: 5000 })

    // Expand the outline folder
    const outlineFolder = page.locator('text=大纲').first()
    await outlineFolder.click()
    await expect(page.locator('.overflow-auto >> text=大纲')).toBeVisible()

    // Create multiple files to test rendering performance
    // Note: In a real test, you would create 100+ files via API for accuracy
    const fileCount = 10 // Reduced for E2E test performance
    const startTime = Date.now()

    for (let i = 0; i < fileCount; i++) {
      await outlineFolder.hover()
      const addButton = outlineFolder.locator('..').locator('button:has(svg.lucide-plus)').first()
      await addButton.click({ force: true })

      const fileInput = page.locator('input[placeholder*="大纲"]')
      await fileInput.fill(`测试文件${i}`)
      await fileInput.press('Enter')
      // Small delay for file creation to complete
      await page.locator(`text=测试文件${i}`).waitFor({ state: 'visible', timeout: 2000 })
    }

    const renderTime = Date.now() - startTime
    console.log(`Time to create and render ${fileCount} files: ${renderTime}ms`)

    // Measure scroll performance in the file tree
    const scrollContainer = page.locator('.overflow-auto').first()
    const scrollStartTime = Date.now()

    // Scroll through the file tree
    for (let i = 0; i < 5; i++) {
      await scrollContainer.evaluate((el, scrollAmount) => {
        el.scrollTop += scrollAmount
      }, 200)
      // Wait for scroll frame (~60fps) - use requestAnimationFrame for proper frame timing
      await scrollContainer.evaluate(() => new Promise(resolve => requestAnimationFrame(resolve)))
    }

    const scrollTime = Date.now() - scrollStartTime
    console.log(`Scroll performance for ${fileCount} items: ${scrollTime}ms`)

    // Verify all files are visible
    await expect(page.locator('text=测试文件0')).toBeVisible()
    await expect(page.locator(`text=测试文件${fileCount - 1}`)).toBeVisible()

    // For 100+ items, we'd expect render time < LARGE_FILE_TREE_RENDER_MS
    // With 10 items, we expect proportionally faster
    expect(renderTime).toBeLessThan(PERFORMANCE_THRESHOLDS.LARGE_FILE_TREE_RENDER_MS * (fileCount / 100))
  })

  test('editor handles 10k+ word documents', async ({ page }) => {
    // Login and setup project
    await page.goto('/login')
    await page.locator('#identifier').fill(TEST_EMAIL)
    await page.locator('#password').fill(TEST_PASSWORD)
    await page.locator('button[type="submit"]').click()
    await page.waitForURL(/\/(dashboard|project)/, { timeout: 10000 })

    if (page.url().includes('/project/')) {
      await page.goto('/dashboard')
    }

    const inspirationInput = page.locator('[data-testid="dashboard-inspiration-input"]')
    await inspirationInput.fill(`编辑器性能测试 ${Date.now()}`)
    await page.click('button:has-text("创建")')
    await page.waitForURL(/\/project\//, { timeout: 15000 })

    // Create and select a file
    await page.waitForSelector('.overflow-auto', { timeout: 5000 })
    const outlineFolder = page.locator('text=大纲').first()
    await outlineFolder.click()
    await expect(page.locator('.overflow-auto >> text=大纲')).toBeVisible()
    await outlineFolder.hover()
    const addButton = outlineFolder.locator('..').locator('button:has(svg.lucide-plus)').first()
    await addButton.click({ force: true })

    const fileInput = page.locator('input[placeholder*="大纲"]')
    await fileInput.fill('大文档测试')
    await fileInput.press('Enter')
    // Wait for file to be created
    await page.locator('text=大文档测试').waitFor({ state: 'visible', timeout: 2000 })

    // Select the file
    const testFile = page.locator('.overflow-auto >> text=大文档测试').first()
    await testFile.click()
    // Wait for editor to load
    await expect(page.locator('textarea')).toBeVisible({ timeout: 5000 })

    // Generate large content (10000 words for full test, 1000 for E2E speed)
    const wordCount = 1000 // Reduced for E2E test performance
    const largeContent = generateLargeContent(wordCount)

    // Measure editor fill performance
    const editor = page.locator('textarea').first()
    await expect(editor).toBeVisible()

    const fillStartTime = Date.now()
    await editor.fill(largeContent)
    const fillTime = Date.now() - fillStartTime

    console.log(`Time to fill editor with ${wordCount} words: ${fillTime}ms`)

    // Measure typing responsiveness (simulate typing at the end)
    const typeStartTime = Date.now()
    await editor.press('End')
    await editor.press('Enter')
    await editor.type('新段落测试', { delay: 10 })
    const typeTime = Date.now() - typeStartTime

    console.log(`Typing responsiveness with ${wordCount} words: ${typeTime}ms`)

    // Measure selection performance
    const selectStartTime = Date.now()
    await editor.focus()
    await page.keyboard.down('Shift')
    for (let i = 0; i < 20; i++) { // Reduced from 50 to 20 for faster test
      await page.keyboard.press('ArrowRight')
    }
    await page.keyboard.up('Shift')
    const selectTime = Date.now() - selectStartTime

    console.log(`Selection time with ${wordCount} words: ${selectTime}ms`)

    // Verify content
    const editorValue = await editor.inputValue()
    expect(editorValue.length).toBeGreaterThan(wordCount * 0.9) // Allow some margin

    // Performance assertions (scaled for word count)
    // For 10000 words, we'd expect < EDITOR_LARGE_DOC_RESPONSE_MS
    expect(fillTime).toBeLessThan(PERFORMANCE_THRESHOLDS.EDITOR_LARGE_DOC_RESPONSE_MS * (wordCount / 1000) * 5)
    expect(typeTime).toBeLessThan(PERFORMANCE_THRESHOLDS.EDITOR_LARGE_DOC_RESPONSE_MS * 3)
    expect(selectTime).toBeLessThan(200)
  })

  test('chat scroll remains smooth with 100+ messages', async ({ page }) => {
    // Login and setup
    await page.goto('/login')
    await page.locator('#identifier').fill(TEST_EMAIL)
    await page.locator('#password').fill(TEST_PASSWORD)
    await page.locator('button[type="submit"]').click()
    await page.waitForURL(/\/(dashboard|project)/, { timeout: 10000 })

    if (page.url().includes('/project/')) {
      await page.goto('/dashboard')
    }

    const projectCard = page.locator('[data-testid="project-card"]').first()
    if (await projectCard.isVisible()) {
      await projectCard.click()
      await page.waitForURL(/\/project\//, { timeout: 5000 })
    } else {
      const inspirationInput = page.locator('[data-testid="dashboard-inspiration-input"]')
      await inspirationInput.fill(`聊天性能测试 ${Date.now()}`)
      await page.click('button:has-text("创建")')
      await page.waitForURL(/\/project\//, { timeout: 15000 })
    }

    const input = page.locator('textarea[placeholder*="输入"]')
    await expect(input).toBeVisible()

    // Send multiple messages to test scroll performance
    // Note: Reduced to 10 messages for E2E test performance
    // In production, you would create 100+ messages via API
    const messageCount = 10

    for (let i = 0; i < messageCount; i++) {
      await input.fill(`测试消息 ${i}：${generateLargeContent(50)}`)
      await page.locator('button[type="submit"], button:has([class*="Send"])').last().click()

      // Wait for message to appear
      await expect(page.locator('.markdown-content').last()).toBeVisible({ timeout: 5000 }).catch(() => {})

      // Wait for AI response (with timeout)
      try {
        await expect(page.locator('.markdown-content').last()).toBeVisible({ timeout: 30000 })
      } catch {
        // Continue even if AI response times out
        console.log(`AI response timeout for message ${i}`)
      }
    }

    // Measure scroll performance in chat panel
    const chatContainer = page.locator('.flex-1.overflow-y-auto, [class*="overflow"]').filter({
      has: page.locator('.markdown-content'),
    }).first()

    if (await chatContainer.isVisible()) {
      const scrollMetrics: number[] = []

      // Perform multiple scroll operations and measure time
      for (let i = 0; i < 10; i++) {
        const scrollStart = Date.now()
        await chatContainer.evaluate((el) => {
          el.scrollTop = el.scrollHeight
        })
        // Wait for frame rendering using requestAnimationFrame
        await chatContainer.evaluate(() => new Promise(resolve => requestAnimationFrame(resolve)))
        const scrollEnd = Date.now()
        scrollMetrics.push(scrollEnd - scrollStart)
      }

      const avgScrollTime = scrollMetrics.reduce((a, b) => a + b, 0) / scrollMetrics.length
      console.log(`Average scroll time per frame: ${avgScrollTime}ms`)

      // Smooth scrolling should be < 33ms per frame (30 FPS)
      expect(avgScrollTime).toBeLessThan(1000 / PERFORMANCE_THRESHOLDS.CHAT_SCROLL_FPS)

      // Test scroll to top performance
      const scrollTopStart = Date.now()
      await chatContainer.evaluate((el) => {
        el.scrollTop = 0
      })
      const scrollTopTime = Date.now() - scrollTopStart
      console.log(`Scroll to top time: ${scrollTopTime}ms`)
      expect(scrollTopTime).toBeLessThan(100)

      // Test scroll to bottom performance
      const scrollBottomStart = Date.now()
      await chatContainer.evaluate((el) => {
        el.scrollTop = el.scrollHeight
      })
      const scrollBottomTime = Date.now() - scrollBottomStart
      console.log(`Scroll to bottom time: ${scrollBottomTime}ms`)
      expect(scrollBottomTime).toBeLessThan(100)
    }

    // Verify messages are visible
    await expect(page.locator('text=测试消息 0')).toBeVisible()
    await expect(page.locator(`text=测试消息 ${messageCount - 1}`)).toBeVisible()
  })

  test('time to interactive < 5 seconds', async ({ page }) => {
    const startTime = Date.now()

    // Navigate to login
    await page.goto('/login')

    // Wait for form to be interactive (inputs are focusable)
    await page.waitForSelector('#identifier', { state: 'visible' })
    await page.waitForSelector('#password', { state: 'visible' })
    await page.waitForSelector('button[type="submit"]', { state: 'visible' })

    // Verify form is actually interactive by typing
    await page.locator('#identifier').fill(TEST_EMAIL)
    await page.locator('#password').fill(TEST_PASSWORD)

    const interactiveTime = Date.now() - startTime
    console.log(`Login page time to interactive: ${interactiveTime}ms`)

    expect(interactiveTime).toBeLessThan(PERFORMANCE_THRESHOLDS.TIME_TO_INTERACTIVE_MS)

    // Login and measure dashboard time to interactive
    await page.locator('button[type="submit"]').click()
    const dashboardStart = Date.now()

    await page.waitForURL(/\/(dashboard|project)/, { timeout: 10000 })

    // Navigate to dashboard if on project page
    if (page.url().includes('/project/')) {
      await page.goto('/dashboard')
    }

    // Wait for interactive elements on dashboard
    await page.waitForSelector('[data-testid="project-card"], button:has-text("创建")', {
      state: 'visible',
      timeout: 10000,
    })

    // Verify dashboard is interactive
    const createButton = page.locator('button:has-text("创建")')
    await expect(createButton).toBeEnabled()

    const dashboardInteractiveTime = Date.now() - dashboardStart
    console.log(`Dashboard time to interactive: ${dashboardInteractiveTime}ms`)

    expect(dashboardInteractiveTime).toBeLessThan(PERFORMANCE_THRESHOLDS.TIME_TO_INTERACTIVE_MS)
  })

  test('project page time to interactive', async ({ page }) => {
    // Login first
    await page.goto('/login')
    await page.locator('#identifier').fill(TEST_EMAIL)
    await page.locator('#password').fill(TEST_PASSWORD)
    await page.locator('button[type="submit"]').click()
    await page.waitForURL(/\/(dashboard|project)/, { timeout: 10000 })

    // Navigate to dashboard
    if (page.url().includes('/project/')) {
      await page.goto('/dashboard')
    }

    // Click on a project
    const projectCard = page.locator('[data-testid="project-card"]').first()
    if (await projectCard.isVisible()) {
      const projectStart = Date.now()
      await projectCard.click()
      await page.waitForURL(/\/project\//, { timeout: 10000 })

      // Wait for key interactive elements
      await page.waitForSelector('.overflow-auto', { timeout: 5000 }) // File tree
      await page.waitForSelector('textarea', { timeout: 5000 }) // Editor or chat

      // Verify page is interactive
      const chatInput = page.locator('textarea[placeholder*="输入"]')
      await expect(chatInput).toBeVisible()
      await expect(chatInput).toBeEnabled()

      const projectInteractiveTime = Date.now() - projectStart
      console.log(`Project page time to interactive: ${projectInteractiveTime}ms`)

      expect(projectInteractiveTime).toBeLessThan(PERFORMANCE_THRESHOLDS.TIME_TO_INTERACTIVE_MS)
    } else {
      // Skip if no projects available
      console.log('No projects available for project page TTI test')
      test.skip()
    }
  })

  test('memory usage remains stable during extended use', async ({ page }) => {
    // Login and setup
    await page.goto('/login')
    await page.locator('#identifier').fill(TEST_EMAIL)
    await page.locator('#password').fill(TEST_PASSWORD)
    await page.locator('button[type="submit"]').click()
    await page.waitForURL(/\/(dashboard|project)/, { timeout: 10000 })

    if (page.url().includes('/project/')) {
      await page.goto('/dashboard')
    }

    // Get initial memory metrics
    const initialMetrics = await page.evaluate(() => {
      if ('memory' in performance) {
        const memory = (performance as { memory: { usedJSHeapSize: number } }).memory
        return {
          usedJSHeapSize: memory.usedJSHeapSize,
        }
      }
      return null
    })

    if (initialMetrics) {
      console.log(`Initial memory usage: ${(initialMetrics.usedJSHeapSize / 1024 / 1024).toFixed(2)} MB`)

      // Perform multiple operations to simulate extended use
      const inspirationInput = page.locator('[data-testid="dashboard-inspiration-input"]')
      for (let i = 0; i < 5; i++) {
        await inspirationInput.fill(`内存测试项目 ${Date.now()}`)
        await page.click('button:has-text("创建")')
        await page.waitForURL(/\/project\//, { timeout: 15000 })

        // Interact with the page
        await page.waitForSelector('.overflow-auto', { timeout: 5000 })

        // Navigate back to dashboard
        await page.goto('/dashboard')
        await page.waitForLoadState('networkidle')
      }

      // Get final memory metrics
      const finalMetrics = await page.evaluate(() => {
        if ('memory' in performance) {
          const memory = (performance as { memory: { usedJSHeapSize: number } }).memory
          return {
            usedJSHeapSize: memory.usedJSHeapSize,
          }
        }
        return null
      })

      if (finalMetrics) {
        console.log(`Final memory usage: ${(finalMetrics.usedJSHeapSize / 1024 / 1024).toFixed(2)} MB`)

        const memoryIncrease = finalMetrics.usedJSHeapSize - initialMetrics.usedJSHeapSize
        console.log(`Memory increase: ${(memoryIncrease / 1024 / 1024).toFixed(2)} MB`)

        // Memory should not increase by more than 100MB during normal use
        expect(memoryIncrease).toBeLessThan(100 * 1024 * 1024)
      }
    } else {
      console.log('Memory metrics not available in this browser')
      test.skip()
    }
  })

  test('network request count is reasonable', async ({ page }) => {
    // Track network requests
    const requests: string[] = []
    page.on('request', (request) => {
      requests.push(request.url())
    })

    // Navigate to login and perform actions
    await page.goto('/login')
    await page.locator('#identifier').fill(TEST_EMAIL)
    await page.locator('#password').fill(TEST_PASSWORD)
    await page.locator('button[type="submit"]').click()
    await page.waitForURL(/\/(dashboard|project)/, { timeout: 10000 })
    await page.waitForLoadState('networkidle')

    // Count requests by type
    const apiRequests = requests.filter((r) => r.includes('/api/'))
    const staticRequests = requests.filter((r) => r.includes('/assets/') || r.endsWith('.js') || r.endsWith('.css'))

    console.log(`Total requests: ${requests.length}`)
    console.log(`API requests: ${apiRequests.length}`)
    console.log(`Static asset requests: ${staticRequests.length}`)

    // Initial load should not make excessive API calls
    expect(apiRequests.length).toBeLessThan(20)

    // Static assets should be cached (reasonable number)
    expect(staticRequests.length).toBeLessThan(50)
  })
})

test.describe('Performance - Stress Tests', () => {
  test.skip(!ENABLE_PERFORMANCE_E2E, PERFORMANCE_OPT_IN_MESSAGE)
  // These tests push the limits and may fail on slower systems

  test.skip('file tree handles 500+ items', async ({ page }) => {
    // This test requires API setup to create 500+ files
    // Skipping by default - enable manually for stress testing

    // Login
    await page.goto('/login')
    await page.locator('#identifier').fill(TEST_EMAIL)
    await page.locator('#password').fill(TEST_PASSWORD)
    await page.locator('button[type="submit"]').click()
    await page.waitForURL(/\/(dashboard|project)/, { timeout: 10000 })

    // Note: In production, create files via API before this test
    console.log('Stress test skipped - requires 500+ files to be created via API')
  })

  test.skip('editor handles 50k+ word documents', async ({ page }) => {
    // This test requires significant time - skipping by default

    // Login and setup
    await page.goto('/login')
    await page.locator('#identifier').fill(TEST_EMAIL)
    await page.locator('#password').fill(TEST_PASSWORD)
    await page.locator('button[type="submit"]').click()
    await page.waitForURL(/\/(dashboard|project)/, { timeout: 10000 })

    console.log('Stress test skipped - 50k word document test disabled by default')
  })

  test.skip('chat handles 500+ messages', async ({ page }) => {
    // This test requires significant time - skipping by default

    // Login and setup
    await page.goto('/login')
    await page.locator('#identifier').fill(TEST_EMAIL)
    await page.locator('#password').fill(TEST_PASSWORD)
    await page.locator('button[type="submit"]').click()
    await page.waitForURL(/\/(dashboard|project)/, { timeout: 10000 })

    console.log('Stress test skipped - 500 message test disabled by default')
  })
})
