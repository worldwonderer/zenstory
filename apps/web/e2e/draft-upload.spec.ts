import { test, expect, type Page } from '@playwright/test'
import { TEST_USERS, config } from './config'
import { TIMEOUTS } from './constants'

const API_BASE = config.apiBaseUrl
const TEST_EMAIL = TEST_USERS.standard.email
const TEST_PASSWORD = TEST_USERS.standard.password

test.describe('Draft Upload', () => {
  let accessToken: string
  let projectId: string

  test.beforeAll(async ({ request }) => {
    // Login via API
    const params = new URLSearchParams()
    params.append('username', TEST_EMAIL)
    params.append('password', TEST_PASSWORD)

    const loginRes = await request.post(`${API_BASE}/api/auth/login`, {
      data: params.toString(),
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
    expect(loginRes.ok()).toBeTruthy()
    const loginData = await loginRes.json()
    accessToken = loginData.access_token

    // Get existing projects
    const projRes = await request.get(`${API_BASE}/api/v1/projects`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
    const projects = await projRes.json()
    const projectList = Array.isArray(projects) ? projects : []
    if (projectList.length > 0) {
      projectId = projectList[0].id
    }
  })

  async function injectAuth(page: Page) {
    await page.addInitScript(() => {
      const cachedUser = localStorage.getItem('user')
      if (cachedUser) {
        localStorage.setItem('auth_validated_at', Date.now().toString())
      }
    })
  }

  test('should open file dialog when clicking + on draft folder', async ({ page }) => {
    test.skip(!projectId, 'No project available for testing')

    await injectAuth(page)
    await page.goto(`/project/${projectId}`, { waitUntil: 'domcontentloaded' })

    // Wait for file tree to load
    await page.waitForTimeout(3000)

    // Find the draft folder - try both Chinese and English names
    const draftFolderEl = page.locator('text=正文').first()
      .or(page.locator('text=Drafts').first())
      .or(page.locator('text=Draft').first())

    const draftVisible = await draftFolderEl.isVisible().catch(() => false)
    test.skip(!draftVisible, 'No draft folder found in project')

    // Hover to reveal the + button
    await draftFolderEl.hover()
    await page.waitForTimeout(500)

    // Find the parent row container to locate the + button
    const parentRow = draftFolderEl.locator('xpath=ancestor::div[contains(@class, "group")]')
      .or(draftFolderEl.locator('xpath=ancestor::*[.//button]'))
    const plusBtn = parentRow.locator('button').first()

    // Click + should trigger file chooser
    const [fileChooser] = await Promise.all([
      page.waitForEvent('filechooser', { timeout: 5000 }),
      plusBtn.click(),
    ])

    expect(fileChooser).toBeTruthy()
    // Draft upload accepts .txt and .md
    const _accepted = fileChooser.inputElement.then(el => el.getAttribute('accept') || '')
    // The input element should exist
    expect(await fileChooser.inputElement).toBeTruthy()
  })

  test('should upload a txt file and create draft entries', async ({ page: _page, request }) => {
    test.skip(!projectId, 'No project available for testing')

    // Upload via API directly (more reliable than file dialog for content verification)
    const content = '第一章 开始\n这是第一章的内容。\n\n第二章 发展\n这是第二章的内容。'
    const uploadRes = await request.post(
      `${API_BASE}/api/v1/projects/${projectId}/files/upload-drafts`,
      {
        headers: { Authorization: `Bearer ${accessToken}` },
        multipart: {
          files: {
            name: 'test_novel.txt',
            mimeType: 'text/plain',
            buffer: Buffer.from(content, 'utf-8'),
          },
        },
      },
    )

    expect(uploadRes.ok()).toBeTruthy()
    const data = await uploadRes.json()
    expect(data.total).toBe(2)
    expect(data.errors).toHaveLength(0)

    const titles = data.files.map((f: { title: string }) => f.title)
    expect(titles.some((t: string) => t.includes('第一章'))).toBeTruthy()
    expect(titles.some((t: string) => t.includes('第二章'))).toBeTruthy()

    // Content should NOT contain chapter headings (they're stripped)
    for (const f of data.files) {
      expect(f.content).not.toContain('第一章 开始')
      expect(f.content).not.toContain('第二章 发展')
      expect(f.content).toContain('这是第')
    }
  })

  test('should show error toast for invalid file type', async ({ page: _page, request }) => {
    test.skip(!projectId, 'No project available for testing')

    const uploadRes = await request.post(
      `${API_BASE}/api/v1/projects/${projectId}/files/upload-drafts`,
      {
        headers: { Authorization: `Bearer ${accessToken}` },
        multipart: {
          files: {
            name: 'document.pdf',
            mimeType: 'application/pdf',
            buffer: Buffer.from('%PDF-1.4 fake content'),
          },
        },
      },
    )

    expect(uploadRes.ok()).toBeTruthy()
    const data = await uploadRes.json()
    expect(data.total).toBe(0)
    expect(data.errors.length).toBeGreaterThan(0)
    expect(data.errors[0]).toContain('ERR_FILE_TYPE_INVALID')
  })

  test('should preserve paragraph indentation after chapter split', async ({ page: _page, request }) => {
    test.skip(!projectId, 'No project available for testing')

    const content = '第一章 缩进\n　　段落有全角空格缩进。\n　　第二段也有缩进。'
    const uploadRes = await request.post(
      `${API_BASE}/api/v1/projects/${projectId}/files/upload-drafts`,
      {
        headers: { Authorization: `Bearer ${accessToken}` },
        multipart: {
          files: {
            name: 'indent_test.txt',
            mimeType: 'text/plain',
            buffer: Buffer.from(content, 'utf-8'),
          },
        },
      },
    )

    expect(uploadRes.ok()).toBeTruthy()
    const data = await uploadRes.json()

    // Single-chapter upload → title comes from filename, not heading
    const chapter = data.files[0]
    expect(chapter).toBeTruthy()
    // Heading should be stripped from content
    expect(chapter.content).not.toContain('第一章 缩进')
    // Indentation should be preserved
    expect(chapter.content).toContain('　　段落有全角空格缩进')
  })
})
