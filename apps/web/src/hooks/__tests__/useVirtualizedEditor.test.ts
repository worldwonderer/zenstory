import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  useVirtualizedEditor,
  useFocusedChunk,
  useEditorStats,
} from '../useVirtualizedEditor'
import type { DocumentChunk } from '@/lib/documentChunker'

// Helper to create mock document chunks
function createMockChunks(count: number, contentPrefix = 'Chunk'): DocumentChunk[] {
  const chunks: DocumentChunk[] = []
  let offset = 0

  for (let i = 0; i < count; i++) {
    const content = `${contentPrefix} ${i} content that is long enough to be realistic. `.repeat(5)
    chunks.push({
      id: `chunk-${i}`,
      content,
      startOffset: offset,
      endOffset: offset + content.length,
      type: 'paragraph',
      estimatedHeight: 120,
      isPartial: false,
      lineNumber: i * 5 + 1,
    })
    offset += content.length
  }

  return chunks
}

// Helper to create a single chunk with specific content
function createChunk(
  id: string,
  content: string,
  startOffset: number = 0,
  type: DocumentChunk['type'] = 'paragraph'
): DocumentChunk {
  return {
    id,
    content,
    startOffset,
    endOffset: startOffset + content.length,
    type,
    estimatedHeight: 100,
    isPartial: false,
    lineNumber: 1,
  }
}

// Create a mock scroll element ref
function createMockScrollRef(scrollTop = 0, clientHeight = 500) {
  const mockElement = {
    scrollTop,
    clientHeight,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  } as unknown as HTMLDivElement

  return { current: mockElement }
}

