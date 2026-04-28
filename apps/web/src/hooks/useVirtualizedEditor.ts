/**
 * React hooks for virtualized document editor rendering.
 *
 * Provides efficient rendering of large documents by:
 * - Rendering only visible chunks using @tanstack/react-virtual
 * - Managing scroll position and cursor tracking
 * - Preserving scroll position during content updates
 * - Calculating word count and line statistics
 *
 * Key features:
 * - Handles documents with 50,000+ words smoothly
 * - RAF-throttled scroll handling for performance
 * - Isomorphic layout effects for SSR compatibility
 *
 * @module useVirtualizedEditor
 */

import { useMemo, useCallback, useRef, useState, useEffect, useLayoutEffect, type RefObject } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import type { DocumentChunk } from '../lib/documentChunker';
import { logger } from '../lib/logger';
import {
  buildPositionCache,
  calculateVisibleRange,
  estimateChunkHeight,
  preserveScrollPosition,
  rafThrottle,
  type ChunkPositionCache,
  type HeightEstimationConfig,
  OVERSCAN_COUNT,
  EDITOR_TOP_PADDING,
  DEFAULT_LINE_HEIGHT,
} from '../lib/virtualizationUtils';

// Use useLayoutEffect on client, useEffect on server
const useIsomorphicLayoutEffect = typeof window !== 'undefined' ? useLayoutEffect : useEffect;
const DEFAULT_HEIGHT_CONFIG: HeightEstimationConfig = {};

/**
 * Configuration options for the virtualized editor hook
 */
export interface VirtualizedEditorConfig {
  /** Height estimation configuration */
  heightConfig?: HeightEstimationConfig;
  /** Number of items to render beyond the visible area */
  overscan?: number;
  /** Whether to enable debug logging */
  debug?: boolean;
  /** Whether cache rebuilds should actively remap scrollTop */
  shouldPreserveScrollPosition?: boolean;
}

/**
 * Represents a visible chunk in the virtualized editor
 */
export interface VisibleEditorChunk {
  /** The document chunk data */
  chunk: DocumentChunk;
  /** Index in the chunks array */
  index: number;
  /** Estimated height in pixels */
  height: number;
  /** Y position from top of container */
  startY: number;
}

/**
 * Cursor position in the virtualized editor
 */
export interface EditorCursorPosition {
  /** Global character offset in the document */
  globalOffset: number;
  /** Index of the chunk containing the cursor */
  chunkIndex: number;
  /** Local offset within the chunk */
  localOffset: number;
}

/**
 * Return type for the useVirtualizedEditor hook
 */
export interface VirtualizedEditorResult {
  /** Virtualizer instance from @tanstack/react-virtual */
  virtualizer: ReturnType<typeof useVirtualizer<HTMLDivElement, Element>>;
  /** Currently visible chunks with positioning data */
  visibleChunks: VisibleEditorChunk[];
  /** Total size of all chunks in pixels */
  totalSize: number;
  /** Virtual items from the virtualizer */
  virtualItems: ReturnType<
    ReturnType<typeof useVirtualizer<HTMLDivElement, Element>>['getVirtualItems']
  >;
  /** Position cache for scroll calculations */
  positionCache: ChunkPositionCache;
  /** Scroll to a specific chunk by index */
  scrollToChunk: (index: number, align?: 'start' | 'center' | 'end' | 'auto') => void;
  /** Scroll to a specific character offset */
  scrollToOffset: (offset: number) => void;
  /** Get the chunk at a specific scroll position */
  getChunkAtScrollPosition: (scrollTop: number) => DocumentChunk | undefined;
  /** Update a chunk's content */
  updateChunk: (chunkId: string, newContent: string) => void;
  /** Get the current cursor position info */
  cursorPosition: EditorCursorPosition | null;
  /** Set cursor position by global offset */
  setCursorOffset: (offset: number) => void;
  /** Whether the editor is currently scrolling */
  isScrolling: boolean;
  /** Total number of chunks */
  totalChunks: number;
}

