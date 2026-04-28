import { afterEach, describe, expect, it } from 'vitest'

import { isAdmin } from '../authz'

describe('isAdmin', () => {
  afterEach(() => {
    localStorage.clear()
  })

  it('prefers the explicitly provided user', () => {
    expect(isAdmin({ is_superuser: true })).toBe(true)
    expect(isAdmin({ is_superuser: false })).toBe(false)
  })

  it('falls back to the cached localStorage user', () => {
    localStorage.setItem('user', JSON.stringify({ is_superuser: true }))
    expect(isAdmin()).toBe(true)

    localStorage.setItem('user', JSON.stringify({ is_superuser: false }))
    expect(isAdmin()).toBe(false)
  })

  it('returns false when cached data is missing or malformed', () => {
    expect(isAdmin()).toBe(false)

    localStorage.setItem('user', '{bad-json')
    expect(isAdmin()).toBe(false)
  })

  it('returns false when window is unavailable', () => {
    const originalWindow = window

    Object.defineProperty(globalThis, 'window', {
      configurable: true,
      value: undefined,
    })

    try {
      expect(isAdmin()).toBe(false)
    } finally {
      Object.defineProperty(globalThis, 'window', {
        configurable: true,
        value: originalWindow,
      })
    }
  })
})