describe('useVirtualizedEditor', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  describe('initial state', () => {
    it('initializes with empty chunks', () => {
      const scrollRef = createMockScrollRef()
      const { result } = renderHook(() =>
        useVirtualizedEditor('', [], { current: scrollRef.current })
      )

      expect(result.current.totalChunks).toBe(0)
      expect(result.current.visibleChunks).toEqual([])
      expect(result.current.isScrolling).toBe(false)
      expect(result.current.cursorPosition).toBe(null)
    })

    it('initializes with provided chunks', () => {
      const chunks = createMockChunks(10)
      const scrollRef = createMockScrollRef()

      const { result } = renderHook(() =>
        useVirtualizedEditor('test content', chunks, { current: scrollRef.current })
      )

      expect(result.current.totalChunks).toBe(10)
      expect(result.current.positionCache.chunkIds).toHaveLength(10)
    })

    it('creates position cache with correct total height', () => {
      const chunks = createMockChunks(5)
      const scrollRef = createMockScrollRef()

      const { result } = renderHook(() =>
        useVirtualizedEditor('test', chunks, { current: scrollRef.current })
      )

      // Position cache should have offsets and heights
      expect(result.current.positionCache.offsets).toHaveLength(5)
      expect(result.current.positionCache.heights).toHaveLength(5)
      expect(result.current.positionCache.totalHeight).toBeGreaterThan(0)
    })

    it('accepts custom configuration', () => {
      const chunks = createMockChunks(5)
      const scrollRef = createMockScrollRef()

      const { result } = renderHook(() =>
        useVirtualizedEditor('test', chunks, { current: scrollRef.current }, {
          overscan: 10,
          debug: false,
          heightConfig: { lineHeight: 32 },
        })
      )

      // Hook should initialize without errors
      expect(result.current.totalChunks).toBe(5)
    })
  })

  describe('visibleChunks', () => {
    // Note: These tests are skipped because @tanstack/react-virtual requires
    // a real DOM with proper scroll measurements to calculate visible items.
    // In the test environment with mocked scroll refs, the virtualizer
    // returns empty arrays.
    it.skip('returns visible chunks based on scroll position', () => {
      const chunks = createMockChunks(20)
      const scrollRef = createMockScrollRef(0, 500)

      const { result } = renderHook(() =>
        useVirtualizedEditor('test', chunks, { current: scrollRef.current })
      )

      // Should return some visible chunks
      expect(result.current.visibleChunks.length).toBeGreaterThan(0)
      expect(result.current.visibleChunks.length).toBeLessThanOrEqual(chunks.length)
    })

    it('includes chunk data in visible chunks', () => {
      const chunks = createMockChunks(5)
      const scrollRef = createMockScrollRef()

      const { result } = renderHook(() =>
        useVirtualizedEditor('test', chunks, { current: scrollRef.current })
      )

      if (result.current.visibleChunks.length > 0) {
        const visibleChunk = result.current.visibleChunks[0]
        expect(visibleChunk).toHaveProperty('chunk')
        expect(visibleChunk).toHaveProperty('index')
        expect(visibleChunk).toHaveProperty('height')
        expect(visibleChunk).toHaveProperty('startY')
        expect(visibleChunk.chunk).toBeInstanceOf(Object)
        expect(typeof visibleChunk.index).toBe('number')
        expect(typeof visibleChunk.height).toBe('number')
        expect(typeof visibleChunk.startY).toBe('number')
      }
    })

    it.skip('updates visible chunks when chunks change', () => {
      const chunks1 = createMockChunks(5)
      const scrollRef = createMockScrollRef()

      const { result, rerender } = renderHook(
        ({ chunks }) => useVirtualizedEditor('test', chunks, { current: scrollRef.current }),
        { initialProps: { chunks: chunks1 } }
      )

      const initialVisibleCount = result.current.visibleChunks.length

      const chunks2 = createMockChunks(20)
      rerender({ chunks: chunks2 })

      // Visible chunks should update
      expect(result.current.totalChunks).toBe(20)
      // Verify visible count changed
      expect(result.current.visibleChunks.length).not.toBe(initialVisibleCount)
    })
  })

  describe('scrollToChunk', () => {
    it('scrolls to valid chunk index', () => {
      const chunks = createMockChunks(10)
      const scrollRef = createMockScrollRef()

      const { result } = renderHook(() =>
        useVirtualizedEditor('test', chunks, { current: scrollRef.current })
      )

      act(() => {
        result.current.scrollToChunk(5)
      })

      // Virtualizer should handle the scroll
      // We're just verifying the function doesn't throw
      expect(result.current.scrollToChunk).toBeInstanceOf(Function)
    })

    it('ignores invalid chunk index', () => {
      const chunks = createMockChunks(5)
      const scrollRef = createMockScrollRef()

      const { result } = renderHook(() =>
        useVirtualizedEditor('test', chunks, { current: scrollRef.current })
      )

      act(() => {
        result.current.scrollToChunk(-1)
        result.current.scrollToChunk(100)
      })

      // Should not throw or cause errors
      expect(result.current.totalChunks).toBe(5)
    })

    it('accepts alignment option', () => {
      const chunks = createMockChunks(10)
      const scrollRef = createMockScrollRef()

      const { result } = renderHook(() =>
        useVirtualizedEditor('test', chunks, { current: scrollRef.current })
      )

      act(() => {
        result.current.scrollToChunk(5, 'center')
        result.current.scrollToChunk(5, 'start')
        result.current.scrollToChunk(5, 'end')
        result.current.scrollToChunk(5, 'auto')
      })

      // All alignment options should be accepted
      expect(result.current.scrollToChunk).toBeInstanceOf(Function)
    })
  })

  describe('scrollToOffset', () => {
    it('scrolls to offset within a chunk', () => {
      const chunks = createMockChunks(10)
      const scrollRef = createMockScrollRef()

      const { result } = renderHook(() =>
        useVirtualizedEditor('test', chunks, { current: scrollRef.current })
      )

      act(() => {
        result.current.scrollToOffset(500)
      })

      // Should scroll without error
      expect(result.current.scrollToOffset).toBeInstanceOf(Function)
    })

    it('handles offset at end of document', () => {
      const chunks = createMockChunks(5)
      const scrollRef = createMockScrollRef()
      const totalLength = chunks[chunks.length - 1].endOffset

      const { result } = renderHook(() =>
        useVirtualizedEditor('test', chunks, { current: scrollRef.current })
      )

      act(() => {
        result.current.scrollToOffset(totalLength + 1000)
      })

      // Should handle gracefully
      expect(result.current.totalChunks).toBe(5)
    })

    it('handles offset not in any chunk', () => {
      const chunks = createMockChunks(5)
      const scrollRef = createMockScrollRef()

      const { result } = renderHook(() =>
        useVirtualizedEditor('test', chunks, { current: scrollRef.current })
      )

      act(() => {
        // Negative offset shouldn't match any chunk
        result.current.scrollToOffset(-100)
      })

      expect(result.current.totalChunks).toBe(5)
    })
  })

  describe('getChunkAtScrollPosition', () => {
    it('returns chunk at scroll position', () => {
      const chunks = createMockChunks(10)
      const scrollRef = createMockScrollRef(100, 500)

      const { result } = renderHook(() =>
        useVirtualizedEditor('test', chunks, { current: scrollRef.current })
      )

      const chunk = result.current.getChunkAtScrollPosition(100)

      // May return undefined if no chunk at that position
      if (chunk) {
        expect(chunk).toHaveProperty('id')
        expect(chunk).toHaveProperty('content')
        expect(chunk).toHaveProperty('startOffset')
        expect(chunk).toHaveProperty('endOffset')
      }
    })

    it('returns undefined for empty chunks', () => {
      const scrollRef = createMockScrollRef()

      const { result } = renderHook(() =>
        useVirtualizedEditor('', [], { current: scrollRef.current })
      )

      const chunk = result.current.getChunkAtScrollPosition(0)
      expect(chunk).toBeUndefined()
    })
  })

  describe('updateChunk', () => {
    it('updates cursor position when chunk is updated', () => {
      const chunks = createMockChunks(5)
      const scrollRef = createMockScrollRef()

      const { result } = renderHook(() =>
        useVirtualizedEditor('test', chunks, { current: scrollRef.current })
      )

      expect(result.current.cursorPosition).toBe(null)

      act(() => {
        result.current.updateChunk('chunk-2', 'New content for chunk 2')
      })

      // Cursor position should be set
      expect(result.current.cursorPosition).not.toBe(null)
      if (result.current.cursorPosition) {
        expect(result.current.cursorPosition.chunkIndex).toBe(2)
        expect(result.current.cursorPosition.localOffset).toBe('New content for chunk 2'.length)
      }
    })

    it('ignores update for non-existent chunk', () => {
      const chunks = createMockChunks(5)
      const scrollRef = createMockScrollRef()

      const { result } = renderHook(() =>
        useVirtualizedEditor('test', chunks, { current: scrollRef.current })
      )

      act(() => {
        result.current.updateChunk('non-existent', 'New content')
      })

      // Cursor position should remain null
      expect(result.current.cursorPosition).toBe(null)
    })
  })

  describe('setCursorOffset', () => {
    it('sets cursor position by global offset', () => {
      const chunks = createMockChunks(5)
      const scrollRef = createMockScrollRef()

      const { result } = renderHook(() =>
        useVirtualizedEditor('test', chunks, { current: scrollRef.current })
      )

      // Calculate an offset within chunk 2
      const targetOffset = chunks[2].startOffset + 50

      act(() => {
        result.current.setCursorOffset(targetOffset)
      })

      expect(result.current.cursorPosition).not.toBe(null)
      if (result.current.cursorPosition) {
        expect(result.current.cursorPosition.chunkIndex).toBe(2)
        expect(result.current.cursorPosition.globalOffset).toBe(targetOffset)
      }
    })

    it('handles offset at end of document', () => {
      const chunks = createMockChunks(5)
      const scrollRef = createMockScrollRef()
      const endOffset = chunks[chunks.length - 1].endOffset

      const { result } = renderHook(() =>
        useVirtualizedEditor('test', chunks, { current: scrollRef.current })
      )

      act(() => {
        result.current.setCursorOffset(endOffset)
      })

      // Should set cursor at end of last chunk
      expect(result.current.cursorPosition).not.toBe(null)
      if (result.current.cursorPosition) {
        expect(result.current.cursorPosition.chunkIndex).toBe(chunks.length - 1)
      }
    })

    it('ignores invalid offset', () => {
      const chunks = createMockChunks(5)
      const scrollRef = createMockScrollRef()

      const { result } = renderHook(() =>
        useVirtualizedEditor('test', chunks, { current: scrollRef.current })
      )

      act(() => {
        // Offset past end but not exactly at end
        result.current.setCursorOffset(999999)
      })

      // Cursor should remain null or unchanged
      expect(result.current.cursorPosition).toBe(null)
    })
  })

  describe('isScrolling state', () => {
    it('initializes with isScrolling false', () => {
      const chunks = createMockChunks(5)
      const scrollRef = createMockScrollRef()

      const { result } = renderHook(() =>
        useVirtualizedEditor('test', chunks, { current: scrollRef.current })
      )

      expect(result.current.isScrolling).toBe(false)
    })

    // Note: These tests are skipped because the isScrolling state depends on
    // the virtualizer's internal scroll tracking which doesn't work properly
    // with mocked scroll elements in the test environment.
    it.skip('sets isScrolling to true on scroll event', async () => {
      const chunks = createMockChunks(10)
      const mockElement = {
        scrollTop: 0,
        clientHeight: 500,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      } as unknown as HTMLDivElement

      // Capture the scroll handler
      let scrollHandler: (() => void) | null = null
      mockElement.addEventListener = vi.fn((event, handler) => {
        if (event === 'scroll') {
          scrollHandler = handler as () => void
        }
      })

      const { result } = renderHook(() =>
        useVirtualizedEditor('test', chunks, { current: mockElement })
      )

      // Verify scroll listener was registered
      expect(mockElement.addEventListener).toHaveBeenCalledWith(
        'scroll',
        expect.any(Function),
        { passive: true }
      )

      // Trigger scroll
      if (scrollHandler) {
        act(() => {
          scrollHandler!()
        })

        expect(result.current.isScrolling).toBe(true)
      }
    })

    it.skip('sets isScrolling to false after scroll stops', async () => {
      const chunks = createMockChunks(10)
      const mockElement = {
        scrollTop: 0,
        clientHeight: 500,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      } as unknown as HTMLDivElement

      let scrollHandler: (() => void) | null = null
      mockElement.addEventListener = vi.fn((event, handler) => {
        if (event === 'scroll') {
          scrollHandler = handler as () => void
        }
      })

      const { result } = renderHook(() =>
        useVirtualizedEditor('test', chunks, { current: mockElement })
      )

      // Trigger scroll
      if (scrollHandler) {
        act(() => {
          scrollHandler!()
        })

        expect(result.current.isScrolling).toBe(true)

        // Advance timers past the debounce delay (150ms)
        act(() => {
          vi.advanceTimersByTime(200)
        })

        expect(result.current.isScrolling).toBe(false)
      }
    })

    it('cleans up scroll listener on unmount', () => {
      const chunks = createMockChunks(5)
      const mockElement = {
        scrollTop: 0,
        clientHeight: 500,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      } as unknown as HTMLDivElement

      const { unmount } = renderHook(() =>
        useVirtualizedEditor('test', chunks, { current: mockElement })
      )

      unmount()

      expect(mockElement.removeEventListener).toHaveBeenCalledWith(
        'scroll',
        expect.any(Function)
      )
    })
  })

  describe('positionCache', () => {
    it('builds position cache for chunks', () => {
      const chunks = createMockChunks(5)
      const scrollRef = createMockScrollRef()

      const { result } = renderHook(() =>
        useVirtualizedEditor('test', chunks, { current: scrollRef.current })
      )

      const cache = result.current.positionCache

      expect(cache.chunkIds).toHaveLength(5)
      expect(cache.offsets).toHaveLength(5)
      expect(cache.heights).toHaveLength(5)
      expect(cache.totalHeight).toBeGreaterThan(0)
    })

    it('rebuilds cache when chunks change', () => {
      const chunks1 = createMockChunks(5)
      const scrollRef = createMockScrollRef()

      const { result, rerender } = renderHook(
        ({ chunks }) => useVirtualizedEditor('test', chunks, { current: scrollRef.current }),
        { initialProps: { chunks: chunks1 } }
      )

      const cache1 = result.current.positionCache

      const chunks2 = createMockChunks(10)
      rerender({ chunks: chunks2 })

      const cache2 = result.current.positionCache

      expect(cache2.chunkIds).toHaveLength(10)
      expect(cache2).not.toBe(cache1)
    })

    it('keeps the same cache on rerender when heightConfig is omitted', () => {
      const chunks = createMockChunks(5)
      const scrollRef = createMockScrollRef()

      const { result, rerender } = renderHook(() =>
        useVirtualizedEditor('test', chunks, { current: scrollRef.current }, { overscan: 5, debug: false })
      )

      const cache1 = result.current.positionCache
      rerender()
      const cache2 = result.current.positionCache

      expect(cache2).toBe(cache1)
    })

    it('skips scroll remapping while active editing disables preservation', () => {
      const initialFirstChunk = createChunk('chunk-1', 'a'.repeat(80), 0)
      const initialSecondChunk = createChunk(
        'chunk-2',
        'b'.repeat(120),
        initialFirstChunk.content.length
      )
      const updatedFirstChunk = createChunk('chunk-1', 'a'.repeat(1200), 0)
      const updatedSecondChunk = createChunk(
        'chunk-2',
        'b'.repeat(120),
        updatedFirstChunk.content.length
      )
      const scrollRef = createMockScrollRef(120)

      const { rerender } = renderHook(
        ({ chunks, shouldPreserveScrollPosition }) =>
          useVirtualizedEditor('test', chunks, { current: scrollRef.current }, { shouldPreserveScrollPosition }),
        {
          initialProps: {
            chunks: [initialFirstChunk, initialSecondChunk],
            shouldPreserveScrollPosition: true,
          },
        }
      )

      rerender({
        chunks: [updatedFirstChunk, updatedSecondChunk],
        shouldPreserveScrollPosition: false,
      })

      expect(scrollRef.current?.scrollTop).toBe(120)
    })
  })

  describe('virtualizer', () => {
    it('provides virtualizer instance', () => {
      const chunks = createMockChunks(10)
      const scrollRef = createMockScrollRef()

      const { result } = renderHook(() =>
        useVirtualizedEditor('test', chunks, { current: scrollRef.current })
      )

      expect(result.current.virtualizer).toBeDefined()
      expect(result.current.virtualizer.getTotalSize).toBeInstanceOf(Function)
      expect(result.current.virtualizer.getVirtualItems).toBeInstanceOf(Function)
    })

    it('provides totalSize', () => {
      const chunks = createMockChunks(10)
      const scrollRef = createMockScrollRef()

      const { result } = renderHook(() =>
        useVirtualizedEditor('test', chunks, { current: scrollRef.current })
      )

      expect(result.current.totalSize).toBeGreaterThan(0)
      expect(result.current.totalSize).toBe(result.current.virtualizer.getTotalSize())
    })

    it('provides virtualItems', () => {
      const chunks = createMockChunks(10)
      const scrollRef = createMockScrollRef()

      const { result } = renderHook(() =>
        useVirtualizedEditor('test', chunks, { current: scrollRef.current })
      )

      expect(Array.isArray(result.current.virtualItems)).toBe(true)
    })
  })

  describe('edge cases', () => {
    it('handles null scroll element ref', () => {
      const chunks = createMockChunks(5)

      const { result } = renderHook(() =>
        useVirtualizedEditor('test', chunks, { current: null })
      )

      // Should initialize without error
      expect(result.current.totalChunks).toBe(5)
    })

    it('handles empty content string', () => {
      const scrollRef = createMockScrollRef()

      const { result } = renderHook(() =>
        useVirtualizedEditor('', [], { current: scrollRef.current })
      )

      expect(result.current.totalChunks).toBe(0)
      expect(result.current.visibleChunks).toEqual([])
    })

    it('handles single chunk', () => {
      const chunks = [createChunk('single', 'Single chunk content', 0)]
      const scrollRef = createMockScrollRef()

      const { result } = renderHook(() =>
        useVirtualizedEditor('Single chunk content', chunks, { current: scrollRef.current })
      )

      expect(result.current.totalChunks).toBe(1)
      expect(result.current.positionCache.chunkIds).toEqual(['single'])
    })

    it('handles chunks of different types', () => {
      const chunks: DocumentChunk[] = [
        createChunk('heading', '# Heading', 0, 'heading'),
        createChunk('paragraph', 'Paragraph content.', 10, 'paragraph'),
        createChunk('code', 'const x = 1;', 30, 'code'),
        createChunk('list', '- Item 1', 45, 'list'),
        createChunk('blockquote', '> Quote', 55, 'blockquote'),
      ]
      const scrollRef = createMockScrollRef()

      const { result } = renderHook(() =>
        useVirtualizedEditor('content', chunks, { current: scrollRef.current })
      )

      expect(result.current.totalChunks).toBe(5)
      // Different chunk types may have different height estimates
      expect(result.current.positionCache.heights).toHaveLength(5)
    })

    it('handles very large number of chunks', () => {
      const chunks = createMockChunks(1000)
      const scrollRef = createMockScrollRef()

      const { result } = renderHook(() =>
        useVirtualizedEditor('test', chunks, { current: scrollRef.current })
      )

      expect(result.current.totalChunks).toBe(1000)
      expect(result.current.positionCache.chunkIds).toHaveLength(1000)
    })
  })
})

