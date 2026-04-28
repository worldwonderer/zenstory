import { renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

let lastVirtualizerOptions: {
  count: number
  overscan: number
  estimateSize: (index: number) => number
} | null = null
const scrollToIndexMock = vi.fn()
const getTotalSizeMock = vi.fn(() => 320)
let virtualItemsMock = [{ index: 0, key: '0', start: 0, size: 32 }]

vi.mock('@tanstack/react-virtual', () => ({
  useVirtualizer: (options: { count: number; overscan: number; estimateSize: (index: number) => number }) => {
    lastVirtualizerOptions = options
    return {
      scrollToIndex: scrollToIndexMock,
      getTotalSize: getTotalSizeMock,
      getVirtualItems: () => virtualItemsMock,
    }
  },
}))

import { useVirtualizedTree } from '../useVirtualizedTree'

function makeNode(overrides: Record<string, unknown>) {
  return {
    id: 'node',
    title: 'Node',
    file_type: 'draft',
    children: [],
    ...overrides,
  }
}

describe('useVirtualizedTree', () => {
  beforeEach(() => {
    lastVirtualizerOptions = null
    scrollToIndexMock.mockReset()
    getTotalSizeMock.mockClear()
    virtualItemsMock = [{ index: 0, key: '0', start: 0, size: 32 }]
  })

  it('returns only root nodes when folders are collapsed', () => {
    const tree = [
      makeNode({ id: 'folder-1', title: 'Folder', file_type: 'folder', children: [makeNode({ id: 'child-1' })] }),
      makeNode({ id: 'file-1', title: 'File' }),
    ]

    const { result } = renderHook(() =>
      useVirtualizedTree(tree as never[], new Set(), { current: document.createElement('div') }),
    )

    expect(result.current.visibleItems.map((item) => item.key)).toEqual(['folder-1', 'file-1'])
    expect(result.current.totalSize).toBe(320)
    expect(result.current.virtualItems).toEqual(virtualItemsMock)
  })

  it('injects create-input rows and nested children for expanded folders', () => {
    const tree = [
      makeNode({
        id: 'folder-1',
        title: 'Folder',
        file_type: 'folder',
        children: [makeNode({ id: 'child-1', title: 'Child file' })],
      }),
    ]

    const { result } = renderHook(() =>
      useVirtualizedTree(tree as never[], new Set(['folder-1']), { current: document.createElement('div') }, 'folder-1'),
    )

    expect(result.current.visibleItems.map((item) => [item.key, item.type, item.depth])).toEqual([
      ['folder-1', 'node', 0],
      ['folder-1-create', 'create-input', 1],
      ['child-1', 'node', 1],
    ])
  })

  it('shows an empty-folder placeholder for expanded folders without children', () => {
    const tree = [makeNode({ id: 'folder-1', file_type: 'folder', children: [] })]

    const { result } = renderHook(() =>
      useVirtualizedTree(tree as never[], new Set(['folder-1']), { current: document.createElement('div') }),
    )

    expect(result.current.visibleItems.map((item) => item.key)).toEqual(['folder-1', 'folder-1-empty'])
    expect(result.current.visibleItems[1]).toMatchObject({
      type: 'empty-folder',
      depth: 1,
      parentFolderId: 'folder-1',
    })
  })

  it('passes sizing rules to the virtualizer and can scroll to a node by id', () => {
    const tree = [
      makeNode({
        id: 'folder-1',
        file_type: 'folder',
        children: [makeNode({ id: 'child-1' })],
      }),
    ]

    const { result } = renderHook(() =>
      useVirtualizedTree(tree as never[], new Set(['folder-1']), { current: document.createElement('div') }, 'folder-1'),
    )

    expect(lastVirtualizerOptions?.count).toBe(3)
    expect(lastVirtualizerOptions?.overscan).toBe(10)
    expect(lastVirtualizerOptions?.estimateSize(0)).toBe(32)
    expect(lastVirtualizerOptions?.estimateSize(1)).toBe(36)

    result.current.scrollToNode('child-1')
    expect(scrollToIndexMock).toHaveBeenCalledWith(2, { align: 'auto' })
  })
})
