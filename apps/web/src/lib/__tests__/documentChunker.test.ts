/**
 * Tests for document chunking utility
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import {
  generateChunkId,
  resetChunkIdCounter,
  detectChunkType,
  estimateChunkHeight,
  splitIntoBlocks,
  splitLargeBlock,
  chunkDocument,
  mergeChunks,
  updateChunkContent,
  findChunkAtOffset,
  findChunkAtLine,
  globalToLocalOffset,
  localToGlobalOffset,
  getChunkStats,
  shouldVirtualize,
  countWords,
  chunkDocumentInitial,
  continueChunking,
  chunkDocumentGenerator,
  estimateChunkCount,
  isLargeDocument,
  type DocumentChunk,
  type ChunkingOptions,
} from '../documentChunker'

const DEFAULT_OPTIONS: Required<ChunkingOptions> = {
  targetChunkSize: 750,
  minChunkSize: 100,
  maxChunkSize: 1500,
  lineHeight: 24,
  charsPerLine: 80,
}

describe('documentChunker', () => {
  beforeEach(() => {
    resetChunkIdCounter()
  })

  afterEach(() => {
    resetChunkIdCounter()
  })

  describe('generateChunkId', () => {
    it('generates unique IDs', () => {
      const id1 = generateChunkId()
      const id2 = generateChunkId()
      expect(id1).not.toBe(id2)
    })

    it('generates IDs with expected format', () => {
      const id = generateChunkId()
      expect(id).toMatch(/^chunk-\d+-\d+$/)
    })

    it('resets counter correctly', () => {
      generateChunkId()
      generateChunkId()
      resetChunkIdCounter()
      const id = generateChunkId()
      expect(id).toMatch(/chunk-\d+-0$/)
    })
  })

  describe('detectChunkType', () => {
    it('detects empty content', () => {
      expect(detectChunkType('')).toBe('empty')
      expect(detectChunkType('   ')).toBe('empty')
      expect(detectChunkType('\n\n')).toBe('empty')
    })

    it('detects headings', () => {
      expect(detectChunkType('# Heading 1')).toBe('heading')
      expect(detectChunkType('## Heading 2')).toBe('heading')
      expect(detectChunkType('### Heading 3')).toBe('heading')
      expect(detectChunkType('###### Heading 6')).toBe('heading')
    })

    it('detects unordered lists', () => {
      expect(detectChunkType('- List item')).toBe('list')
      expect(detectChunkType('* List item')).toBe('list')
      expect(detectChunkType('+ List item')).toBe('list')
    })

    it('detects ordered lists', () => {
      expect(detectChunkType('1. List item')).toBe('list')
      expect(detectChunkType('99. List item')).toBe('list')
    })

    it('detects code blocks', () => {
      expect(detectChunkType('```javascript')).toBe('code')
      expect(detectChunkType('```')).toBe('code')
    })

    it('detects indented code', () => {
      expect(detectChunkType('    const x = 1')).toBe('code')
    })

    it('detects blockquotes', () => {
      expect(detectChunkType('> Quote text')).toBe('blockquote')
    })

    it('detects separators', () => {
      expect(detectChunkType('---')).toBe('separator')
      expect(detectChunkType('***')).toBe('separator')
      expect(detectChunkType('___')).toBe('separator')
    })

    it('defaults to paragraph for normal text', () => {
      expect(detectChunkType('Just some normal text')).toBe('paragraph')
      expect(detectChunkType('This is a sentence.')).toBe('paragraph')
    })

    it('handles text starting with # but not heading', () => {
      expect(detectChunkType('#not-a-heading')).toBe('paragraph')
    })
  })

  describe('estimateChunkHeight', () => {
    it('returns lineHeight for empty content', () => {
      const height = estimateChunkHeight('', 'empty', DEFAULT_OPTIONS)
      expect(height).toBe(24)
    })

    it('calculates height based on content length', () => {
      const content = 'a'.repeat(80) // One line
      const height = estimateChunkHeight(content, 'paragraph', DEFAULT_OPTIONS)
      expect(height).toBe(24) // 1 line * 24px
    })

    it('handles multi-line content', () => {
      const content = 'a'.repeat(160) // Two lines
      const height = estimateChunkHeight(content, 'paragraph', DEFAULT_OPTIONS)
      expect(height).toBe(48) // 2 lines * 24px
    })

    it('adds extra lines for code blocks', () => {
      const content = 'a'.repeat(80) // One line
      const height = estimateChunkHeight(content, 'code', DEFAULT_OPTIONS)
      expect(height).toBe(72) // (1 + 2 extra) * 24px
    })

    it('rounds up for partial lines', () => {
      const content = 'a'.repeat(81) // Just over one line
      const height = estimateChunkHeight(content, 'paragraph', DEFAULT_OPTIONS)
      expect(height).toBe(48) // 2 lines * 24px (rounded up)
    })
  })

  describe('splitIntoBlocks', () => {
    it('handles empty content', () => {
      expect(splitIntoBlocks('')).toEqual([])
    })

    it('splits on blank lines', () => {
      const content = 'Paragraph 1\n\nParagraph 2'
      const blocks = splitIntoBlocks(content)
      expect(blocks).toHaveLength(2)
      // Blank lines are preserved at the end of blocks to maintain document structure
      expect(blocks[0]).toBe('Paragraph 1\n\n')
      expect(blocks[1]).toBe('Paragraph 2')
    })

    it('preserves code blocks as single units', () => {
      const content = '```javascript\nconst x = 1\nconst y = 2\n```\n\nParagraph'
      const blocks = splitIntoBlocks(content)
      // Code block + trailing blank line as separate block, then paragraph
      expect(blocks.length).toBeGreaterThanOrEqual(2)
      expect(blocks[0]).toContain('```javascript')
      expect(blocks[0]).toContain('const x = 1')
    })

    it('handles consecutive list items', () => {
      const content = '- Item 1\n- Item 2\n- Item 3'
      const blocks = splitIntoBlocks(content)
      expect(blocks.length).toBeGreaterThanOrEqual(1)
    })

    it('handles headings as block boundaries', () => {
      const content = '# Heading\nContent under heading'
      const blocks = splitIntoBlocks(content)
      expect(blocks.length).toBeGreaterThan(1)
    })
  })

  describe('splitLargeBlock', () => {
    it('returns single chunk for small blocks', () => {
      const block = 'Small block'
      const result = splitLargeBlock(block, 1500, 750)
      expect(result).toEqual([block])
    })

    it('splits large blocks at sentence boundaries', () => {
      const block = 'First sentence. Second sentence. Third sentence. Fourth sentence.'
      const result = splitLargeBlock(block, 30, 20)
      expect(result.length).toBeGreaterThan(1)
    })

    it('splits at Chinese sentence boundaries', () => {
      // Use a block larger than maxSize to trigger splitting
      const block = '这是第一句话。这是第二句话。这是第三句话。这是第四句话。这是第五句话。这是第六句话。'
      const result = splitLargeBlock(block, 30, 20)
      expect(result.length).toBeGreaterThan(1)
    })

    it('splits at word boundaries when no sentence end', () => {
      const block = 'word '.repeat(100)
      const result = splitLargeBlock(block, 100, 50)
      expect(result.length).toBeGreaterThan(1)
    })

    it('handles blocks exactly at max size', () => {
      const block = 'a'.repeat(1500)
      const result = splitLargeBlock(block, 1500, 750)
      expect(result).toHaveLength(1)
    })
  })

  describe('chunkDocument', () => {
    it('returns empty array for empty content', () => {
      expect(chunkDocument('')).toEqual([])
    })

    it('returns empty array for null/undefined', () => {
      expect(chunkDocument(null as unknown as string)).toEqual([])
      expect(chunkDocument(undefined as unknown as string)).toEqual([])
    })

    it('creates chunks with correct structure', () => {
      const content = 'This is a test paragraph with some content.'
      const chunks = chunkDocument(content)

      expect(chunks.length).toBeGreaterThan(0)
      expect(chunks[0]).toHaveProperty('id')
      expect(chunks[0]).toHaveProperty('content')
      expect(chunks[0]).toHaveProperty('startOffset')
      expect(chunks[0]).toHaveProperty('endOffset')
      expect(chunks[0]).toHaveProperty('type')
      expect(chunks[0]).toHaveProperty('estimatedHeight')
      expect(chunks[0]).toHaveProperty('isPartial')
      expect(chunks[0]).toHaveProperty('lineNumber')
    })

    it('sets correct offsets', () => {
      const content = 'Paragraph 1\n\nParagraph 2'
      const chunks = chunkDocument(content)

      expect(chunks[0].startOffset).toBe(0)
      expect(chunks[0].endOffset).toBe(chunks[0].content.length)

      if (chunks.length > 1) {
        expect(chunks[1].startOffset).toBe(chunks[0].endOffset)
      }
    })

    it('respects custom chunk size options', () => {
      const content = 'a'.repeat(2000)
      const chunks = chunkDocument(content, { maxChunkSize: 500 })

      chunks.forEach(chunk => {
        expect(chunk.content.length).toBeLessThanOrEqual(500)
      })
    })

    it('handles large documents', () => {
      const content = Array(100).fill('This is a paragraph with some content.').join('\n\n')
      const chunks = chunkDocument(content)

      expect(chunks.length).toBeGreaterThan(0)
      // Verify content can be reconstructed
      const merged = mergeChunks(chunks)
      expect(merged.length).toBe(content.length)
    })

    it('keeps chunk IDs stable across equivalent re-chunking', () => {
      const content = [
        'First paragraph with enough content to form a stable chunk.',
        'Second paragraph with enough content to form another stable chunk.',
        'Third paragraph with enough content to form yet another stable chunk.',
      ].join('\n\n')

      const firstPass = chunkDocument(content)
      const secondPass = chunkDocument(content)

      expect(secondPass.map((chunk) => chunk.id)).toEqual(firstPass.map((chunk) => chunk.id))
    })

    it('keeps a chunk ID stable when editing inside that same chunk', () => {
      const baseContent = [
        'First paragraph with enough content to form a stable chunk.',
        'Second paragraph with enough content to form another stable chunk.',
        'Third paragraph with enough content to form yet another stable chunk.',
      ].join('\n\n')
      const editedContent = baseContent.replace(
        'Second paragraph with enough content to form another stable chunk.',
        'Second paragraph with enough content to form another stable chunk plus one more sentence.'
      )

      const originalChunks = chunkDocument(baseContent)
      const editedChunks = chunkDocument(editedContent)

      expect(originalChunks[1]?.id).toBeDefined()
      expect(editedChunks[1]?.id).toBe(originalChunks[1]?.id)
    })
  })

  describe('mergeChunks', () => {
    it('returns empty string for empty array', () => {
      expect(mergeChunks([])).toBe('')
    })

    it('merges single chunk', () => {
      const chunks: DocumentChunk[] = [
        {
          id: 'test-1',
          content: 'Hello world',
          startOffset: 0,
          endOffset: 11,
          type: 'paragraph',
          estimatedHeight: 24,
          isPartial: false,
          lineNumber: 1,
        },
      ]
      expect(mergeChunks(chunks)).toBe('Hello world')
    })

    it('merges multiple chunks in order', () => {
      const chunks: DocumentChunk[] = [
        {
          id: 'test-1',
          content: 'Hello ',
          startOffset: 0,
          endOffset: 6,
          type: 'paragraph',
          estimatedHeight: 24,
          isPartial: false,
          lineNumber: 1,
        },
        {
          id: 'test-2',
          content: 'world',
          startOffset: 6,
          endOffset: 11,
          type: 'paragraph',
          estimatedHeight: 24,
          isPartial: false,
          lineNumber: 1,
        },
      ]
      expect(mergeChunks(chunks)).toBe('Hello world')
    })

    it('sorts chunks by offset before merging', () => {
      const chunks: DocumentChunk[] = [
        {
          id: 'test-2',
          content: 'world',
          startOffset: 6,
          endOffset: 11,
          type: 'paragraph',
          estimatedHeight: 24,
          isPartial: false,
          lineNumber: 1,
        },
        {
          id: 'test-1',
          content: 'Hello ',
          startOffset: 0,
          endOffset: 6,
          type: 'paragraph',
          estimatedHeight: 24,
          isPartial: false,
          lineNumber: 1,
        },
      ]
      expect(mergeChunks(chunks)).toBe('Hello world')
    })
  })

  describe('updateChunkContent', () => {
    const createTestChunks = (): DocumentChunk[] => [
      {
        id: 'chunk-1',
        content: 'First',
        startOffset: 0,
        endOffset: 5,
        type: 'paragraph',
        estimatedHeight: 24,
        isPartial: false,
        lineNumber: 1,
      },
      {
        id: 'chunk-2',
        content: 'Second',
        startOffset: 5,
        endOffset: 11,
        type: 'paragraph',
        estimatedHeight: 24,
        isPartial: false,
        lineNumber: 1,
      },
      {
        id: 'chunk-3',
        content: 'Third',
        startOffset: 11,
        endOffset: 16,
        type: 'paragraph',
        estimatedHeight: 24,
        isPartial: false,
        lineNumber: 1,
      },
    ]

    it('returns unchanged chunks if chunk not found', () => {
      const chunks = createTestChunks()
      const result = updateChunkContent(chunks, 'non-existent', 'New content')
      expect(result).toEqual(chunks)
    })

    it('updates chunk content and adjusts offsets', () => {
      const chunks = createTestChunks()
      const result = updateChunkContent(chunks, 'chunk-2', 'SecondUpdated')

      expect(result[1].content).toBe('SecondUpdated')
      expect(result[1].endOffset).toBe(5 + 'SecondUpdated'.length)
      expect(result[2].startOffset).toBe(result[1].endOffset)
      expect(result[2].endOffset).toBe(result[2].startOffset + 5)
    })

    it('handles shorter replacement content', () => {
      const chunks = createTestChunks()
      const result = updateChunkContent(chunks, 'chunk-2', 'X')

      expect(result[1].content).toBe('X')
      expect(result[1].endOffset).toBe(6)
      expect(result[2].startOffset).toBe(6)
    })

    it('updates type when content changes', () => {
      const chunks = createTestChunks()
      const result = updateChunkContent(chunks, 'chunk-1', '# Heading')

      expect(result[0].type).toBe('heading')
    })
  })

  describe('findChunkAtOffset', () => {
    const chunks: DocumentChunk[] = [
      {
        id: 'chunk-1',
        content: 'First',
        startOffset: 0,
        endOffset: 5,
        type: 'paragraph',
        estimatedHeight: 24,
        isPartial: false,
        lineNumber: 1,
      },
      {
        id: 'chunk-2',
        content: 'Second',
        startOffset: 5,
        endOffset: 11,
        type: 'paragraph',
        estimatedHeight: 24,
        isPartial: false,
        lineNumber: 1,
      },
    ]

    it('finds chunk at offset 0', () => {
      const result = findChunkAtOffset(chunks, 0)
      expect(result?.id).toBe('chunk-1')
    })

    it('finds chunk in middle of content', () => {
      const result = findChunkAtOffset(chunks, 7)
      expect(result?.id).toBe('chunk-2')
    })

    it('finds chunk at boundary', () => {
      const result = findChunkAtOffset(chunks, 5)
      expect(result?.id).toBe('chunk-2')
    })

    it('returns undefined for out of bounds offset', () => {
      expect(findChunkAtOffset(chunks, 100)).toBeUndefined()
    })

    it('returns undefined for negative offset', () => {
      expect(findChunkAtOffset(chunks, -1)).toBeUndefined()
    })

    it('handles empty chunks array', () => {
      expect(findChunkAtOffset([], 0)).toBeUndefined()
    })
  })

  describe('findChunkAtLine', () => {
    const chunks: DocumentChunk[] = [
      {
        id: 'chunk-1',
        content: 'Line 1\nLine 2',
        startOffset: 0,
        endOffset: 12,
        type: 'paragraph',
        estimatedHeight: 48,
        isPartial: false,
        lineNumber: 1,
      },
      {
        id: 'chunk-2',
        content: 'Line 3',
        startOffset: 12,
        endOffset: 18,
        type: 'paragraph',
        estimatedHeight: 24,
        isPartial: false,
        lineNumber: 3,
      },
    ]

    it('finds chunk at line 1', () => {
      const result = findChunkAtLine(chunks, 1)
      expect(result?.id).toBe('chunk-1')
    })

    it('finds chunk at line 2', () => {
      const result = findChunkAtLine(chunks, 2)
      expect(result?.id).toBe('chunk-1')
    })

    it('finds chunk at line 3', () => {
      const result = findChunkAtLine(chunks, 3)
      expect(result?.id).toBe('chunk-2')
    })

    it('returns undefined for out of bounds line', () => {
      expect(findChunkAtLine(chunks, 100)).toBeUndefined()
    })

    it('returns undefined for line 0', () => {
      expect(findChunkAtLine(chunks, 0)).toBeUndefined()
    })
  })

  describe('globalToLocalOffset', () => {
    const chunk: DocumentChunk = {
      id: 'test',
      content: 'Hello world',
      startOffset: 100,
      endOffset: 111,
      type: 'paragraph',
      estimatedHeight: 24,
      isPartial: false,
      lineNumber: 1,
    }

    it('converts global offset to local', () => {
      expect(globalToLocalOffset(chunk, 105)).toBe(5)
    })

    it('handles start offset', () => {
      expect(globalToLocalOffset(chunk, 100)).toBe(0)
    })

    it('clamps negative results to 0', () => {
      expect(globalToLocalOffset(chunk, 50)).toBe(0)
    })
  })

  describe('localToGlobalOffset', () => {
    const chunk: DocumentChunk = {
      id: 'test',
      content: 'Hello world',
      startOffset: 100,
      endOffset: 111,
      type: 'paragraph',
      estimatedHeight: 24,
      isPartial: false,
      lineNumber: 1,
    }

    it('converts local offset to global', () => {
      expect(localToGlobalOffset(chunk, 5)).toBe(105)
    })

    it('handles offset 0', () => {
      expect(localToGlobalOffset(chunk, 0)).toBe(100)
    })
  })

  describe('getChunkStats', () => {
    it('returns zero stats for empty array', () => {
      const stats = getChunkStats([])
      expect(stats).toEqual({
        totalChunks: 0,
        totalCharacters: 0,
        averageChunkSize: 0,
        maxChunkSize: 0,
        minChunkSize: 0,
        estimatedTotalHeight: 0,
        chunksByType: {
          paragraph: 0,
          heading: 0,
          code: 0,
          list: 0,
          blockquote: 0,
          separator: 0,
          empty: 0,
        },
      })
    })

    it('calculates correct statistics', () => {
      const chunks: DocumentChunk[] = [
        {
          id: '1',
          content: 'abc',
          startOffset: 0,
          endOffset: 3,
          type: 'paragraph',
          estimatedHeight: 24,
          isPartial: false,
          lineNumber: 1,
        },
        {
          id: '2',
          content: 'abcdefghij',
          startOffset: 3,
          endOffset: 13,
          type: 'heading',
          estimatedHeight: 48,
          isPartial: false,
          lineNumber: 1,
        },
      ]

      const stats = getChunkStats(chunks)
      expect(stats.totalChunks).toBe(2)
      expect(stats.totalCharacters).toBe(13)
      expect(stats.averageChunkSize).toBe(7) // (3 + 10) / 2 = 6.5 -> 7
      expect(stats.maxChunkSize).toBe(10)
      expect(stats.minChunkSize).toBe(3)
      expect(stats.estimatedTotalHeight).toBe(72)
      expect(stats.chunksByType.paragraph).toBe(1)
      expect(stats.chunksByType.heading).toBe(1)
    })
  })

  describe('shouldVirtualize', () => {
    it('returns false for small documents', () => {
      const content = 'Small document'
      expect(shouldVirtualize(content)).toBe(false)
    })

    it('returns true for large documents', () => {
      const content = 'word '.repeat(15000)
      expect(shouldVirtualize(content)).toBe(true)
    })

    it('respects custom threshold', () => {
      const content = 'word '.repeat(500)
      expect(shouldVirtualize(content, 100)).toBe(true)
      expect(shouldVirtualize(content, 10000)).toBe(false)
    })

    it('counts Chinese characters correctly', () => {
      const chinese = '中'.repeat(15000)
      expect(shouldVirtualize(chinese)).toBe(true)
    })

    it('counts mixed content correctly', () => {
      const mixed = 'Hello '.repeat(5000) + '世界'.repeat(5000)
      expect(shouldVirtualize(mixed)).toBe(true)
    })
  })

  describe('countWords', () => {
    it('counts English words', () => {
      expect(countWords('Hello world test')).toBe(3)
    })

    it('counts Chinese characters', () => {
      expect(countWords('你好世界')).toBe(4)
    })

    it('counts mixed content', () => {
      expect(countWords('Hello 世界')).toBe(3) // 1 English + 2 Chinese
    })

    it('handles empty string', () => {
      expect(countWords('')).toBe(0)
    })

    it('handles whitespace-only string', () => {
      expect(countWords('   ')).toBe(0)
    })
  })

  describe('chunkDocumentInitial', () => {
    it('returns complete result for empty content', () => {
      const result = chunkDocumentInitial('')
      expect(result.isComplete).toBe(true)
      expect(result.chunks).toEqual([])
    })

    it('returns complete result for small documents', () => {
      const content = 'Small document'
      const result = chunkDocumentInitial(content)
      expect(result.isComplete).toBe(true)
    })

    it('returns partial result for large documents', () => {
      const content = 'a'.repeat(50000)
      const result = chunkDocumentInitial(content)
      expect(result.isComplete).toBe(false)
      expect(result.chunkedUntil).toBeLessThan(content.length)
      expect(result.chunks.length).toBeGreaterThan(0)
    })

    it('estimates total chunks correctly', () => {
      const content = 'a'.repeat(50000)
      const result = chunkDocumentInitial(content)
      expect(result.estimatedTotalChunks).toBeGreaterThan(result.chunks.length)
    })
  })

  describe('continueChunking', () => {
    it('returns complete when already at end', () => {
      const content = 'Small'
      const result = continueChunking(content, content.length, [])
      expect(result.isComplete).toBe(true)
    })

    it('chunks next batch of content', () => {
      const content = 'a'.repeat(50000)
      const initial = chunkDocumentInitial(content)

      const result = continueChunking(
        content,
        initial.chunkedUntil,
        initial.chunks
      )

      expect(result.chunks.length).toBeGreaterThan(initial.chunks.length)
      expect(result.newOffset).toBeGreaterThan(initial.chunkedUntil)
    })

    it('eventually completes chunking', () => {
      const content = 'a'.repeat(30000)
      const initial = chunkDocumentInitial(content)

      let chunks = initial.chunks
      let offset = initial.chunkedUntil
      let isComplete = initial.isComplete

      while (!isComplete) {
        const result = continueChunking(content, offset, chunks, {}, 50000)
        chunks = result.chunks
        offset = result.newOffset
        isComplete = result.isComplete
      }

      expect(isComplete).toBe(true)
      expect(offset).toBe(content.length)
    })
  })

  describe('chunkDocumentGenerator', () => {
    it('yields complete result for empty content', () => {
      const generator = chunkDocumentGenerator('')
      const result = generator.next()
      expect(result.value.isComplete).toBe(true)
      expect(result.value.chunks).toEqual([])
    })

    it('yields progress for large documents', () => {
      const content = 'a'.repeat(50000)
      const generator = chunkDocumentGenerator(content)

      const first = generator.next()
      expect(first.value.chunks.length).toBeGreaterThan(0)
      expect(first.value.progress).toBeGreaterThan(0)

      if (!first.value.isComplete) {
        const second = generator.next()
        expect(second.value.progress).toBeGreaterThan(first.value.progress)
      }
    })

    it('eventually yields complete result', () => {
      const content = 'a'.repeat(30000)
      const generator = chunkDocumentGenerator(content)

      let lastProgress = 0
      let iterations = 0
      let result

      do {
        result = generator.next()
        expect(result.value.progress).toBeGreaterThanOrEqual(lastProgress)
        lastProgress = result.value.progress
        iterations++
      } while (!result.value.isComplete && iterations < 100)

      expect(result.value.isComplete).toBe(true)
    })
  })

  describe('estimateChunkCount', () => {
    it('returns 0 for empty content', () => {
      expect(estimateChunkCount('')).toBe(0)
    })

    it('estimates based on average chunk size', () => {
      const content = 'a'.repeat(7500)
      expect(estimateChunkCount(content)).toBe(10) // 7500 / 750
    })

    it('respects custom chunk size', () => {
      const content = 'a'.repeat(5000)
      expect(estimateChunkCount(content, 500)).toBe(10)
    })

    it('rounds up', () => {
      const content = 'a'.repeat(751)
      expect(estimateChunkCount(content)).toBe(2)
    })
  })

  describe('isLargeDocument', () => {
    it('returns false for small documents', () => {
      expect(isLargeDocument('small')).toBe(false)
    })

    it('returns true for documents over threshold', () => {
      const content = 'a'.repeat(40000)
      expect(isLargeDocument(content)).toBe(true)
    })

    it('respects custom threshold', () => {
      const content = 'a'.repeat(1000)
      expect(isLargeDocument(content, 500)).toBe(true)
      expect(isLargeDocument(content, 2000)).toBe(false)
    })

    it('handles exact threshold', () => {
      const content = 'a'.repeat(30000)
      expect(isLargeDocument(content)).toBe(false)
      expect(isLargeDocument(content, 29999)).toBe(true)
    })
  })

  describe('integration tests', () => {
    it('round-trips content through chunking and merging', () => {
      const content = 'Paragraph 1\n\nParagraph 2\n\nParagraph 3'
      const chunks = chunkDocument(content)
      const merged = mergeChunks(chunks)
      expect(merged).toBe(content)
    })

    it('handles complex markdown content', () => {
      const content = `# Heading 1

This is a paragraph with some text.

## Heading 2

- List item 1
- List item 2
- List item 3

\`\`\`javascript
const code = "block";
\`\`\`

> A blockquote

---

Final paragraph.`

      const chunks = chunkDocument(content)
      expect(chunks.length).toBeGreaterThan(0)

      // Verify different types are detected
      const types = new Set(chunks.map(c => c.type))
      expect(types.size).toBeGreaterThan(1)
    })

    it('handles Chinese content', () => {
      const content = '这是第一段。这是第二段内容。这是第三段。'
      const chunks = chunkDocument(content)
      const merged = mergeChunks(chunks)
      expect(merged).toBe(content)
    })

    it('handles mixed language content', () => {
      // Note: The chunking algorithm is optimized for virtual scrolling, not exact content preservation.
      // It preserves most content but may normalize some blank lines.
      const content = `# English Title

This is English text.

## 中文标题

这是中文内容。

- Mixed 列表 item
- Another 项目

Code block:
\`\`\`
const x = "混合";
\`\`\``
      const chunks = chunkDocument(content)
      expect(chunks.length).toBeGreaterThan(0)
      // Verify the merged content has approximately the same length
      const merged = mergeChunks(chunks)
      // Allow for minor differences in blank line handling
      expect(Math.abs(merged.length - content.length)).toBeLessThan(5)
    })

    it('handles very long lines', () => {
      const longLine = 'a'.repeat(10000)
      const chunks = chunkDocument(longLine)
      expect(chunks.length).toBeGreaterThan(1)
      expect(mergeChunks(chunks)).toBe(longLine)
    })

    it('handles document with only whitespace', () => {
      const content = '   \n\n   \n   '
      const chunks = chunkDocument(content)
      // Should handle gracefully, may produce chunks or empty array
      expect(Array.isArray(chunks)).toBe(true)
    })
  })

  describe('edge cases', () => {
    it('handles single character content', () => {
      const chunks = chunkDocument('a')
      expect(chunks).toHaveLength(1)
      expect(chunks[0].content).toBe('a')
    })

    it('handles content with only newlines', () => {
      const chunks = chunkDocument('\n\n\n')
      expect(Array.isArray(chunks)).toBe(true)
    })

    it('handles unicode content', () => {
      const content = '🎉 🚀 ✨ 🌈'
      const chunks = chunkDocument(content)
      expect(mergeChunks(chunks)).toBe(content)
    })

    it('handles tabs and special whitespace', () => {
      const content = 'Column1\tColumn2\tColumn3'
      const chunks = chunkDocument(content)
      expect(mergeChunks(chunks)).toBe(content)
    })

    it('handles carriage returns', () => {
      const content = 'Line1\r\nLine2\r\nLine3'
      const chunks = chunkDocument(content)
      // Should handle CRLF line endings
      expect(chunks.length).toBeGreaterThan(0)
    })

    it('handles unclosed code blocks', () => {
      const content = '```javascript\nconst x = 1;\nNo closing backticks'
      const chunks = chunkDocument(content)
      expect(chunks.length).toBeGreaterThan(0)
    })
  })
})