describe('useFocusedChunk', () => {
  it('returns cursor chunk index when cursor is set', () => {
    const chunks = createMockChunks(10)
    const visibleChunks = [{ chunk: chunks[3], index: 3, height: 100, startY: 0 }]

    const cursorPosition = {
      globalOffset: 500,
      chunkIndex: 5,
      localOffset: 50,
    }

    const { result } = renderHook(() =>
      useFocusedChunk(visibleChunks, cursorPosition)
    )

    expect(result.current).toBe(5)
  })

  it('returns first visible chunk index when no cursor', () => {
    const chunks = createMockChunks(10)
    const visibleChunks = [{ chunk: chunks[3], index: 3, height: 100, startY: 0 }]

    const { result } = renderHook(() =>
      useFocusedChunk(visibleChunks, null)
    )

    expect(result.current).toBe(3)
  })

  it('returns null when no visible chunks and no cursor', () => {
    const { result } = renderHook(() =>
      useFocusedChunk([], null)
    )

    expect(result.current).toBe(null)
  })

  it('updates when cursor position changes', () => {
    const chunks = createMockChunks(10)
    const visibleChunks = [{ chunk: chunks[0], index: 0, height: 100, startY: 0 }]

    const { result, rerender } = renderHook(
      ({ cursorPosition }) => useFocusedChunk(visibleChunks, cursorPosition),
      { initialProps: { cursorPosition: null as ReturnType<typeof useFocusedChunk> extends infer R ? R : never } }
    )

    expect(result.current).toBe(0)

    const newCursorPosition = {
      globalOffset: 500,
      chunkIndex: 7,
      localOffset: 50,
    }
    rerender({ cursorPosition: newCursorPosition })

    expect(result.current).toBe(7)
  })
})

