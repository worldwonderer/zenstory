import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useMediaQuery, useIsMobile, useIsTablet, useIsDesktop } from '../useMediaQuery'

// Helper to create a mock MediaQueryList
function createMockMediaQueryList(matches: boolean) {
  const listeners = new Set<(e: MediaQueryListEvent) => void>()

  return {
    matches,
    media: '',
    onchange: null,
    addListener: vi.fn(), // deprecated
    removeListener: vi.fn(), // deprecated
    addEventListener: vi.fn((_type: string, listener: (e: MediaQueryListEvent) => void) => {
      listeners.add(listener)
    }),
    removeEventListener: vi.fn((_type: string, listener: (e: MediaQueryListEvent) => void) => {
      listeners.delete(listener)
    }),
    dispatchEvent: vi.fn((event: MediaQueryListEvent) => {
      listeners.forEach((listener) => listener(event))
      return true
    }),
    // Helper to simulate change events
    _simulateChange: (newMatches: boolean) => {
      const event = { matches: newMatches, media: '' } as MediaQueryListEvent
      listeners.forEach((listener) => listener(event))
    },
    _setMatches: (newMatches: boolean) => {
      Object.defineProperty(this, 'matches', { value: newMatches, writable: true })
    },
  } as MediaQueryList & { _simulateChange: (matches: boolean) => void }
}

describe('useMediaQuery', () => {
  let mockMatchMedia: ReturnType<typeof vi.spyOn>
  let mockMediaQueryList: ReturnType<typeof createMockMediaQueryList>

  beforeEach(() => {
    mockMediaQueryList = createMockMediaQueryList(false)
    mockMatchMedia = vi.spyOn(window, 'matchMedia').mockReturnValue(mockMediaQueryList)
  })

  afterEach(() => {
    mockMatchMedia.mockRestore()
  })

  describe('initial state', () => {
    it('returns false when media query does not match', () => {
      mockMediaQueryList = createMockMediaQueryList(false)
      mockMatchMedia.mockReturnValue(mockMediaQueryList)

      const { result } = renderHook(() => useMediaQuery('(min-width: 768px)'))

      expect(result.current).toBe(false)
      expect(mockMatchMedia).toHaveBeenCalledWith('(min-width: 768px)')
    })

    it('returns true when media query matches', () => {
      mockMediaQueryList = createMockMediaQueryList(true)
      mockMatchMedia.mockReturnValue(mockMediaQueryList)

      const { result } = renderHook(() => useMediaQuery('(min-width: 768px)'))

      expect(result.current).toBe(true)
    })

    it('handles different media query types', () => {
      mockMediaQueryList = createMockMediaQueryList(true)
      mockMatchMedia.mockReturnValue(mockMediaQueryList)

      const { result } = renderHook(() => useMediaQuery('(prefers-color-scheme: dark)'))

      expect(result.current).toBe(true)
      expect(mockMatchMedia).toHaveBeenCalledWith('(prefers-color-scheme: dark)')
    })
  })

  describe('media query changes', () => {
    it('updates when media query starts matching', () => {
      mockMediaQueryList = createMockMediaQueryList(false)
      mockMatchMedia.mockReturnValue(mockMediaQueryList)

      const { result } = renderHook(() => useMediaQuery('(min-width: 768px)'))

      expect(result.current).toBe(false)

      // Simulate media query change
      act(() => {
        mockMediaQueryList._simulateChange(true)
      })

      expect(result.current).toBe(true)
    })

    it('updates when media query stops matching', () => {
      mockMediaQueryList = createMockMediaQueryList(true)
      mockMatchMedia.mockReturnValue(mockMediaQueryList)

      const { result } = renderHook(() => useMediaQuery('(min-width: 768px)'))

      expect(result.current).toBe(true)

      // Simulate media query change
      act(() => {
        mockMediaQueryList._simulateChange(false)
      })

      expect(result.current).toBe(false)
    })

    it('handles multiple sequential changes', () => {
      mockMediaQueryList = createMockMediaQueryList(false)
      mockMatchMedia.mockReturnValue(mockMediaQueryList)

      const { result } = renderHook(() => useMediaQuery('(min-width: 768px)'))

      expect(result.current).toBe(false)

      act(() => {
        mockMediaQueryList._simulateChange(true)
      })
      expect(result.current).toBe(true)

      act(() => {
        mockMediaQueryList._simulateChange(false)
      })
      expect(result.current).toBe(false)

      act(() => {
        mockMediaQueryList._simulateChange(true)
      })
      expect(result.current).toBe(true)
    })
  })

  describe('cleanup', () => {
    it('removes event listener on unmount', () => {
      mockMediaQueryList = createMockMediaQueryList(false)
      mockMatchMedia.mockReturnValue(mockMediaQueryList)

      const { unmount } = renderHook(() => useMediaQuery('(min-width: 768px)'))

      expect(mockMediaQueryList.addEventListener).toHaveBeenCalledWith('change', expect.any(Function))

      unmount()

      expect(mockMediaQueryList.removeEventListener).toHaveBeenCalledWith('change', expect.any(Function))
    })

    it('adds new listener when query changes', () => {
      mockMediaQueryList = createMockMediaQueryList(false)
      mockMatchMedia.mockReturnValue(mockMediaQueryList)

      const { rerender } = renderHook(
        ({ query }) => useMediaQuery(query),
        { initialProps: { query: '(min-width: 768px)' } }
      )

      expect(mockMatchMedia).toHaveBeenCalledWith('(min-width: 768px)')

      // Rerender with new query
      rerender({ query: '(min-width: 1024px)' })

      // Should create new media query list for new query
      expect(mockMatchMedia).toHaveBeenCalledWith('(min-width: 1024px)')
    })
  })

  describe('query changes', () => {
    it('sets up new listener when query prop changes', () => {
      const firstMql = createMockMediaQueryList(false)
      const secondMql = createMockMediaQueryList(true)

      mockMatchMedia.mockImplementation((query: string) => {
        if (query === '(min-width: 768px)') return firstMql
        if (query === '(min-width: 1024px)') return secondMql
        return createMockMediaQueryList(false)
      })

      const { rerender } = renderHook(
        ({ query }) => useMediaQuery(query),
        { initialProps: { query: '(min-width: 768px)' } }
      )

      expect(mockMatchMedia).toHaveBeenCalledWith('(min-width: 768px)')
      expect(firstMql.addEventListener).toHaveBeenCalledWith('change', expect.any(Function))

      // Rerender with new query - should set up new listener
      rerender({ query: '(min-width: 1024px)' })

      // Verify new query was called and new listener was set up
      expect(mockMatchMedia).toHaveBeenCalledWith('(min-width: 1024px)')
      expect(secondMql.addEventListener).toHaveBeenCalledWith('change', expect.any(Function))

      // Verify old listener was cleaned up
      expect(firstMql.removeEventListener).toHaveBeenCalledWith('change', expect.any(Function))
    })
  })
})

