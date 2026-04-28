import { test as setup } from '@playwright/test'
import path from 'path'
import fs from 'fs'
import { config, TEST_USERS } from './config'

const authFile = process.env.PLAYWRIGHT_AUTH_FILE || 'playwright/.auth/user.json'

setup('authenticate', async ({ request, page }) => {
  // Ensure .auth directory exists
  const authDir = path.dirname(authFile)
  if (!fs.existsSync(authDir)) {
    fs.mkdirSync(authDir, { recursive: true })
  }

  // Perform API-based login using OAuth2 form-data
  const params = new URLSearchParams()
  params.append('username', TEST_USERS.standard.email)
  params.append('password', TEST_USERS.standard.password)

  const response = await request.post(`${config.apiBaseUrl}/api/auth/login`, {
    data: params.toString(),
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
  })

  if (!response.ok()) {
    throw new Error(`Authentication failed: ${response.status()} ${response.statusText()}`)
  }

  const tokens = await response.json()

  // Store tokens in localStorage by visiting the app and injecting them
  await page.goto('/')

  // Inject tokens into localStorage
  await page.evaluate((tokenData) => {
    localStorage.setItem('access_token', tokenData.access_token)
    localStorage.setItem('refresh_token', tokenData.refresh_token)
    localStorage.setItem('token_type', tokenData.token_type)
    localStorage.setItem('user', JSON.stringify(tokenData.user))
    localStorage.setItem('auth_validated_at', Date.now().toString())
  }, tokens)

  // Save authentication state (cookies and localStorage)
  await page.context().storageState({ path: authFile })
})
