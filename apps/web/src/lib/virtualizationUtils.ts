/**
 * Virtualization utilities for efficient rendering of large documents.
 *
 * This module provides helper functions for implementing virtual scrolling
 * in the document editor. It works in conjunction with documentChunker.ts
 * to enable smooth scrolling and editing of documents with 50,000+ words
 * while maintaining a memory footprint under 500MB.
 *
 * Architecture:
 * - Documents are split into chunks via documentChunker.ts
 * - This module estimates chunk heights for virtualizer positioning
 * - Visible range calculations determine which chunks to render
 * - Scroll position management preserves context during navigation
 * - Chunk merging/splitting handles dynamic content during edits
 *
 * The virtualization strategy:
 * 1. Build position cache with estimated heights for all chunks
 * 2. Calculate visible range based on scroll position and viewport
 * 3. Only render chunks within visible range (+ overscan)
 * 4. Maintain scroll position stability during content updates
 *
 * Usage:
 * ```ts
 * import {
 *   buildPositionCache,
 *   calculateVisibleRange,
 *   getVisibleChunks,
 *   estimateChunkHeight
 * } from '../lib/virtualizationUtils';
 * import type { DocumentChunk } from '../lib/documentChunker';
 *
 * // Build cache for efficient calculations
 * const cache = buildPositionCache(chunks);
 *
 * // Calculate which chunks are visible
 * const visibleRange = calculateVisibleRange(cache, scrollTop, viewportHeight);
 *
 * // Get chunks to render
 * const visibleChunks = getVisibleChunks(chunks, visibleRange);
 *
 * // Estimate individual chunk height
 * const height = estimateChunkHeight(chunk, { lineHeight: 24, charsPerLine: 80 });
 * ```
 *
 * @module lib/virtualizationUtils
 * @see documentChunker - For document chunking logic
 */

import type { DocumentChunk, ChunkType } from './documentChunker';

// ============================================================================
// Constants
// ============================================================================

/** Default line height in pixels */
export const DEFAULT_LINE_HEIGHT = 24;

/** Default characters per line for height estimation */
export const DEFAULT_CHARS_PER_LINE = 80;

/** Number of chunks to render beyond the visible area (overscan) */
export const OVERSCAN_COUNT = 5;

/** Minimum chunk height in pixels */
export const MIN_CHUNK_HEIGHT = 32;

/** Padding at the top of the editor in pixels */
export const EDITOR_TOP_PADDING = 16;

/** Padding at the bottom of the editor in pixels */
export const EDITOR_BOTTOM_PADDING = 16;

/** Threshold for considering chunks as "near" each other (in chunks) */
export const PROXIMITY_THRESHOLD = 3;

// ============================================================================
// Height Estimation
// ============================================================================

/**
 * Height multipliers for different chunk types.
 * Some content types need more vertical space due to styling.
 */
const CHUNK_TYPE_HEIGHT_MULTIPLIERS: Record<ChunkType, number> = {
  paragraph: 1.0,
  heading: 1.5, // Headings have larger font
  code: 1.2, // Code blocks have padding/margin
  list: 1.0,
  blockquote: 1.1, // Blockquotes have padding
  separator: 0.5, // Separators are thin
  empty: 0.5, // Empty lines are minimal
};

/**
 * Configuration options for chunk height estimation.
 *
 * These settings control how the virtualizer calculates the estimated
 * height of each chunk, which affects scroll position accuracy and
 * the smoothness of the virtual scrolling experience.
 *
 * @interface HeightEstimationConfig
 */
export interface HeightEstimationConfig {
  /** Line height in pixels. Default: 24 */
  lineHeight?: number;
  /** Characters per line for wrapping calculations. Default: 80 */
  charsPerLine?: number;
  /** Custom multipliers for chunk types to adjust for different content styles */
  typeMultipliers?: Partial<Record<ChunkType, number>>;
}

/**
 * Estimate the height of a single chunk in pixels.
 *
 * Uses content length, type, and configuration to calculate an estimated
 * height for virtualizer positioning. The estimate considers:
 * - Number of explicit line breaks in content
 * - Content wrapping based on charsPerLine setting
 * - Type-specific multipliers (headings are taller, separators are shorter)
 *
 * @param chunk - The document chunk to estimate height for
 * @param config - Height estimation configuration options
 * @returns Estimated height in pixels, guaranteed to be at least MIN_CHUNK_HEIGHT
 *
 * @example
 * ```ts
 * // Basic height estimation
 * const height = estimateChunkHeight(chunk);
 *
 * // With custom configuration
 * const height = estimateChunkHeight(chunk, {
 *   lineHeight: 28,
 *   charsPerLine: 100,
 *   typeMultipliers: { heading: 2.0 } // Make headings even taller
 * });
 * ```
 */