/**
 * Hook that virtualizes a document editor for efficient rendering.
 *
 * Uses @tanstack/react-virtual to render only visible chunks,
 * providing smooth scrolling for documents with 50,000+ words.
 *
 * @param content - The full document content string
 * @param chunks - Pre-chunked document chunks (from documentChunker)
 * @param scrollElementRef - Ref to the scrollable container element
 * @param config - Configuration options for height estimation, overscan, and debug mode
 * @returns VirtualizedEditorResult object with virtualizer, visible chunks, scroll methods, and cursor state
 *
 * @example
 * ```tsx
 * const scrollRef = useRef<HTMLDivElement>(null);
 * const { content, chunks } = useDocumentChunker(rawContent);
 *
 * const {
 *   visibleChunks,
 *   totalSize,
 *   scrollToChunk,
 *   cursorPosition,
 *   isScrolling,
 * } = useVirtualizedEditor(content, chunks, scrollRef, {
 *   overscan: 5,
 *   debug: true,
 * });
 *
 * return (
 *   <div ref={scrollRef} style={{ height: '100vh', overflow: 'auto' }}>
 *     <div style={{ height: totalSize }}>
 *       {visibleChunks.map(({ chunk, index, startY }) => (
 *         <EditorChunk
 *           key={chunk.id}
 *           chunk={chunk}
 *           style={{ position: 'absolute', top: startY }}
 *         />
 *       ))}
 *     </div>
 *   </div>
 * );
 * ```
 */