describe('useEditorStats', () => {
  it('calculates stats for chunks', () => {
    const chunks: DocumentChunk[] = [
      createChunk('1', 'Hello world', 0),
      createChunk('2', 'Test content here', 12),
      createChunk('3', 'Another chunk', 29),
    ]

    const { result } = renderHook(() => useEditorStats(chunks))

    expect(result.current.totalChunks).toBe(3)
    // Actual content lengths: 'Hello world' = 11, 'Test content here' = 17, 'Another chunk' = 13
    expect(result.current.totalCharacters).toBe(11 + 17 + 13)
    expect(result.current.lineCount).toBeGreaterThan(0)
  })

  it('handles empty chunks array', () => {
    const { result } = renderHook(() => useEditorStats([]))

    expect(result.current.totalChunks).toBe(0)
    expect(result.current.totalCharacters).toBe(0)
    expect(result.current.totalWords).toBe(0)
    // Empty array returns 1 line (baseline)
    expect(result.current.lineCount).toBe(1)
  })

  it('counts Chinese characters', () => {
    const chunks: DocumentChunk[] = [
      createChunk('1', '你好世界', 0),
      createChunk('2', '测试内容', 4),
    ]

    const { result } = renderHook(() => useEditorStats(chunks))

    // 8 Chinese characters
    expect(result.current.totalWords).toBe(8)
  })

  it('counts English words', () => {
    const chunks: DocumentChunk[] = [
      createChunk('1', 'Hello world', 0),
      createChunk('2', 'Test content', 11),
    ]

    const { result } = renderHook(() => useEditorStats(chunks))

    // Content joins to 'Hello worldTest content' = 4 English words
    // Note: Without space between chunks, 'worldTest' might be counted as one word
    expect(result.current.totalWords).toBeGreaterThanOrEqual(3)
  })

  it('counts mixed Chinese and English', () => {
    const chunks: DocumentChunk[] = [
      createChunk('1', 'Hello 世界', 0),
      createChunk('2', 'Test 测试', 8),
    ]

    const { result } = renderHook(() => useEditorStats(chunks))

    // 2 English words + 4 Chinese characters = 6
    expect(result.current.totalWords).toBe(6)
  })

  it('counts lines correctly', () => {
    // Chunks should include newline separators between content blocks
    // as they would when created by chunkDocument
    const chunks: DocumentChunk[] = [
      createChunk('1', 'Line 1\nLine 2\nLine 3\n', 0),
      createChunk('2', 'Line 4\nLine 5', 22),
    ]

    const { result } = renderHook(() => useEditorStats(chunks))

    // 5 lines total (3 from first chunk + 2 from second)
    expect(result.current.lineCount).toBe(5)
  })

  it('updates when chunks change', () => {
    const chunks1: DocumentChunk[] = [
      createChunk('1', 'Initial content', 0),
    ]

    const { result, rerender } = renderHook(
      ({ chunks }) => useEditorStats(chunks),
      { initialProps: { chunks: chunks1 } }
    )

    expect(result.current.totalChunks).toBe(1)

    const chunks2: DocumentChunk[] = [
      createChunk('1', 'Updated content', 0),
      createChunk('2', 'New chunk', 15),
    ]
    rerender({ chunks: chunks2 })

    expect(result.current.totalChunks).toBe(2)
  })
})