export function estimateChunkHeight(
  chunk: DocumentChunk,
  config: HeightEstimationConfig = {}
): number {
  const {
    lineHeight = DEFAULT_LINE_HEIGHT,
    charsPerLine = DEFAULT_CHARS_PER_LINE,
    typeMultipliers = {},
  } = config;

  // Merge default and custom multipliers
  const multipliers = { ...CHUNK_TYPE_HEIGHT_MULTIPLIERS, ...typeMultipliers };
  const typeMultiplier = multipliers[chunk.type] ?? 1.0;

  // Handle empty chunks
  if (chunk.type === 'empty' || chunk.content.length === 0) {
    return Math.max(MIN_CHUNK_HEIGHT, lineHeight * typeMultiplier);
  }

  // Calculate number of lines
  const explicitLineBreaks = chunk.content.split('\n').length;
  const contentLines = Math.ceil(chunk.content.length / charsPerLine);
  const lineCount = Math.max(explicitLineBreaks, contentLines);

  // Calculate estimated height
  const estimatedHeight = lineCount * lineHeight * typeMultiplier;

  // Ensure minimum height
  return Math.max(MIN_CHUNK_HEIGHT, Math.round(estimatedHeight));
}

/**
 * Estimate heights for all chunks and return a map.
 *
 * Convenience function that iterates through all chunks and creates
 * a lookup map for quick height access during virtualization.
 *
 * @param chunks - Array of document chunks to estimate heights for
 * @param config - Height estimation configuration options
 * @returns Map of chunk ID to estimated height in pixels
 *
 * @example
 * ```ts
 * const heightMap = estimateAllChunkHeights(chunks);
 * const specificHeight = heightMap.get('chunk-123'); // number | undefined
 * ```
 */
export function estimateAllChunkHeights(
  chunks: DocumentChunk[],
  config: HeightEstimationConfig = {}
): Map<string, number> {
  const heightMap = new Map<string, number>();

  for (const chunk of chunks) {
    heightMap.set(chunk.id, estimateChunkHeight(chunk, config));
  }

  return heightMap;
}

/**
 * Calculate the total estimated height of all chunks combined.
 *
 * Sums up all chunk heights plus editor top and bottom padding.
 * This is used to set the total scrollable height for the virtualizer.
 *
 * @param chunks - Array of document chunks
 * @param config - Height estimation configuration options
 * @returns Total estimated document height in pixels including padding
 *
 * @example
 * ```ts
 * const totalHeight = calculateTotalHeight(chunks);
 * // Use this to set the scroll container's total scrollable height
 * scrollContainer.style.height = `${totalHeight}px`;
 * ```
 */
export function calculateTotalHeight(
  chunks: DocumentChunk[],
  config: HeightEstimationConfig = {}
): number {
  const heights = estimateAllChunkHeights(chunks, config);
  let total = EDITOR_TOP_PADDING + EDITOR_BOTTOM_PADDING;

  for (const height of Array.from(heights.values())) {
    total += height;
  }

  return total;
}

// ============================================================================
// Visible Range Calculation
// ============================================================================

/**
 * Represents a range of chunks that should be rendered.
 *
 * This range includes chunks within the viewport plus any overscan
 * chunks on either side for smoother scrolling experience.
 *
 * @interface VisibleRange
 */
export interface VisibleRange {
  /** Index of the first visible chunk (0-based) */
  startIndex: number;
  /** Index of the last visible chunk, inclusive (0-based) */
  endIndex: number;
  /** Pixel offset before the first visible chunk for positioning */
  startOffset: number;
  /** Pixel offset after the last visible chunk for positioning */
  endOffset: number;
}

/**
 * Cached chunk positions for efficient visible range calculation.
 *
 * This cache stores pre-calculated positions and heights for all chunks,
 * enabling O(log n) binary search lookups for visible range calculations.
 * Should be rebuilt whenever chunks change (content edits, structure changes).
 *
 * @interface ChunkPositionCache
 */
export interface ChunkPositionCache {
  /** Chunk IDs in document order */
  chunkIds: string[];
  /** Cumulative Y offsets for each chunk from document top */
  offsets: number[];
  /** Individual heights for each chunk */
  heights: number[];
  /** Total document height including padding */
  totalHeight: number;
}

/**
 * Build a position cache for efficient visible range calculations.
 *
 * Creates a cache structure that stores chunk positions and heights,
 * enabling O(log n) lookups during scroll events. Should be called
 * whenever chunks are modified (content changes, additions, deletions).
 *
 * Performance: O(n) where n is the number of chunks.
 *
 * @param chunks - Array of document chunks to cache positions for
 * @param config - Height estimation configuration options
 * @returns Position cache for use with calculateVisibleRange and scroll functions
 *
 * @example
 * ```ts
 * // Build cache after loading document
 * const cache = buildPositionCache(documentChunks);
 *
 * // Rebuild cache after edits
 * const updatedChunks = [...chunks, newChunk];
 * const newCache = buildPositionCache(updatedChunks);
 * ```
 */
export function buildPositionCache(
  chunks: DocumentChunk[],
  config: HeightEstimationConfig = {}
): ChunkPositionCache {
  const chunkIds: string[] = [];
  const offsets: number[] = [];
  const heights: number[] = [];

  let currentOffset = EDITOR_TOP_PADDING;

  for (const chunk of chunks) {
    chunkIds.push(chunk.id);
    offsets.push(currentOffset);
    const height = estimateChunkHeight(chunk, config);
    heights.push(height);
    currentOffset += height;
  }

  return {
    chunkIds,
    offsets,
    heights,
    totalHeight: currentOffset + EDITOR_BOTTOM_PADDING,
  };
}