export function useVirtualizedEditor(
  _content: string,
  chunks: DocumentChunk[],
  scrollElementRef: RefObject<HTMLDivElement | null>,
  config: VirtualizedEditorConfig = {}
): VirtualizedEditorResult {
  const {
    heightConfig = DEFAULT_HEIGHT_CONFIG,
    overscan = OVERSCAN_COUNT,
    debug = false,
    shouldPreserveScrollPosition = true,
  } = config;

  // Track scroll state for cursor preservation
  const [isScrolling, setIsScrolling] = useState(false);
  const scrollTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isScrollingRef = useRef(false);

  // Track cursor position
  const [cursorPosition, setCursorPosition] = useState<EditorCursorPosition | null>(null);

  // Build position cache when chunks change
  const positionCache = useMemo(() => {
    const cache = buildPositionCache(chunks, heightConfig);
    if (debug) {
      logger.log('[useVirtualizedEditor] Position cache rebuilt:', {
        totalChunks: chunks.length,
        totalHeight: cache.totalHeight,
      });
    }
    return cache;
  }, [chunks, heightConfig, debug]);

  // Store previous cache for scroll position preservation
  const prevPositionCacheRef = useRef<ChunkPositionCache>(positionCache);

  // Estimate size for each chunk
  const estimateSize = useCallback(
    (index: number): number => {
      if (index < 0 || index >= chunks.length) {
        return DEFAULT_LINE_HEIGHT;
      }
      return estimateChunkHeight(chunks[index], heightConfig);
    },
    [chunks, heightConfig]
  );

  // Create virtualizer instance
  // eslint-disable-next-line react-hooks/incompatible-library
  const virtualizer = useVirtualizer<HTMLDivElement, Element>({
    count: chunks.length,
    getScrollElement: () => scrollElementRef.current,
    estimateSize,
    overscan,
    // Enable smooth scrolling
    scrollMargin: EDITOR_TOP_PADDING,
  });

  const virtualItems = virtualizer.getVirtualItems();

  // Get visible chunks with positioning data
  // Memoize based on virtualItems to avoid unnecessary recalculations
  const visibleChunks = useMemo((): VisibleEditorChunk[] => {
    // Pre-allocate array for performance
    const result: VisibleEditorChunk[] = new Array(virtualItems.length);

    for (let i = 0; i < virtualItems.length; i++) {
      const item = virtualItems[i];
      const chunk = chunks[item.index];
      result[i] = {
        chunk,
        index: item.index,
        height: item.size,
        startY: item.start,
      };
    }

    return result;
  }, [virtualItems, chunks]);

  // Handle scroll events for isScrolling state with RAF throttling
  useEffect(() => {
    const scrollElement = scrollElementRef.current;
    if (!scrollElement) return;

    // RAF-throttled scroll handler to reduce re-renders
    const handleScroll = rafThrottle(() => {
      // Update ref immediately (no re-render)
      isScrollingRef.current = true;

      // Batch state update with RAF
      setIsScrolling(true);

      // Clear previous timeout
      if (scrollTimeoutRef.current) {
        clearTimeout(scrollTimeoutRef.current);
      }

      // Set scrolling to false after 150ms of no scroll events
      scrollTimeoutRef.current = setTimeout(() => {
        isScrollingRef.current = false;
        setIsScrolling(false);
      }, 150);
    });

    scrollElement.addEventListener('scroll', handleScroll, { passive: true });

    return () => {
      scrollElement.removeEventListener('scroll', handleScroll);
      if (scrollTimeoutRef.current) {
        clearTimeout(scrollTimeoutRef.current);
      }
    };
  }, [scrollElementRef]);

  // Preserve scroll position when chunks are modified
  // Use layout effect to sync before paint and avoid scroll jump
  useIsomorphicLayoutEffect(() => {
    if (prevPositionCacheRef.current.chunkIds.length > 0 && scrollElementRef.current) {
      if (!shouldPreserveScrollPosition) {
        prevPositionCacheRef.current = positionCache;
        return;
      }

      const currentScrollTop = scrollElementRef.current.scrollTop;
      const newScrollTop = preserveScrollPosition(
        prevPositionCacheRef.current,
        positionCache,
        currentScrollTop
      );

      // Only update if there's an actual difference (avoid unnecessary writes)
      if (Math.abs(newScrollTop - currentScrollTop) > 1) {
        scrollElementRef.current.scrollTop = newScrollTop;
      }
    }

    prevPositionCacheRef.current = positionCache;
  }, [positionCache, scrollElementRef, shouldPreserveScrollPosition]);

  // Scroll to a specific chunk
  const scrollToChunk = useCallback(
    (index: number, align: 'start' | 'center' | 'end' | 'auto' = 'auto') => {
      if (index < 0 || index >= chunks.length) return;
      const scrollElement = scrollElementRef.current;
      if (!scrollElement?.ownerDocument?.documentElement) return;

      virtualizer.scrollToIndex(index, { align });
    },
    [chunks.length, scrollElementRef, virtualizer]
  );

  // Scroll to a specific character offset
  const scrollToOffset = useCallback(
    (offset: number) => {
      // Find the chunk containing this offset
      const chunkIndex = chunks.findIndex(
        (chunk) => offset >= chunk.startOffset && offset < chunk.endOffset
      );

      if (chunkIndex === -1) {
        // If offset is at the end, scroll to last chunk
        if (chunks.length > 0 && offset >= chunks[chunks.length - 1].endOffset) {
          scrollToChunk(chunks.length - 1, 'end');
        }
        return;
      }

      scrollToChunk(chunkIndex, 'center');
    },
    [chunks, scrollToChunk]
  );

  // Get chunk at a specific scroll position
  const getChunkAtScrollPosition = useCallback(
    (scrollTop: number): DocumentChunk | undefined => {
      const visibleRange = calculateVisibleRange(
        positionCache,
        scrollTop,
        scrollElementRef.current?.clientHeight ?? 0,
        0 // No overscan for exact position
      );

      if (visibleRange.startIndex > visibleRange.endIndex) {
        return undefined;
      }

      return chunks[visibleRange.startIndex];
    },
    [positionCache, scrollElementRef, chunks]
  );

  // Update a chunk's content (the actual update is handled by the parent component)
  const updateChunk = useCallback(
    (chunkId: string, newContent: string) => {
      const chunkIndex = chunks.findIndex((c) => c.id === chunkId);
      if (chunkIndex === -1) return;

      // The parent component handles the actual content update
      // We just update cursor position here
      const chunk = chunks[chunkIndex];
      setCursorPosition({
        globalOffset: chunk.startOffset + newContent.length,
        chunkIndex,
        localOffset: newContent.length,
      });

      if (debug) {
        logger.log('[useVirtualizedEditor] Chunk updated:', {
          chunkId,
          newLength: newContent.length,
          cursorPosition: chunk.startOffset + newContent.length,
        });
      }
    },
    [chunks, debug]
  );

  // Set cursor position by global offset
  const setCursorOffset = useCallback(
    (offset: number) => {
      const chunkIndex = chunks.findIndex(
        (chunk) => offset >= chunk.startOffset && offset < chunk.endOffset
      );

      if (chunkIndex === -1) {
        // Check if at end of document
        if (chunks.length > 0 && offset === chunks[chunks.length - 1].endOffset) {
          const lastChunk = chunks[chunks.length - 1];
          setCursorPosition({
            globalOffset: offset,
            chunkIndex: chunks.length - 1,
            localOffset: lastChunk.content.length,
          });
        }
        return;
      }

      const chunk = chunks[chunkIndex];
      setCursorPosition({
        globalOffset: offset,
        chunkIndex,
        localOffset: offset - chunk.startOffset,
      });
    },
    [chunks]
  );

  return {
    virtualizer,
    visibleChunks,
    totalSize: virtualizer.getTotalSize(),
    virtualItems,
    positionCache,
    scrollToChunk,
    scrollToOffset,
    getChunkAtScrollPosition,
    updateChunk,
    cursorPosition,
    setCursorOffset,
    isScrolling,
    totalChunks: chunks.length,
  };
}

