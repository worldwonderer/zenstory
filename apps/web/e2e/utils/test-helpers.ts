/**
 * E2E Test Helper Utilities
 *
 * Utility functions for ensuring test isolation and parallel execution.
 * These helpers generate unique identifiers and provide async waiting utilities.
 */

/**
 * Generates a unique test name with timestamp and random suffix.
 *
 * Format: `${prefix}-${timestamp}-${randomString}`
 *
 * @param prefix - The prefix for the test name (e.g., 'test-project', 'test-file')
 * @returns A unique identifier string
 *
 * @example
 * const testName = generateUniqueName('test-project')
 * // => 'test-project-2026-02-14T12-34-56-abc123'
 */
export function generateUniqueName(prefix: string): string {
  return `${prefix}-${timestamp()}-${randomString(6)}`
}

/**
 * Returns the current timestamp in ISO-like format suitable for test names.
 *
 * Format: `YYYY-MM-DDTHH-MM-SS` (colons replaced with hyphens for filesystem compatibility)
 *
 * @returns The current timestamp string
 *
 * @example
 * const ts = timestamp()
 * // => '2026-02-14T12-34-56'
 */
export function timestamp(): string {
  const now = new Date()
  return now.toISOString().replace(/:/g, '-').slice(0, 19)
}

/**
 * Generates a random alphanumeric string of the specified length.
 *
 * Uses lowercase letters (a-z) and digits (0-9).
 *
 * @param length - The desired length of the random string (default: 6)
 * @returns A random string of the specified length
 *
 * @example
 * const id = randomString(8)
 * // => 'k9x2mp4q'
 *
 * const shortId = randomString()
 * // => 'abc123'
 */
export function randomString(length: number = 6): string {
  const chars = 'abcdefghijklmnopqrstuvwxyz0123456789'
  let result = ''
  for (let i = 0; i < length; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length))
  }
  return result
}

/**
 * Options for the waitFor helper function.
 */
interface WaitForOptions {
  /** Maximum time to wait in milliseconds (default: 5000) */
  timeout?: number
  /** Interval between condition checks in milliseconds (default: 100) */
  interval?: number
}

/**
 * Waits for an async condition to become true.
 *
 * Polls the condition function at the specified interval until it returns true
 * or the timeout is exceeded.
 *
 * @param condition - An async function that returns true when the condition is met
 * @param options - Configuration options for timeout and interval
 * @throws Error if the condition is not met within the timeout period
 *
 * @example
 * await waitFor(async () => {
 *   const element = await page.$('.loaded')
 *   return element !== null
 * })
 *
 * @example
 * // With custom options
 * await waitFor(
 *   async () => {
 *     const text = await page.textContent('.status')
 *     return text === 'Complete'
 *   },
 *   { timeout: 10000, interval: 200 }
 * )
 */
export async function waitFor(
  condition: () => Promise<boolean>,
  options?: WaitForOptions
): Promise<void> {
  const timeout = options?.timeout ?? 5000
  const interval = options?.interval ?? 100

  const startTime = Date.now()

  while (Date.now() - startTime < timeout) {
    if (await condition()) {
      return
    }
    await new Promise((resolve) => setTimeout(resolve, interval))
  }

  throw new Error(`Condition not met within ${timeout}ms timeout`)
}