/**
 * Calculate which chunks are visible in the viewport.
 *
 * Uses binary search for efficient O(log n) lookup. Includes overscan
 * chunks on either side of the visible area for smoother scrolling
 * experience by pre-rendering chunks that will soon be visible.
 *
 * Performance: O(log n) where n is the number of chunks.
 *
 * @param cache - Position cache from buildPositionCache
 * @param scrollTop - Current scroll position in pixels from top
 * @param viewportHeight - Height of the visible viewport in pixels
 * @param overscan - Number of extra chunks to include on each side. Default: OVERSCAN_COUNT (5)
 * @returns Visible range with start/end indices and pixel offsets
 *
 * @example
 * ```ts
 * // On scroll event
 * const handleScroll = () => {
 *   const range = calculateVisibleRange(
 *     cache,
 *     container.scrollTop,
 *     container.clientHeight
 *   );
 *   setVisibleChunks(chunks.slice(range.startIndex, range.endIndex + 1));
 * };
 * ```
 */
export function calculateVisibleRange(
  cache: ChunkPositionCache,
  scrollTop: number,
  viewportHeight: number,
  overscan: number = OVERSCAN_COUNT
): VisibleRange {
  const { offsets, heights, chunkIds } = cache;

  if (chunkIds.length === 0) {
    return {
      startIndex: 0,
      endIndex: -1,
      startOffset: 0,
      endOffset: 0,
    };
  }

  // Adjust scroll position for top padding
  const adjustedScrollTop = Math.max(0, scrollTop - EDITOR_TOP_PADDING);
  const scrollBottom = adjustedScrollTop + viewportHeight;

  // Binary search for first potentially visible chunk
  let left = 0;
  let right = chunkIds.length - 1;

  while (left < right) {
    const mid = Math.floor((left + right) / 2);
    const chunkBottom = offsets[mid] + heights[mid] - EDITOR_TOP_PADDING;

    if (chunkBottom < adjustedScrollTop) {
      left = mid + 1;
    } else {
      right = mid;
    }
  }

  const startIndex = Math.max(0, left - overscan);

  // Binary search for last potentially visible chunk
  left = 0;
  right = chunkIds.length - 1;

  while (left < right) {
    const mid = Math.ceil((left + right) / 2);
    const chunkTop = offsets[mid] - EDITOR_TOP_PADDING;

    if (chunkTop > scrollBottom) {
      right = mid - 1;
    } else {
      left = mid;
    }
  }

  const endIndex = Math.min(chunkIds.length - 1, left + overscan);

  return {
    startIndex,
    endIndex,
    startOffset: startIndex < chunkIds.length ? offsets[startIndex] : 0,
    endOffset:
      endIndex >= 0 && endIndex < chunkIds.length
        ? offsets[endIndex] + heights[endIndex]
        : 0,
  };
}

/**
 * Get the chunks that are currently visible based on a calculated range.
 *
 * Simple slice operation that extracts the chunks within the visible range.
 * This is the final step after calculating the visible range.
 *
 * @param chunks - All document chunks in order
 * @param visibleRange - Calculated visible range from calculateVisibleRange
 * @returns Array of chunks that should be rendered
 *
 * @example
 * ```ts
 * const range = calculateVisibleRange(cache, scrollTop, viewportHeight);
 * const chunksToRender = getVisibleChunks(allChunks, range);
 * // Render chunksToRender in your virtualized list
 * ```
 */
export function getVisibleChunks(
  chunks: DocumentChunk[],
  visibleRange: VisibleRange
): DocumentChunk[] {
  if (visibleRange.startIndex > visibleRange.endIndex) {
    return [];
  }

  return chunks.slice(visibleRange.startIndex, visibleRange.endIndex + 1);
}

// ============================================================================
// Scroll Position Management
// ============================================================================

/**
 * Find the chunk index at a given scroll position.
 *
 * Linear search through the cache to find which chunk contains
 * the given scroll position. Used for cursor positioning and
 * scroll position preservation.
 *
 * @param cache - Position cache from buildPositionCache
 * @param scrollTop - Scroll position in pixels from top
 * @returns Chunk index (0-based) or -1 if position is before first chunk
 *
 * @example
 * ```ts
 * // Find which chunk the user is currently viewing
 * const currentChunkIndex = findChunkIndexAtScrollPosition(cache, scrollTop);
 * if (currentChunkIndex >= 0) {
 *   highlightChunk(chunks[currentChunkIndex]);
 * }
 * ```
 */
export function findChunkIndexAtScrollPosition(
  cache: ChunkPositionCache,
  scrollTop: number
): number {
  const { offsets, heights } = cache;

  if (offsets.length === 0) {
    return -1;
  }

  const adjustedScrollTop = scrollTop + EDITOR_TOP_PADDING;

  for (let i = 0; i < offsets.length; i++) {
    if (adjustedScrollTop >= offsets[i] && adjustedScrollTop < offsets[i] + heights[i]) {
      return i;
    }
  }

  // If past the end, return the last index
  if (adjustedScrollTop >= offsets[offsets.length - 1] + heights[heights.length - 1]) {
    return offsets.length - 1;
  }

  return -1;
}

