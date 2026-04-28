import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useFileTreeDragDrop } from '../useFileTreeDrag'

describe('useFileTreeDragDrop', () => {
  const onMoveFile = vi.fn<(_: string, __: string) => Promise<boolean>>()
  const onReorderFiles = vi.fn<(_: string | null, __: string[]) => Promise<boolean>>()

  beforeEach(() => {
    onMoveFile.mockReset()
    onReorderFiles.mockReset()
  })

  it('tracks drag start, drop targets, errors, and drag end', () => {
    const { result } = renderHook(() => useFileTreeDragDrop(onMoveFile, onReorderFiles))

    act(() => {
      result.current.startDrag('file-1', 'draft', 'parent-1', 'Title')
    })
    expect(result.current.state).toMatchObject({
      draggingId: 'file-1',
      dropTarget: null,
      error: null,
    })

    act(() => {
      result.current.setDropTarget('folder-2', 'into')
    })
    expect(result.current.state.dropTarget).toEqual({ targetId: 'folder-2', position: 'into' })

    act(() => {
      result.current.setError('manual error')
    })
    expect(result.current.state.error).toBe('manual error')

    act(() => {
      result.current.endDrag()
    })
    expect(result.current.state).toEqual({ draggingId: null, dropTarget: null, error: null })
  })

  it('executes file moves and records failures from falsy responses', async () => {
    onMoveFile.mockResolvedValueOnce(true).mockResolvedValueOnce(false)

    const { result } = renderHook(() => useFileTreeDragDrop(onMoveFile, onReorderFiles))

    await expect(result.current.executeMove('file-1', 'folder-1')).resolves.toBe(true)
    expect(result.current.state.error).toBeNull()

    await expect(result.current.executeMove('file-2', 'folder-2')).resolves.toBe(false)
    await waitFor(() => {
      expect(result.current.state.error).toBe('Failed to move file')
    })
  })

  it('surfaces thrown move and reorder errors as state', async () => {
    onMoveFile.mockRejectedValueOnce(new Error('move exploded'))
    onReorderFiles.mockRejectedValueOnce(new Error('reorder exploded'))

    const { result } = renderHook(() => useFileTreeDragDrop(onMoveFile, onReorderFiles))

    await expect(result.current.executeMove('file-1', 'folder-1')).resolves.toBe(false)
    await waitFor(() => {
      expect(result.current.state.error).toBe('move exploded')
    })

    await expect(result.current.executeReorder('project-1', null, ['a', 'b'])).resolves.toBe(false)
    await waitFor(() => {
      expect(result.current.state.error).toBe('reorder exploded')
    })
  })

  it('executes reorders and flags unsuccessful responses', async () => {
    onReorderFiles.mockResolvedValueOnce(true).mockResolvedValueOnce(false)

    const { result } = renderHook(() => useFileTreeDragDrop(onMoveFile, onReorderFiles))

    await expect(result.current.executeReorder('project-1', 'parent-1', ['a', 'b'])).resolves.toBe(true)
    expect(onReorderFiles).toHaveBeenCalledWith('parent-1', ['a', 'b'])

    await expect(result.current.executeReorder('project-1', null, ['x'])).resolves.toBe(false)
    await waitFor(() => {
      expect(result.current.state.error).toBe('Failed to reorder files')
    })
  })
})
