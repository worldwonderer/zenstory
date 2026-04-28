import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { warnMock } = vi.hoisted(() => ({
  warnMock: vi.fn(),
}))

vi.mock('../../lib/logger', () => ({
  logger: {
    warn: warnMock,
  },
}))

import { useDraftPersistence } from '../useDraftPersistence'

const STORAGE_KEY = 'zenstory_chat_drafts'

describe('useDraftPersistence', () => {
  beforeEach(() => {
    localStorage.clear()
    warnMock.mockReset()
  })

  it('loads the default draft for the active project', () => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        projectA: {
          default: 'Saved draft',
          session2: 'Other draft',
        },
      }),
    )

    const { result } = renderHook(() => useDraftPersistence('projectA'))

    expect(result.current.draft).toBe('Saved draft')
  })

  it('falls back to the first stored session when no default draft exists', () => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        projectA: {
          session2: 'Recovered draft',
        },
      }),
    )

    const { result } = renderHook(() => useDraftPersistence('projectA'))

    expect(result.current.draft).toBe('Recovered draft')
  })

  it('saves and clears drafts in localStorage', () => {
    const { result } = renderHook(() => useDraftPersistence('projectA'))

    act(() => {
      result.current.saveDraft('Fresh draft')
    })

    expect(result.current.draft).toBe('Fresh draft')
    expect(JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '{}')).toMatchObject({
      projectA: { default: 'Fresh draft' },
    })

    act(() => {
      result.current.clearDraft()
    })

    expect(result.current.draft).toBe('')
    expect(JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '{}')).toEqual({ projectA: {} })
  })

  it('syncs draft state when the active project changes', () => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        projectA: { default: 'Draft A' },
        projectB: { default: 'Draft B' },
      }),
    )

    const { result, rerender } = renderHook(({ projectId }) => useDraftPersistence(projectId), {
      initialProps: { projectId: 'projectA' as string | null },
    })

    expect(result.current.draft).toBe('Draft A')

    rerender({ projectId: 'projectB' })
    expect(result.current.draft).toBe('Draft B')
  })

  it('fails safely and logs warnings when storage is corrupted', () => {
    localStorage.setItem(STORAGE_KEY, '{not-valid-json')

    const { result } = renderHook(() => useDraftPersistence('projectA'))

    expect(result.current.draft).toBe('')
    expect(warnMock).toHaveBeenCalled()
  })
})