/**
 * Calculate the scroll position to bring a specific chunk into view.
 *
 * Supports multiple alignment modes for different UX needs:
 * - 'start': Align chunk top to viewport top
 * - 'end': Align chunk bottom to viewport bottom
 * - 'center': Center the chunk in the viewport
 * - 'auto': Default to 'start' alignment
 *
 * @param cache - Position cache from buildPositionCache
 * @param chunkIndex - Index of the chunk to scroll to (0-based)
 * @param align - Alignment mode: 'start', 'center', 'end', or 'auto'. Default: 'auto'
 * @param viewportHeight - Height of the viewport (required for 'center' and 'end' alignment)
 * @returns Scroll position in pixels to set container.scrollTop
 *
 * @example
 * ```ts
 * // Scroll to chunk, aligning it to the top
 * const scrollTop = calculateScrollToPosition(cache, targetIndex, 'start');
 * container.scrollTo({ top: scrollTop, behavior: 'smooth' });
 *
 * // Center a chunk in the viewport
 * const scrollTop = calculateScrollToPosition(
 *   cache,
 *   targetIndex,
 *   'center',
 *   container.clientHeight
 * );
 * ```
 */
export function calculateScrollToPosition(
  cache: ChunkPositionCache,
  chunkIndex: number,
  align: 'start' | 'center' | 'end' | 'auto' = 'auto',
  viewportHeight?: number
): number {
  const { offsets, heights } = cache;

  if (chunkIndex < 0 || chunkIndex >= offsets.length) {
    return 0;
  }

  const chunkTop = offsets[chunkIndex];
  const chunkBottom = chunkTop + heights[chunkIndex];
  const chunkHeight = heights[chunkIndex];

  switch (align) {
    case 'start':
      return chunkTop - EDITOR_TOP_PADDING;

    case 'end':
      if (viewportHeight) {
        return chunkBottom - viewportHeight + EDITOR_TOP_PADDING;
      }
      return chunkTop - EDITOR_TOP_PADDING;

    case 'center':
      if (viewportHeight) {
        return chunkTop - (viewportHeight - chunkHeight) / 2 - EDITOR_TOP_PADDING;
      }
      return chunkTop - EDITOR_TOP_PADDING;

    case 'auto':
    default:
      // Auto: only scroll if necessary
      return chunkTop - EDITOR_TOP_PADDING;
  }
}

/**
 * Calculate scroll position to bring a specific offset within a chunk into view.
 *
 * Useful for precise positioning within a chunk, such as scrolling to
 * a specific line or character position. Supports both ratio-based
 * (0-1) and pixel-based offsets.
 *
 * @param cache - Position cache from buildPositionCache
 * @param chunkIndex - Index of the chunk (0-based)
 * @param localOffset - Offset within the chunk: either ratio (0-1) or pixels
 * @param isRatio - Whether localOffset is a ratio (0-1) or pixel offset. Default: true
 * @returns Scroll position in pixels
 *
 * @example
 * ```ts
 * // Scroll to 50% of the chunk
 * const scrollTop = calculateScrollToOffset(cache, chunkIndex, 0.5, true);
 *
 * // Scroll to 100 pixels within the chunk
 * const scrollTop = calculateScrollToOffset(cache, chunkIndex, 100, false);
 * ```
 */
export function calculateScrollToOffset(
  cache: ChunkPositionCache,
  chunkIndex: number,
  localOffset: number,
  isRatio: boolean = true
): number {
  const { offsets, heights } = cache;

  if (chunkIndex < 0 || chunkIndex >= offsets.length) {
    return 0;
  }

  const chunkTop = offsets[chunkIndex];
  const chunkHeight = heights[chunkIndex];

  const pixelOffset = isRatio ? localOffset * chunkHeight : localOffset;

  return chunkTop + pixelOffset - EDITOR_TOP_PADDING;
}

/**
 * Preserve scroll position when chunks are modified.
 *
 * When chunks are added, removed, or resized due to edits, this function
 * calculates the new scroll position that maintains the user's view of
 * the same content. Essential for preventing jarring jumps during typing.
 *
 * @param oldCache - Position cache before modification
 * @param newCache - Position cache after modification
 * @param currentScrollTop - Current scroll position in pixels
 * @returns New scroll position to maintain relative position
 *
 * @example
 * ```ts
 * // After editing content that changes chunk structure
 * const oldCache = currentCache;
 * const newCache = buildPositionCache(updatedChunks);
 * const newScrollTop = preserveScrollPosition(oldCache, newCache, container.scrollTop);
 * container.scrollTop = newScrollTop;
 * ```
 */
export function preserveScrollPosition(
  oldCache: ChunkPositionCache,
  newCache: ChunkPositionCache,
  currentScrollTop: number
): number {
  // Find the chunk at the current scroll position
  const oldChunkIndex = findChunkIndexAtScrollPosition(oldCache, currentScrollTop);

  if (oldChunkIndex === -1 || oldChunkIndex >= oldCache.offsets.length) {
    return currentScrollTop;
  }

  const oldChunkId = oldCache.chunkIds[oldChunkIndex];
  const mappedChunkIndex = oldChunkId ? newCache.chunkIds.indexOf(oldChunkId) : -1;
  const targetChunkIndex =
    mappedChunkIndex !== -1 ? mappedChunkIndex : Math.min(oldChunkIndex, newCache.offsets.length - 1);

  if (targetChunkIndex < 0 || targetChunkIndex >= newCache.offsets.length) {
    return currentScrollTop;
  }

  // Keep relative offset within the same chunk to avoid upward scroll rebound
  const oldChunkTop = oldCache.offsets[oldChunkIndex] - EDITOR_TOP_PADDING;
  const offsetWithinChunk = currentScrollTop - oldChunkTop;
  const newChunkTop = newCache.offsets[targetChunkIndex] - EDITOR_TOP_PADDING;

  return Math.max(0, newChunkTop + offsetWithinChunk);
}

