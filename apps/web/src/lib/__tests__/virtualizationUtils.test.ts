import { describe, it, expect } from 'vitest'
import {
  preserveScrollPosition,
  EDITOR_TOP_PADDING,
  type ChunkPositionCache,
} from '../virtualizationUtils'

function createCache(
  chunkIds: string[],
  offsets: number[],
  heights: number[]
): ChunkPositionCache {
  const lastIndex = offsets.length - 1
  const totalHeight =
    lastIndex >= 0 ? offsets[lastIndex] + heights[lastIndex] + EDITOR_TOP_PADDING : EDITOR_TOP_PADDING * 2

  return {
    chunkIds,
    offsets,
    heights,
    totalHeight,
  }
}

describe('virtualizationUtils.preserveScrollPosition', () => {
  it('keeps relative offset within the current chunk when heights change', () => {
    const oldCache = createCache(
      ['a', 'b'],
      [EDITOR_TOP_PADDING, EDITOR_TOP_PADDING + 100],
      [100, 100]
    )
    const newCache = createCache(
      ['a', 'b'],
      [EDITOR_TOP_PADDING, EDITOR_TOP_PADDING + 180],
      [180, 100]
    )

    const currentScrollTop = 140 // 40px inside chunk "b" (old top = 100)

    expect(preserveScrollPosition(oldCache, newCache, currentScrollTop)).toBe(220)
  })

  it('tracks the same chunk by id when indices shift', () => {
    const oldCache = createCache(
      ['a', 'b'],
      [EDITOR_TOP_PADDING, EDITOR_TOP_PADDING + 100],
      [100, 100]
    )
    const newCache = createCache(
      ['x', 'a', 'b'],
      [EDITOR_TOP_PADDING, EDITOR_TOP_PADDING + 60, EDITOR_TOP_PADDING + 160],
      [60, 100, 100]
    )

    const currentScrollTop = 140 // 40px inside chunk "b" (old top = 100)

    expect(preserveScrollPosition(oldCache, newCache, currentScrollTop)).toBe(200)
  })
})
