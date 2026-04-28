import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useDelayedLoading } from '../useDelayedLoading'

describe('useDelayedLoading', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-04-07T00:00:00Z'))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('does not show the loader when loading resolves before the delay', async () => {
    const { result, rerender } = renderHook(
      ({ isLoading }) => useDelayedLoading(isLoading, { delay: 200, minDuration: 400 }),
      { initialProps: { isLoading: true } },
    )

    await act(async () => {
      await vi.advanceTimersByTimeAsync(150)
    })
    rerender({ isLoading: false })

    expect(result.current).toBe(false)
  })

  it('shows the loader after the delay and keeps it visible for the minimum duration', async () => {
    const { result, rerender } = renderHook(
      ({ isLoading }) => useDelayedLoading(isLoading, { delay: 200, minDuration: 400 }),
      { initialProps: { isLoading: true } },
    )

    await act(async () => {
      await vi.advanceTimersByTimeAsync(200)
    })
    expect(result.current).toBe(true)

    rerender({ isLoading: false })
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100)
    })
    expect(result.current).toBe(true)

    await act(async () => {
      await vi.advanceTimersByTimeAsync(300)
    })
    expect(result.current).toBe(false)
  })

  it('supports custom delay and minimum duration values', async () => {
    const { result } = renderHook(() => useDelayedLoading(true, { delay: 50, minDuration: 100 }))

    await act(async () => {
      await vi.advanceTimersByTimeAsync(50)
    })

    expect(result.current).toBe(true)
  })
})