// ============================================================================
// Chunk Merging and Splitting During Edits
// ============================================================================

/**
 * Result of a chunk edit operation (merge, split, or rebalance).
 *
 * Contains the updated chunks array and metadata about what changes
 * were made, useful for updating UI state and maintaining cursor position.
 *
 * @interface ChunkEditResult
 */
export interface ChunkEditResult {
  /** Updated chunks array after the operation */
  chunks: DocumentChunk[];
  /** Index of the primary affected chunk */
  primaryIndex: number;
  /** Whether chunks were merged during this operation */
  merged: boolean;
  /** Whether chunks were split during this operation */
  split: boolean;
  /** Indices of removed chunks (empty if no removals) */
  removedIndices: number[];
  /** Indices of newly created chunks (empty if no additions) */
  addedIndices: number[];
}

/**
 * Configuration options for chunk merging and splitting operations.
 *
 * These thresholds control when chunks should be combined or divided
 * to maintain optimal chunk sizes for virtualization performance.
 *
 * @interface ChunkEditConfig
 */
export interface ChunkEditConfig {
  /** Minimum characters per chunk. Chunks smaller than this may be merged. Default: 100 */
  minChunkSize?: number;
  /** Maximum characters per chunk. Chunks larger than this will be split. Default: 1500 */
  maxChunkSize?: number;
  /** Target characters per chunk when splitting. Default: 750 */
  targetChunkSize?: number;
}

const DEFAULT_EDIT_CONFIG: Required<ChunkEditConfig> = {
  minChunkSize: 100,
  maxChunkSize: 1500,
  targetChunkSize: 750,
};

/**
 * Check if a chunk should be merged with its neighbors (too small).
 *
 * Chunks below the minChunkSize threshold should be merged to avoid
 * having too many tiny chunks, which would reduce virtualization efficiency.
 * Separator chunks are never merged as they represent intentional boundaries.
 *
 * @param chunk - The chunk to check
 * @param config - Edit configuration with size thresholds
 * @returns True if the chunk should be merged, false otherwise
 *
 * @example
 * ```ts
 * if (shouldMergeChunk(chunk, { minChunkSize: 100 })) {
 *   // Consider merging this chunk with neighbors
 * }
 * ```
 */
export function shouldMergeChunk(
  chunk: DocumentChunk,
  config: ChunkEditConfig = {}
): boolean {
  const { minChunkSize } = { ...DEFAULT_EDIT_CONFIG, ...config };
  return chunk.content.length < minChunkSize && chunk.type !== 'separator';
}

/**
 * Check if a chunk should be split (too large).
 *
 * Chunks above the maxChunkSize threshold should be split to maintain
 * manageable chunk sizes for rendering and to improve scroll accuracy.
 *
 * @param chunk - The chunk to check
 * @param config - Edit configuration with size thresholds
 * @returns True if the chunk should be split, false otherwise
 *
 * @example
 * ```ts
 * if (shouldSplitChunk(chunk, { maxChunkSize: 1500 })) {
 *   // Split this chunk into smaller pieces
 * }
 * ```
 */
export function shouldSplitChunk(
  chunk: DocumentChunk,
  config: ChunkEditConfig = {}
): boolean {
  const { maxChunkSize } = { ...DEFAULT_EDIT_CONFIG, ...config };
  return chunk.content.length > maxChunkSize;
}

/**
 * Merge a chunk with its neighbors if it's too small.
 *
 * Attempts to merge the specified chunk with adjacent chunks, prioritizing
 * the previous chunk. Only merges if the combined content doesn't exceed
 * maxChunkSize. Returns the original chunks if no merge is possible.
 *
 * @param chunks - All document chunks in order
 * @param chunkIndex - Index of the chunk to potentially merge (0-based)
 * @param config - Edit configuration with size thresholds
 * @returns Edit result with updated chunks and merge metadata
 *
 * @example
 * ```ts
 * const result = mergeChunkIfNeeded(chunks, 5);
 * if (result.merged) {
 *   console.log(`Merged chunk into index ${result.primaryIndex}`);
 *   setChunks(result.chunks);
 * }
 * ```
 */