describe('useIsMobile', () => {
  let mockMatchMedia: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    mockMatchMedia = vi.spyOn(window, 'matchMedia')
  })

  afterEach(() => {
    mockMatchMedia.mockRestore()
  })

  it('returns true when viewport is less than 768px', () => {
    // (min-width: 768px) does NOT match on mobile
    mockMatchMedia.mockReturnValue(createMockMediaQueryList(false))

    const { result } = renderHook(() => useIsMobile())

    expect(result.current).toBe(true)
  })

  it('returns false when viewport is 768px or greater', () => {
    // (min-width: 768px) matches on tablet/desktop
    mockMatchMedia.mockReturnValue(createMockMediaQueryList(true))

    const { result } = renderHook(() => useIsMobile())

    expect(result.current).toBe(false)
  })

  it('responds to viewport changes', () => {
    const mql = createMockMediaQueryList(false)
    mockMatchMedia.mockReturnValue(mql)

    const { result } = renderHook(() => useIsMobile())

    expect(result.current).toBe(true)

    act(() => {
      mql._simulateChange(true)
    })

    expect(result.current).toBe(false)
  })
})

describe('useIsTablet', () => {
  let mockMatchMedia: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    mockMatchMedia = vi.spyOn(window, 'matchMedia')
  })

  afterEach(() => {
    mockMatchMedia.mockRestore()
  })

  it('returns true when viewport is between 768px and 1024px', () => {
    mockMatchMedia.mockImplementation((_query: string) => {
      if (_query === '(min-width: 768px)') return createMockMediaQueryList(true)
      if (_query === '(min-width: 1024px)') return createMockMediaQueryList(false)
      return createMockMediaQueryList(false)
    })

    const { result } = renderHook(() => useIsTablet())

    expect(result.current).toBe(true)
  })

  it('returns false when viewport is less than 768px (mobile)', () => {
    mockMatchMedia.mockImplementation((_query: string) => {
      // Neither query matches on mobile
      return createMockMediaQueryList(false)
    })

    const { result } = renderHook(() => useIsTablet())

    expect(result.current).toBe(false)
  })

  it('returns false when viewport is 1024px or greater (desktop)', () => {
    mockMatchMedia.mockImplementation((_query: string) => {
      // Both queries match on desktop
      return createMockMediaQueryList(true)
    })

    const { result } = renderHook(() => useIsTablet())

    expect(result.current).toBe(false)
  })

  it('responds to viewport changes', () => {
    const min768Mql = createMockMediaQueryList(false)
    const min1024Mql = createMockMediaQueryList(false)

    mockMatchMedia.mockImplementation((query: string) => {
      if (query === '(min-width: 768px)') return min768Mql
      if (query === '(min-width: 1024px)') return min1024Mql
      return createMockMediaQueryList(false)
    })

    const { result } = renderHook(() => useIsTablet())

    // Initially mobile (not tablet)
    expect(result.current).toBe(false)

    // Resize to tablet
    act(() => {
      min768Mql._simulateChange(true)
    })

    expect(result.current).toBe(true)

    // Resize to desktop
    act(() => {
      min1024Mql._simulateChange(true)
    })

    expect(result.current).toBe(false)
  })
})

describe('useIsDesktop', () => {
  let mockMatchMedia: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    mockMatchMedia = vi.spyOn(window, 'matchMedia')
  })

  afterEach(() => {
    mockMatchMedia.mockRestore()
  })

  it('returns true when viewport is 1024px or greater', () => {
    mockMatchMedia.mockReturnValue(createMockMediaQueryList(true))

    const { result } = renderHook(() => useIsDesktop())

    expect(result.current).toBe(true)
  })

  it('returns false when viewport is less than 1024px', () => {
    mockMatchMedia.mockReturnValue(createMockMediaQueryList(false))

    const { result } = renderHook(() => useIsDesktop())

    expect(result.current).toBe(false)
  })

  it('responds to viewport changes', () => {
    const mql = createMockMediaQueryList(false)
    mockMatchMedia.mockReturnValue(mql)

    const { result } = renderHook(() => useIsDesktop())

    expect(result.current).toBe(false)

    act(() => {
      mql._simulateChange(true)
    })

    expect(result.current).toBe(true)
  })
})
