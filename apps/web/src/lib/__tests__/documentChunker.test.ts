import { describe, it, expect } from 'vitest'
import { countWords } from '../documentChunker'

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