export function mergeChunkIfNeeded(
  chunks: DocumentChunk[],
  chunkIndex: number,
  config: ChunkEditConfig = {}
): ChunkEditResult {
  const opts = { ...DEFAULT_EDIT_CONFIG, ...config };
  const result: ChunkEditResult = {
    chunks: [...chunks],
    primaryIndex: chunkIndex,
    merged: false,
    split: false,
    removedIndices: [],
    addedIndices: [],
  };

  if (chunkIndex < 0 || chunkIndex >= chunks.length) {
    return result;
  }

  const chunk = chunks[chunkIndex];

  if (!shouldMergeChunk(chunk, opts)) {
    return result;
  }

  // Try to merge with previous chunk first
  if (chunkIndex > 0) {
    const prevChunk = chunks[chunkIndex - 1];
    const mergedContent = prevChunk.content + '\n' + chunk.content;

    if (mergedContent.length <= opts.maxChunkSize) {
      // Create merged chunk
      const mergedChunk: DocumentChunk = {
        ...prevChunk,
        content: mergedContent,
        endOffset: chunk.endOffset,
        estimatedHeight: estimateChunkHeight(
          { ...chunk, content: mergedContent } as DocumentChunk,
          {}
        ),
        isPartial: false,
      };

      result.chunks = [
        ...chunks.slice(0, chunkIndex - 1),
        mergedChunk,
        ...chunks.slice(chunkIndex + 1),
      ];
      result.merged = true;
      result.removedIndices = [chunkIndex];
      result.primaryIndex = chunkIndex - 1;

      return result;
    }
  }

  // Try to merge with next chunk
  if (chunkIndex < chunks.length - 1) {
    const nextChunk = chunks[chunkIndex + 1];
    const mergedContent = chunk.content + '\n' + nextChunk.content;

    if (mergedContent.length <= opts.maxChunkSize) {
      const mergedChunk: DocumentChunk = {
        ...chunk,
        content: mergedContent,
        endOffset: nextChunk.endOffset,
        estimatedHeight: estimateChunkHeight(
          { ...chunk, content: mergedContent } as DocumentChunk,
          {}
        ),
        isPartial: false,
      };

      result.chunks = [
        ...chunks.slice(0, chunkIndex),
        mergedChunk,
        ...chunks.slice(chunkIndex + 2),
      ];
      result.merged = true;
      result.removedIndices = [chunkIndex + 1];
      result.primaryIndex = chunkIndex;

      return result;
    }
  }

  return result;
}

/**
 * Split a chunk if it's too large.
 *
 * Finds natural break points (double newlines, single newlines, spaces)
 * near the target chunk size to create well-formed smaller chunks.
 * Falls back to hard splits at target size if no natural breaks exist.
 *
 * @param chunks - All document chunks in order
 * @param chunkIndex - Index of the chunk to potentially split (0-based)
 * @param config - Edit configuration with size thresholds
 * @returns Edit result with updated chunks and split metadata
 *
 * @example
 * ```ts
 * const result = splitChunkIfNeeded(chunks, 3);
 * if (result.split) {
 *   console.log(`Created ${result.addedIndices.length} new chunks`);
 *   setChunks(result.chunks);
 * }
 * ```
 */
export function splitChunkIfNeeded(
  chunks: DocumentChunk[],
  chunkIndex: number,
  config: ChunkEditConfig = {}
): ChunkEditResult {
  const opts = { ...DEFAULT_EDIT_CONFIG, ...config };
  const result: ChunkEditResult = {
    chunks: [...chunks],
    primaryIndex: chunkIndex,
    merged: false,
    split: false,
    removedIndices: [],
    addedIndices: [],
  };

  if (chunkIndex < 0 || chunkIndex >= chunks.length) {
    return result;
  }

  const chunk = chunks[chunkIndex];

  if (!shouldSplitChunk(chunk, opts)) {
    return result;
  }

  // Find good split points
  const content = chunk.content;
  const splitPoints: number[] = [];

  // Look for paragraph breaks first
  let searchPos = opts.targetChunkSize;
  while (searchPos < content.length - opts.minChunkSize) {
    // Look for newline near the target
    const searchStart = Math.max(0, searchPos - 50);
    const searchEnd = Math.min(content.length, searchPos + 50);
    const searchText = content.slice(searchStart, searchEnd);

    // Priority: double newline > single newline > space
    let splitPoint = -1;

    const doubleNewline = searchText.indexOf('\n\n');
    if (doubleNewline !== -1) {
      splitPoint = searchStart + doubleNewline + 2;
    } else {
      const singleNewline = searchText.indexOf('\n');
      if (singleNewline !== -1) {
        splitPoint = searchStart + singleNewline + 1;
      } else {
        const space = searchText.lastIndexOf(' ');
        if (space !== -1) {
          splitPoint = searchStart + space + 1;
        }
      }
    }

    if (splitPoint > 0) {
      splitPoints.push(splitPoint);
      searchPos = splitPoint + opts.targetChunkSize;
    } else {
      // Force split at target size
      splitPoints.push(searchPos);
      searchPos += opts.targetChunkSize;
    }
  }

  if (splitPoints.length === 0) {
    return result;
  }

  // Create split chunks
  const newChunks: DocumentChunk[] = [];
  let prevPoint = 0;

  for (let i = 0; i <= splitPoints.length; i++) {
    const endPoint = i === splitPoints.length ? content.length : splitPoints[i];
    const chunkContent = content.slice(prevPoint, endPoint);

    // Import detectChunkType from documentChunker - for now, use 'paragraph' as default
    const newChunk: DocumentChunk = {
      id: `chunk-${Date.now()}-${i}`,
      content: chunkContent,
      startOffset: chunk.startOffset + prevPoint,
      endOffset: chunk.startOffset + endPoint,
      type: chunk.type,
      estimatedHeight: estimateChunkHeight(
        { ...chunk, content: chunkContent } as DocumentChunk,
        {}
      ),
      isPartial: true,
      lineNumber: chunk.lineNumber + (content.slice(0, prevPoint).match(/\n/g) || []).length,
    };

    newChunks.push(newChunk);
    prevPoint = endPoint;
  }

  // Replace the original chunk with split chunks
  result.chunks = [
    ...chunks.slice(0, chunkIndex),
    ...newChunks,
    ...chunks.slice(chunkIndex + 1),
  ];
  result.split = true;
  result.removedIndices = [chunkIndex];
  result.addedIndices = Array.from(
    { length: newChunks.length },
    (_, i) => chunkIndex + i
  );
  result.primaryIndex = chunkIndex;

  return result;
}

