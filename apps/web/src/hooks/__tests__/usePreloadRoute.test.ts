import { renderHook } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { usePreloadRoute, preloadRoute } from '../usePreloadRoute'

// The preloadCache is internal to the module, so we need to test via the public API
// and mock the import functions

describe('usePreloadRoute', () => {
  let mockImportFn: () => Promise<unknown>

  beforeEach(() => {
    vi.clearAllMocks()
    // Create a fresh mock import function for each test
    mockImportFn = vi.fn().mockResolvedValue({ default: 'mockComponent' })
  })

  afterEach(() => {
    // Clear the preload cache between tests by forcing module re-import
    // Since we can't directly access the cache, we use unique keys
  })

  describe('returned function', () => {
    it('returns a function', () => {
      const { result } = renderHook(() =>
        usePreloadRoute(mockImportFn, '/test-route')
      )

      expect(typeof result.current).toBe('function')
    })

    it('calls preloadRoute when invoked', async () => {
      const { result } = renderHook(() =>
        usePreloadRoute(mockImportFn, '/test-route-1')
      )

      // Call the preload handler
      result.current()

      // The import function should be called
      expect(mockImportFn).toHaveBeenCalledTimes(1)
    })

    it('passes the correct import function and key to preloadRoute', async () => {
      const customImportFn = vi.fn().mockResolvedValue({ component: 'custom' })

      const { result } = renderHook(() =>
        usePreloadRoute(customImportFn, '/custom-route')
      )

      result.current()

      expect(customImportFn).toHaveBeenCalledTimes(1)
    })

    it('does not call import again when already cached', async () => {
      const importFn = vi.fn().mockResolvedValue({ default: 'component' })

      const { result } = renderHook(() =>
        usePreloadRoute(importFn, '/cached-route-test')
      )

      // First call should trigger import
      result.current()
      expect(importFn).toHaveBeenCalledTimes(1)

      // Second call should not trigger another import (cached)
      result.current()
      expect(importFn).toHaveBeenCalledTimes(1)
    })
  })

  describe('callback stability', () => {
    it('returns stable callback with same dependencies', () => {
      const importFn = vi.fn().mockResolvedValue({})
      const key = '/stable-route'

      const { result, rerender } = renderHook(
        ({ fn, routeKey }) => usePreloadRoute(fn, routeKey),
        { initialProps: { fn: importFn, routeKey: key } }
      )

      const firstCallback = result.current

      // Rerender with same dependencies
      rerender({ fn: importFn, routeKey: key })

      // Callback should be the same reference (memoized)
      expect(result.current).toBe(firstCallback)
    })

    it('returns new callback when importFn changes', () => {
      const importFn1 = vi.fn().mockResolvedValue({})
      const importFn2 = vi.fn().mockResolvedValue({})
      const key = '/same-route'

      const { result, rerender } = renderHook(
        ({ fn, routeKey }) => usePreloadRoute(fn, routeKey),
        { initialProps: { fn: importFn1, routeKey: key } }
      )

      const firstCallback = result.current

      // Rerender with different import function
      rerender({ fn: importFn2, routeKey: key })

      // Callback should be different (new function reference due to changed importFn)
      expect(result.current).not.toBe(firstCallback)
    })

    it('returns new callback when key changes', () => {
      const importFn = vi.fn().mockResolvedValue({})

      const { result, rerender } = renderHook(
        ({ fn, routeKey }) => usePreloadRoute(fn, routeKey),
        { initialProps: { fn: importFn, routeKey: '/route-1' } }
      )

      const firstCallback = result.current

      // Rerender with different key
      rerender({ fn: importFn, routeKey: '/route-2' })

      // Callback should be different (new function reference due to changed key)
      expect(result.current).not.toBe(firstCallback)
    })
  })

  describe('multiple hooks with different routes', () => {
    it('allows preloading different routes independently', async () => {
      const importFn1 = vi.fn().mockResolvedValue({ default: 'Component1' })
      const importFn2 = vi.fn().mockResolvedValue({ default: 'Component2' })

      const { result: result1 } = renderHook(() =>
        usePreloadRoute(importFn1, '/independent-route-1')
      )
      const { result: result2 } = renderHook(() =>
        usePreloadRoute(importFn2, '/independent-route-2')
      )

      result1.current()
      result2.current()

      expect(importFn1).toHaveBeenCalledTimes(1)
      expect(importFn2).toHaveBeenCalledTimes(1)
    })

    it('caches per route key across different hook instances', async () => {
      const importFn = vi.fn().mockResolvedValue({ default: 'Component' })
      const sharedKey = '/shared-cache-route'

      const { result: result1 } = renderHook(() =>
        usePreloadRoute(importFn, sharedKey)
      )

      // First instance triggers preload
      result1.current()
      expect(importFn).toHaveBeenCalledTimes(1)

      // Create second hook instance with same key
      const { result: result2 } = renderHook(() =>
        usePreloadRoute(importFn, sharedKey)
      )

      // Second instance should use cache, no new import call
      result2.current()
      expect(importFn).toHaveBeenCalledTimes(1) // Still 1, not 2
    })
  })

  describe('use with different key types', () => {
    it('works with path-style keys', () => {
      const importFn = vi.fn().mockResolvedValue({})

      const { result } = renderHook(() =>
        usePreloadRoute(importFn, '/dashboard/settings')
      )

      result.current()

      expect(importFn).toHaveBeenCalledTimes(1)
    })

    it('works with named keys', () => {
      const importFn = vi.fn().mockResolvedValue({})

      const { result } = renderHook(() =>
        usePreloadRoute(importFn, 'DashboardComponent')
      )

      result.current()

      expect(importFn).toHaveBeenCalledTimes(1)
    })

    it('works with empty string key', () => {
      const importFn = vi.fn().mockResolvedValue({})

      const { result } = renderHook(() =>
        usePreloadRoute(importFn, '')
      )

      result.current()

      expect(importFn).toHaveBeenCalledTimes(1)
    })
  })
})

describe('preloadRoute', () => {
  it('calls import function when route not cached', () => {
    const importFn = vi.fn().mockResolvedValue({ default: 'Component' })

    preloadRoute(importFn, 'unique-preload-test-1')

    expect(importFn).toHaveBeenCalledTimes(1)
  })

  it('does not call import function when route already cached', () => {
    const importFn = vi.fn().mockResolvedValue({ default: 'Component' })
    const key = 'unique-preload-test-2'

    // First call
    preloadRoute(importFn, key)
    expect(importFn).toHaveBeenCalledTimes(1)

    // Second call with same key should use cache
    preloadRoute(importFn, key)
    expect(importFn).toHaveBeenCalledTimes(1) // Still 1
  })

  it('stores the promise in cache for later access', async () => {
    const resolvedValue = { default: 'CachedComponent' }
    const importFn = vi.fn().mockResolvedValue(resolvedValue)
    const key = 'unique-preload-test-3'

    preloadRoute(importFn, key)

    // The import should have been called immediately
    expect(importFn).toHaveBeenCalled()

    // Call again - should not create new promise
    preloadRoute(importFn, key)
    expect(importFn).toHaveBeenCalledTimes(1)
  })
})
