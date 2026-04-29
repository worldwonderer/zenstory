/**
 * Word counting utility for mixed Chinese/English text.
 */

/**
 * Count words in a document, handling both Chinese and English text.
 *
 * Counting methodology:
 * - Chinese characters (Unicode range U+4E00 to U+9FA5): each character = 1 word
 * - English words (sequences of A-Z, a-z): each sequence = 1 word
 * - Numbers and symbols are not counted
 *
 * This hybrid approach provides accurate counts for mixed-language content.
 *
 * @param content - Document content to count words in
 * @returns Total word count
 *
 * @example
 * ```ts
 * countWords('Hello world'); // 2
 * countWords('你好世界'); // 4
 * countWords('Hello 你好 world 世界'); // 4 (2 English + 4 Chinese)
 * countWords(''); // 0
 * ```
 */
export function countWords(content: string): number {
  const chineseChars = (content.match(/[\u4e00-\u9fa5]/g) || []).length;
  const englishWords = (content.match(/[a-zA-Z]+/g) || []).length;
  return chineseChars + englishWords;
}