/**
 * Rebalance chunks around an edited chunk.
 *
 * Comprehensive function that handles both splitting large chunks and
 * merging small chunks. Also checks neighboring chunks that may have
 * become too small after the edit. Call this after any content modification.
 *
 * Algorithm:
 * 1. First attempt to split if the edited chunk is too large
 * 2. If no split, attempt to merge if too small
 * 3. Check previous and next chunks for needed merges
 *
 * @param chunks - All document chunks in order
 * @param editedChunkIndex - Index of the edited chunk (0-based)
 * @param config - Edit configuration with size thresholds
 * @returns Edit result with balanced chunks
 *
 * @example
 * ```ts
 * // After user edits content in a chunk
 * const result = rebalanceChunks(chunks, editedIndex);
 * if (result.merged || result.split) {
 *   updateChunks(result.chunks);
 *   // Update cursor position using result.primaryIndex
 * }
 * ```
 */
export function rebalanceChunks(
  chunks: DocumentChunk[],
  editedChunkIndex: number,
  config: ChunkEditConfig = {}
): ChunkEditResult {
  // First try to split if needed
  let result = splitChunkIfNeeded(chunks, editedChunkIndex, config);

  // If no split happened, try to merge if needed
  if (!result.split) {
    result = mergeChunkIfNeeded(chunks, editedChunkIndex, config);
  }

  // Check neighbors for rebalancing
  if (!result.merged && !result.split) {
    // Check previous chunk
    if (editedChunkIndex > 0) {
      const prevResult = mergeChunkIfNeeded(result.chunks, editedChunkIndex - 1, config);
      if (prevResult.merged) {
        result = prevResult;
      }
    }

    // Check next chunk
    if (editedChunkIndex < result.chunks.length - 1) {
      const nextResult = mergeChunkIfNeeded(result.chunks, editedChunkIndex + 1, config);
      if (nextResult.merged) {
        result = nextResult;
      }
    }
  }

  return result;
}

// ============================================================================
// Cursor Position Utilities
// ============================================================================

/**
 * Information about cursor position in a virtualized document context.
 *
 * Provides all the information needed to position and render a cursor
 * in a virtualized document, including which chunk it's in, the local
 * offset within that chunk, the global offset, and pixel position.
 *
 * @interface VirtualizedCursorPosition
 */
export interface VirtualizedCursorPosition {
  /** Index of the chunk containing the cursor (0-based) */
  chunkIndex: number;
  /** Character offset within the chunk (0-based) */
  localOffset: number;
  /** Global character offset in the document (0-based) */
  globalOffset: number;
  /** Y position in pixels from document top */
  pixelY: number;
}

/**
 * Map a global character offset to virtualized cursor position.
 *
 * Converts a document-wide character offset to chunk-local position
 * information, including pixel Y position for cursor rendering.
 * Used for positioning cursor after navigation or search operations.
 *
 * @param chunks - All document chunks in order
 * @param cache - Position cache from buildPositionCache
 * @param globalOffset - Global character offset in the document (0-based)
 * @returns Virtualized cursor position info, or null if offset is invalid
 *
 * @example
 * ```ts
 * // Convert search match position to cursor position
 * const cursorPos = mapOffsetToVirtualizedCursor(chunks, cache, matchOffset);
 * if (cursorPos) {
 *   // Scroll to make cursor visible
 *   scrollToPosition(cursorPos.pixelY);
 *   // Set cursor in the editor
 *   setCursorPosition(cursorPos.chunkIndex, cursorPos.localOffset);
 * }
 * ```
 */
export function mapOffsetToVirtualizedCursor(
  chunks: DocumentChunk[],
  cache: ChunkPositionCache,
  globalOffset: number
): VirtualizedCursorPosition | null {
  // Find the chunk containing this offset
  const chunkIndex = chunks.findIndex(
    (chunk) => globalOffset >= chunk.startOffset && globalOffset < chunk.endOffset
  );

  if (chunkIndex === -1) {
    // Check if offset is at the very end
    if (chunks.length > 0 && globalOffset === chunks[chunks.length - 1].endOffset) {
      const lastChunk = chunks[chunks.length - 1];
      return {
        chunkIndex: chunks.length - 1,
        localOffset: lastChunk.content.length,
        globalOffset,
        pixelY: cache.offsets[chunkIndex] + cache.heights[chunkIndex],
      };
    }
    return null;
  }

  const chunk = chunks[chunkIndex];
  const localOffset = globalOffset - chunk.startOffset;

  // Calculate Y position within the chunk
  const chunkTop = cache.offsets[chunkIndex];
  const lineHeight = DEFAULT_LINE_HEIGHT;
  const linesBeforeCursor = chunk.content.slice(0, localOffset).split('\n').length - 1;
  const pixelWithinChunk = linesBeforeCursor * lineHeight;

  return {
    chunkIndex,
    localOffset,
    globalOffset,
    pixelY: chunkTop + pixelWithinChunk,
  };
}