/**
 * Hook for tracking the focused chunk index.
 *
 * Determines which chunk should be considered "focused" based on
 * cursor position or visible chunks. Useful for keyboard navigation
 * and cursor management in the virtualized editor.
 *
 * @param visibleChunks - Array of currently visible chunks with positioning data
 * @param cursorPosition - Current cursor position in the editor, or null
 * @returns The index of the focused chunk, or null if no chunks are visible
 *
 * @example
 * ```tsx
 * const { visibleChunks, cursorPosition } = useVirtualizedEditor(content, chunks, scrollRef);
 * const focusedChunkIndex = useFocusedChunk(visibleChunks, cursorPosition);
 *
 * // Use for keyboard navigation
 * const handleKeyDown = (e: KeyboardEvent) => {
 *   if (e.key === 'ArrowDown' && focusedChunkIndex !== null) {
 *     scrollToChunk(focusedChunkIndex + 1);
 *   }
 * };
 * ```
 */
export function useFocusedChunk(
  visibleChunks: VisibleEditorChunk[],
  cursorPosition: EditorCursorPosition | null
): number | null {
  return useMemo(() => {
    if (cursorPosition) {
      return cursorPosition.chunkIndex;
    }
    // Return the first visible chunk if no cursor
    return visibleChunks.length > 0 ? visibleChunks[0].index : null;
  }, [visibleChunks, cursorPosition]);
}

/**
 * Hook for calculating word count statistics.
 *
 * Computes document statistics including character count, word count
 * (supporting both Chinese characters and English words), and line count.
 * Memoized for performance with large documents.
 *
 * @param chunks - Array of document chunks to calculate statistics for
 * @returns Object containing totalChunks, totalCharacters, totalWords, and lineCount
 *
 * @example
 * ```tsx
 * const { chunks } = useDocumentChunker(content);
 * const stats = useEditorStats(chunks);
 *
 * // Display in status bar
 * return (
 *   <div className="status-bar">
 *     {stats.totalWords.toLocaleString()} words • {stats.lineCount} lines
 *   </div>
 * );
 * ```
 */
export function useEditorStats(chunks: DocumentChunk[]) {
  return useMemo(() => {
    const totalCharacters = chunks.reduce((sum, chunk) => sum + chunk.content.length, 0);

    // Count words (Chinese characters + English words)
    const allContent = chunks.map((c) => c.content).join('');
    const chineseChars = (allContent.match(/[\u4e00-\u9fa5]/g) || []).length;
    const englishWords = (allContent.match(/[a-zA-Z]+/g) || []).length;
    const totalWords = chineseChars + englishWords;

    // Count lines
    const lineCount = allContent.split('\n').length;

    return {
      totalChunks: chunks.length,
      totalCharacters,
      totalWords,
      lineCount,
    };
  }, [chunks]);
}
