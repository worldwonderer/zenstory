import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useThinkingVisibility } from '../useThinkingVisibility'

const loggerError = vi.fn()

vi.mock('../../lib/logger', () => ({
  logger: {
    error: (...args: unknown[]) => loggerError(...args),
  },
}))

describe('useThinkingVisibility', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('defaults to true and persists toggles to localStorage', () => {
    const { result } = renderHook(() => useThinkingVisibility())

    expect(result.current.showThinking).toBe(true)

    act(() => {
      result.current.toggleThinking()
    })

    expect(result.current.showThinking).toBe(false)
    expect(localStorage.getItem('zenstory_show_thinking')).toBe('false')
  })

  it('restores the stored visibility preference', () => {
    localStorage.setItem('zenstory_show_thinking', 'false')

    const { result } = renderHook(() => useThinkingVisibility())
    expect(result.current.showThinking).toBe(false)
  })

  it('logs storage failures while preserving state updates', () => {
    const setItemSpy = vi.spyOn(localStorage, 'setItem').mockImplementation(() => {
      throw new Error('quota exceeded')
    })

    const { result } = renderHook(() => useThinkingVisibility())
    act(() => {
      result.current.setShowThinking(false)
    })

    expect(result.current.showThinking).toBe(false)
    expect(loggerError).toHaveBeenCalledWith('Failed to save thinking visibility state:', expect.any(Error))

    setItemSpy.mockRestore()
  })
})