/**
 * Map a pixel Y position to a chunk and approximate offset.
 *
 * Converts a pixel position (e.g., from a mouse click) to chunk and
 * character offset information. The offset is approximated based on
 * relative position within the chunk, suitable for click-to-position.
 *
 * @param chunks - All document chunks in order
 * @param cache - Position cache from buildPositionCache
 * @param pixelY - Y position in pixels from document top
 * @returns Virtualized cursor position info, or null if position is invalid
 *
 * @example
 * ```ts
 * // Handle click in virtualized editor
 * const handleClick = (event: MouseEvent) => {
 *   const pixelY = event.clientY - container.getBoundingClientRect().top + container.scrollTop;
 *   const cursorPos = mapPixelToVirtualizedCursor(chunks, cache, pixelY);
 *   if (cursorPos) {
 *     setCursorAtPosition(cursorPos.globalOffset);
 *   }
 * };
 * ```
 */
export function mapPixelToVirtualizedCursor(
  chunks: DocumentChunk[],
  cache: ChunkPositionCache,
  pixelY: number
): VirtualizedCursorPosition | null {
  const chunkIndex = findChunkIndexAtScrollPosition(cache, pixelY);

  if (chunkIndex === -1) {
    return null;
  }

  const chunk = chunks[chunkIndex];
  const chunkTop = cache.offsets[chunkIndex];
  const chunkHeight = cache.heights[chunkIndex];

  // Approximate offset based on position within chunk
  const relativeY = Math.max(0, pixelY - chunkTop);
  const relativeRatio = Math.min(1, relativeY / chunkHeight);
  const approximateOffset = Math.round(chunk.content.length * relativeRatio);

  return {
    chunkIndex,
    localOffset: approximateOffset,
    globalOffset: chunk.startOffset + approximateOffset,
    pixelY,
  };
}

// ============================================================================
// Performance Utilities
// ============================================================================

/**
 * Debounce a function call.
 *
 * Delays function execution until after the specified delay has passed
 * without another call. Useful for rate-limiting scroll event handlers
 * and other high-frequency events.
 *
 * @typeParam T - Function type to debounce
 * @param fn - The function to debounce
 * @param delay - Delay in milliseconds
 * @returns Debounced function that delays execution
 *
 * @example
 * ```ts
 * // Debounce scroll handler to run 100ms after last scroll
 * const debouncedScroll = debounce(handleScroll, 100);
 * container.addEventListener('scroll', debouncedScroll);
 * ```
 */
export function debounce<T extends (...args: unknown[]) => unknown>(
  fn: T,
  delay: number
): (...args: Parameters<T>) => void {
  let timeoutId: ReturnType<typeof setTimeout> | null = null;

  return (...args: Parameters<T>) => {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }
    timeoutId = setTimeout(() => {
      fn(...args);
      timeoutId = null;
    }, delay);
  };
}

/**
 * Throttle a function call using requestAnimationFrame.
 *
 * Limits function execution to once per animation frame, ensuring
 * smooth updates without overwhelming the browser. Ideal for scroll
 * handlers that update visual state continuously.
 *
 * @typeParam T - Function type to throttle
 * @param fn - The function to throttle
 * @returns Throttled function that runs at most once per frame
 *
 * @example
 * ```ts
 * // Throttle scroll handler for smooth visual updates
 * const throttledScroll = rafThrottle((scrollTop) => {
 *   updateVisibleChunks(scrollTop);
 * });
 * container.addEventListener('scroll', () => throttledScroll(container.scrollTop));
 * ```
 */
export function rafThrottle<T extends (...args: unknown[]) => unknown>(
  fn: T
): (...args: Parameters<T>) => void {
  let rafId: number | null = null;
  let lastArgs: Parameters<T> | null = null;

  return (...args: Parameters<T>) => {
    lastArgs = args;

    if (rafId === null) {
      rafId = requestAnimationFrame(() => {
        if (lastArgs) {
          fn(...lastArgs);
        }
        rafId = null;
      });
    }
  };
}

/**
 * Check if the browser supports passive event listeners.
 *
 * Passive listeners improve scroll performance by indicating the handler
 * won't call preventDefault(), allowing the browser to scroll immediately.
 *
 * @returns True if passive event listeners are supported
 *
 * @example
 * ```ts
 * if (supportsPassiveEvents()) {
 *   element.addEventListener('touchstart', handler, { passive: true });
 * }
 * ```
 */
export function supportsPassiveEvents(): boolean {
  let supported = false;
  try {
    const options = {
      get passive() {
        supported = true;
        return false;
      },
    };
    window.addEventListener('test', () => {}, options);
    window.removeEventListener('test', () => {});
  } catch {
    supported = false;
  }
  return supported;
}

/**
 * Get the optimal scroll listener options for the current browser.
 *
 * Returns passive: true if supported, which improves scroll performance
 * by telling the browser the handler won't call preventDefault().
 *
 * @returns Event listener options object for optimal scroll performance
 *
 * @example
 * ```ts
 * // Use optimal options for scroll listeners
 * element.addEventListener('scroll', handleScroll, getScrollListenerOptions());
 * ```
 */
export function getScrollListenerOptions(): AddEventListenerOptions {
  return supportsPassiveEvents() ? { passive: true } : ({} as AddEventListenerOptions);
}
