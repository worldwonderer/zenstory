import { beforeEach, describe, expect, it, vi } from 'vitest'

const warnMock = vi.fn()

vi.mock('../logger', () => ({
  logger: {
    warn: warnMock,
  },
}))

describe('dashboardPlaceholderSource', () => {
  beforeEach(() => {
    warnMock.mockReset()
    vi.resetModules()
    vi.unstubAllGlobals()
  })

  it('normalizes locales and caches successful placeholder bundles', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        version: 1,
        locale: 'en',
        generated_at: '2026-04-07T00:00:00Z',
        placeholders: {
          novel: ['Novel idea'],
          short: ['Short idea'],
          screenplay: ['Scene idea'],
        },
      }),
    })
    vi.stubGlobal('fetch', fetchMock)

    const mod = await import('../dashboardPlaceholderSource')

    expect(mod.normalizeDashboardPlaceholderLocale('en-GB')).toBe('en')
    expect(mod.normalizeDashboardPlaceholderLocale('zh-CN')).toBe('zh')

    const first = await mod.loadDashboardPlaceholderBundle('en')
    const second = await mod.loadDashboardPlaceholderBundle('en')

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(first).toEqual(second)
    expect(first).toMatchObject({
      locale: 'en',
      placeholders: {
        novel: ['Novel idea'],
      },
    })
  })

  it('warns and returns null when the file is unavailable', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
      }),
    )

    const mod = await import('../dashboardPlaceholderSource')
    const bundle = await mod.loadDashboardPlaceholderBundle('zh')

    expect(bundle).toBeNull()
    expect(warnMock).toHaveBeenCalledWith(
      'Dashboard placeholder file unavailable',
      expect.objectContaining({ locale: 'zh', status: 404 }),
    )
  })

  it('warns and returns null when payload validation fails or locale mismatches', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn()
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          json: async () => ({
            version: 1,
            locale: 'en',
            generated_at: '2026-04-07T00:00:00Z',
            placeholders: {
              novel: [],
              short: ['Short idea'],
              screenplay: ['Scene idea'],
            },
          }),
        })
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          json: async () => ({
            version: 1,
            locale: 'en',
            generated_at: '2026-04-07T00:00:00Z',
            placeholders: {
              novel: ['Novel idea'],
              short: ['Short idea'],
              screenplay: ['Scene idea'],
            },
          }),
        }),
    )

    const mod = await import('../dashboardPlaceholderSource')

    await expect(mod.loadDashboardPlaceholderBundle('zh')).resolves.toBeNull()
    expect(warnMock).toHaveBeenCalledWith(
      'Dashboard placeholder file validation failed',
      expect.objectContaining({ locale: 'zh' }),
    )

    vi.resetModules()
    warnMock.mockReset()
    const fetchLocaleMismatch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        version: 1,
        locale: 'en',
        generated_at: '2026-04-07T00:00:00Z',
        placeholders: {
          novel: ['Novel idea'],
          short: ['Short idea'],
          screenplay: ['Scene idea'],
        },
      }),
    })
    vi.stubGlobal('fetch', fetchLocaleMismatch)

    const localeMismatchMod = await import('../dashboardPlaceholderSource')
    await expect(localeMismatchMod.loadDashboardPlaceholderBundle('zh')).resolves.toBeNull()
    expect(warnMock).toHaveBeenCalledWith(
      'Dashboard placeholder locale mismatch',
      expect.objectContaining({ requestedLocale: 'zh', payloadLocale: 'en' }),
    )
  })

  it('warns and returns null when fetch throws', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network down')))

    const mod = await import('../dashboardPlaceholderSource')
    await expect(mod.loadDashboardPlaceholderBundle('zh')).resolves.toBeNull()

    expect(warnMock).toHaveBeenCalledWith(
      'Dashboard placeholder file load failed',
      expect.objectContaining({ locale: 'zh' }),
    )
  })
})
