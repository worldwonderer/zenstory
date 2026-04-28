import { useState, useEffect, useRef, useCallback, useMemo, useReducer, memo, useLayoutEffect } from "react";
import { useTranslation } from "react-i18next";
import { Save, Clock, Check, History, Sparkles, Loader2 } from "lucide-react";
import type { FileUpdateVersionIntent } from "../lib/api";
import { writingStatsApi } from "../lib/writingStatsApi";
import { FileVersionHistory } from "./FileVersionHistory";
import { DiffReviewSplitView } from "./DiffReviewSplitView";
import { DiffToolbar } from "./DiffToolbar";
import { SelectionToolbar } from "./SelectionToolbar";
import { useTextQuote } from "../contexts/TextQuoteContext";
import { useVirtualizedEditor, useEditorStats } from "../hooks/useVirtualizedEditor";
import {
  chunkDocument,
  updateChunkContent,
  mergeChunks,
  chunkDocumentInitial,
  continueChunking,
  isLargeDocument,
  countWords,
  type DocumentChunk,
} from "../lib/documentChunker";
import { logMemoryUsage } from "../lib/memoryMonitor";
import type { DiffReviewState } from "../types";
import { getLocaleCode } from "../lib/i18n-helpers";
import { logger } from "../lib/logger";
import { toast } from "../lib/toast";
import { preserveSelectionWhitespace } from "../lib/naturalPolish";
import { naturalPolishApi } from "../lib/naturalPolishApi";

// ============================================================================
// Auto-save Performance Constants for Large Documents
// ============================================================================

/**
 * Word count threshold for adaptive save behavior.
 * Documents above this threshold get optimized save handling.
 */
const LARGE_DOC_THRESHOLD = 20000;

/**
 * Base debounce time for auto-save (ms).
 * For small documents: 3000ms
 * For large documents: 5000ms (adaptive)
 */
const BASE_SAVE_DEBOUNCE = 3000;
const LARGE_DOC_SAVE_DEBOUNCE = 5000;

/**
 * Minimum interval between version creations for large documents.
 * This prevents creating too many versions during rapid editing.
 */
const VERSION_THROTTLE_MS = 60000; // 1 minute

/**
 * Minimum content change (characters) to trigger version creation.
 * For large docs, we don't want to create versions for tiny changes.
 */
const MIN_VERSION_CHANGE_CHARS = 500;

// Use useLayoutEffect on client, useEffect on server
const useIsomorphicLayoutEffect = typeof window !== 'undefined' ? useLayoutEffect : useEffect;

const isNearBottom = (el: HTMLElement, thresholdPx = 32) => {
  return el.scrollHeight - el.scrollTop - el.clientHeight < thresholdPx;
};

const VIRTUALIZED_EDITOR_MIN_TEXTAREA_HEIGHT_PX = 48;

const restoreContainerScrollTop = (container: HTMLElement | null, prevScrollTop: number | null) => {
  if (!container || prevScrollTop === null) return;

  const restore = () => {
    const maxTop = Math.max(0, container.scrollHeight - container.clientHeight);
    container.scrollTop = Math.min(prevScrollTop, maxTop);
  };

  restore();
  requestAnimationFrame(restore);
};

const restoreTextareaViewportOffset = (
  container: HTMLElement | null,
  textarea: HTMLElement | null,
  prevOffsetTop: number | null
) => {
  if (!container || !textarea || prevOffsetTop === null) return;

  const restore = () => {
    const containerRect = container.getBoundingClientRect();
    const textareaRect = textarea.getBoundingClientRect();
    const currentOffsetTop = textareaRect.top - containerRect.top;
    const adjustment = currentOffsetTop - prevOffsetTop;

    if (Math.abs(adjustment) <= 1) {
      return;
    }

    const maxTop = Math.max(0, container.scrollHeight - container.clientHeight);
    container.scrollTop = Math.min(maxTop, Math.max(0, container.scrollTop + adjustment));
  };

  restore();
  requestAnimationFrame(restore);
};

/**
 * Chunking state for progressive loading
 */
interface ChunkingState {
  chunks: DocumentChunk[];
  isChunking: boolean;
  progress: number;
  chunkedOffset: number;
  isComplete: boolean;
}

type ChunkingAction =
  | { type: 'INITIAL'; chunks: DocumentChunk[]; offset: number; isComplete: boolean }
  | { type: 'PROGRESS'; chunks: DocumentChunk[]; offset: number; progress: number; isComplete: boolean }
  | { type: 'RESET' }
  | { type: 'UPDATE_CHUNK'; chunkId: string; newContent: string };

/**
 * Reducer for managing progressive chunking state
 */
function chunkingReducer(state: ChunkingState, action: ChunkingAction): ChunkingState {
  switch (action.type) {
    case 'INITIAL':
      return {
        chunks: action.chunks,
        isChunking: !action.isComplete,
        progress: action.offset,
        chunkedOffset: action.offset,
        isComplete: action.isComplete,
      };
    case 'PROGRESS':
      return {
        chunks: action.chunks,
        isChunking: !action.isComplete,
        progress: action.progress,
        chunkedOffset: action.offset,
        isComplete: action.isComplete,
      };
    case 'RESET':
      return {
        chunks: [],
        isChunking: false,
        progress: 0,
        chunkedOffset: 0,
        isComplete: true,
      };
    case 'UPDATE_CHUNK':
      return {
        ...state,
        chunks: updateChunkContent(state.chunks, action.chunkId, action.newContent),
      };
    default:
      return state;
  }
}

// Polyfill for requestIdleCallback in browsers that don't support it
const requestIdleCallbackPolyfill = (
  callback: IdleRequestCallback
): number => {
  const start = Date.now();
  return window.setTimeout(() => {
    callback({
      didTimeout: false,
      timeRemaining: () => Math.max(0, 50 - (Date.now() - start)),
    });
  }, 1);
};

const cancelIdleCallbackPolyfill = (id: number) => {
  window.clearTimeout(id);
};

// Use native or polyfill
const ric = typeof window !== 'undefined' && 'requestIdleCallback' in window
  ? window.requestIdleCallback
  : requestIdleCallbackPolyfill;

const cic = typeof window !== 'undefined' && 'cancelIdleCallback' in window
  ? window.cancelIdleCallback
  : cancelIdleCallbackPolyfill;

/**
 * Props for the memoized ChunkRenderer component
 */
interface ChunkRendererProps {
  chunk: DocumentChunk;
  index: number;
  height: number;
  isStreaming: boolean;
  isLastChunk: boolean;
  readOnly: boolean;
  isFocused: boolean;
  onRegisterRef: (chunkId: string, el: HTMLTextAreaElement | null) => void;
  onContentChange: (chunkId: string, content: string) => void;
  onSelect: (chunkId: string, textarea: HTMLTextAreaElement) => void;
  onFocus: (chunkId: string) => void;
  onBlur: (chunkId: string) => void;
  onCompositionStart: (chunkId: string) => void;
  onCompositionEnd: () => void;
  placeholder: string;
}

/**
 * Memoized chunk renderer for optimal scroll performance.
 * Only re-renders when its specific props change.
 */
const ChunkRenderer = memo(function ChunkRenderer({
  chunk,
  index,
  height,
  isStreaming,
  isLastChunk,
  readOnly,
  isFocused,
  onRegisterRef,
  onContentChange,
  onSelect,
  onFocus,
  onBlur,
  onCompositionStart,
  onCompositionEnd,
  placeholder,
}: ChunkRendererProps) {
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const adjustTextareaHeight = useCallback((force = false) => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    const scrollContainer = textarea.closest('[data-editor-scroll-container="true"]') as HTMLElement | null;
    const prevScrollTop = scrollContainer ? scrollContainer.scrollTop : null;
    const currentHeightPx =
      Number.parseFloat(textarea.style.height || "0") ||
      Math.max(VIRTUALIZED_EDITOR_MIN_TEXTAREA_HEIGHT_PX, height);
    const isFocused = typeof document !== "undefined" && document.activeElement === textarea;

    let nextHeight = Math.max(
      VIRTUALIZED_EDITOR_MIN_TEXTAREA_HEIGHT_PX,
      height,
      textarea.scrollHeight
    );

    if (force || !isFocused) {
      const previousHeight = textarea.style.height;
      textarea.style.height = "0px";
      nextHeight = Math.max(
        VIRTUALIZED_EDITOR_MIN_TEXTAREA_HEIGHT_PX,
        height,
        textarea.scrollHeight
      );
      textarea.style.height = previousHeight;
    } else if (nextHeight < currentHeightPx) {
      nextHeight = currentHeightPx;
    }

    if (force || Math.abs(nextHeight - currentHeightPx) > 1) {
      textarea.style.height = `${nextHeight}px`;
    }

    if (isFocused) {
      restoreContainerScrollTop(scrollContainer, prevScrollTop);
    }
  }, [height]);

  useIsomorphicLayoutEffect(() => {
    adjustTextareaHeight(false);
  }, [chunk.content, height, adjustTextareaHeight]);

  return (
    <div
      data-index={index}
      data-chunk-id={chunk.id}
      className="chunk-container"
    >
      <textarea
        ref={(el) => {
          textareaRef.current = el;
          onRegisterRef(chunk.id, el);
        }}
        value={chunk.content}
        onChange={(e) => onContentChange(chunk.id, e.target.value)}
        onSelect={(e) => onSelect(chunk.id, e.target as HTMLTextAreaElement)}
        onMouseUp={(e) => onSelect(chunk.id, e.target as HTMLTextAreaElement)}
        onCompositionStart={() => onCompositionStart(chunk.id)}
        onCompositionEnd={onCompositionEnd}
        onFocus={() => onFocus(chunk.id)}
        onBlur={() => {
          adjustTextareaHeight(true);
          onBlur(chunk.id);
        }}
        disabled={readOnly || isStreaming}
        placeholder={index === 0 ? placeholder : ''}
        className={`w-full overflow-y-hidden bg-transparent text-[hsl(var(--text-primary))] placeholder-[hsl(var(--text-secondary))] outline-none border-none resize-none leading-relaxed text-base ${isStreaming ? 'cursor-default' : ''} ${isFocused ? 'ring-1 ring-[hsl(var(--accent-primary)/0.2)]' : ''}`}
        style={{
          minHeight: `${Math.max(VIRTUALIZED_EDITOR_MIN_TEXTAREA_HEIGHT_PX, height)}px`,
        }}
      />
      {/* Streaming cursor at the end of the last visible chunk */}
      {isStreaming && isLastChunk && chunk.content && (
        <span className="inline-block w-0.5 h-5 bg-[hsl(var(--accent-primary))] ml-0.5 animate-pulse" style={{ transform: 'translateY(-1px)' }} />
      )}
    </div>
  );
}, (prevProps, nextProps) => {
  // Custom comparison for optimal re-render prevention
  return (
    prevProps.chunk.id === nextProps.chunk.id &&
    prevProps.chunk.content === nextProps.chunk.content &&
    prevProps.height === nextProps.height &&
    prevProps.isFocused === nextProps.isFocused &&
    prevProps.isStreaming === nextProps.isStreaming &&
    prevProps.isLastChunk === nextProps.isLastChunk &&
    prevProps.readOnly === nextProps.readOnly
  );
});

/**
 * Represents cursor state within a chunk for preservation during re-render
 */
interface ChunkCursorState {
  /** Index of the chunk in the array (stable across re-renders with same content) */
  chunkIndex: number;
  /** Cursor position within the chunk content */
  selectionStart: number;
  selectionEnd: number;
  /** Direction of selection */
  selectionDirection: "forward" | "backward" | "none";
}

interface VirtualizedEditorProps {
  fileId?: string;
  projectId?: string;
  fileType?: string;
  fileTitle?: string;
  title: string;
  content: string;
  onTitleChange: (title: string) => void;
  onContentChange: (content: string) => void;
  onSave: (versionIntent?: FileUpdateVersionIntent) => Promise<void>;
  readOnly?: boolean;
  isStreaming?: boolean;
  // Diff review props
  diffReviewState?: DiffReviewState | null;
  onEnterDiffReview?: (fileId: string, originalContent: string, newContent: string) => void;
  onAcceptEdit?: (editId: string) => void;
  onRejectEdit?: (editId: string) => void;
  onResetEdit?: (editId: string) => void;
  onAcceptAllEdits?: () => void;
  onRejectAllEdits?: () => void;
  onFinishReview?: () => void;
}

export const VirtualizedEditor = ({
  fileId,
  projectId,
  fileType,
  fileTitle,
  title,
  content,
  onTitleChange,
  onContentChange,
  onSave,
  readOnly = false,
  isStreaming = false,
  // Diff review props
  diffReviewState,
  onEnterDiffReview,
  onAcceptEdit,
  onRejectEdit,
  onResetEdit,
  onAcceptAllEdits,
  onRejectAllEdits,
  onFinishReview,
}: VirtualizedEditorProps) => {
  const { t } = useTranslation(['editor']);
  const { addQuote } = useTextQuote();
  const [isSaving, setIsSaving] = useState(false);
  const [lastSaved, setLastSaved] = useState<Date | null>(null);
  const [isDirty, setIsDirty] = useState(false);
  const [showVersionHistory, setShowVersionHistory] = useState(false);
  // Selection toolbar state
  const [selectedText, setSelectedText] = useState("");
  const [selectionPosition, setSelectionPosition] = useState<{ x: number; y: number } | null>(null);
  const [selectionInfo, setSelectionInfo] = useState<{ chunkId: string; start: number; end: number } | null>(null);

  // Natural polish (de-AI tone) state
  const [isNaturalPolishRunning, setIsNaturalPolishRunning] = useState(false);
  const naturalPolishRunIdRef = useRef(0);
  const naturalPolishAbortRef = useRef<AbortController | null>(null);
  const naturalPolishBufferRef = useRef<string>("");
  const naturalPolishBaselineRef = useRef<{
    content: string;
    startOffset: number;
    endOffset: number;
    selection: string;
  } | null>(null);

  // Refs
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const chunkTextareaRefs = useRef<Map<string, HTMLTextAreaElement>>(new Map());
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const selectionTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastSavedContentRef = useRef<string>(content);
  const latestContentRef = useRef(content);
  const pendingBaselineSyncRef = useRef(false);
  const pendingLocalContentSyncRef = useRef<string | null>(null);
  const shouldAutoScrollRef = useRef(true);
  const isComposingRef = useRef(false);
  const focusedChunkIdRef = useRef<string | null>(null);
  const pendingViewportAnchorRef = useRef<{ chunkId: string; offsetTop: number } | null>(null);
  const handleSaveRef = useRef<() => Promise<void>>(async () => undefined);
  const latestFileIdRef = useRef<string | undefined>(fileId);

  // Auto-save optimization refs for large documents
  const lastVersionTimeRef = useRef<number>(Date.now());
  const preparedSaveContentRef = useRef<string | null>(null);
  const isPreparingSaveRef = useRef(false);

  // Cursor preservation state
  const [pendingCursorRestore, setPendingCursorRestore] = useState<ChunkCursorState | null>(null);
  const isUserEditingRef = useRef(false);
  const lastCursorStateRef = useRef<ChunkCursorState | null>(null);

  // Progressive chunking state
  const [chunkingState, dispatchChunking] = useReducer(chunkingReducer, {
    chunks: [],
    isChunking: false,
    progress: 0,
    chunkedOffset: 0,
    isComplete: false,
  });

  // Track content hash to detect actual content changes
  const contentHashRef = useRef<string>(content);
  const chunkingCompleteRef = useRef(chunkingState.isComplete);

  latestFileIdRef.current = fileId;
  const idleCallbackIdRef = useRef<number | null>(null);

  latestContentRef.current = content;
  chunkingCompleteRef.current = chunkingState.isComplete;

  // Compute document size for adaptive save behavior
  const documentWordCount = useMemo(() => countWords(content), [content]);
  const isLargeDoc = documentWordCount > LARGE_DOC_THRESHOLD;
  const saveDebounceTime = isLargeDoc ? LARGE_DOC_SAVE_DEBOUNCE : BASE_SAVE_DEBOUNCE;

  // Start lazy chunking when content changes significantly
  useEffect(() => {
    // Cancel any pending idle callback
    if (idleCallbackIdRef.current !== null) {
      cic(idleCallbackIdRef.current);
      idleCallbackIdRef.current = null;
    }

    if (pendingLocalContentSyncRef.current === content && chunkingCompleteRef.current) {
      contentHashRef.current = content;
      pendingLocalContentSyncRef.current = null;
      return;
    }
    pendingLocalContentSyncRef.current = null;

    // Check if content actually changed
    if (content === contentHashRef.current && chunkingCompleteRef.current) {
      return;
    }
    contentHashRef.current = content;

    // Determine if we should use lazy chunking
    const useLazyChunking = isLargeDocument(content);

    if (!useLazyChunking) {
      // For small documents, chunk everything at once
      const chunks = chunkDocument(content, {
        targetChunkSize: 750,
        minChunkSize: 100,
        maxChunkSize: 1500,
      });
      dispatchChunking({
        type: 'INITIAL',
        chunks,
        offset: content.length,
        isComplete: true,
      });
      return;
    }

    // For large documents, use lazy chunking
    // Step 1: Get initial chunks (for visible area)
    const initial = chunkDocumentInitial(content, {
      targetChunkSize: 750,
      minChunkSize: 100,
      maxChunkSize: 1500,
    });
    dispatchChunking({
      type: 'INITIAL',
      chunks: initial.chunks,
      offset: initial.chunkedUntil,
      isComplete: initial.isComplete,
    });

    // Step 2: Continue chunking in idle time if not complete
    if (!initial.isComplete) {
      const continueInIdle = (deadline: IdleDeadline) => {
        // Get current state from the ref to avoid stale closure
        let currentOffset = initial.chunkedUntil;
        let currentChunks = initial.chunks;

        const processBatch = () => {
          if (currentOffset >= content.length) {
            return;
          }

          // Use remaining time or at least 10ms
          const shouldYield = deadline.timeRemaining() < 5;

          if (shouldYield && !deadline.didTimeout) {
            // Schedule next batch
            idleCallbackIdRef.current = ric(continueInIdle, { timeout: 100 });
            return;
          }

          // Process a batch of content
          const result = continueChunking(
            content,
            currentOffset,
            currentChunks,
            {
              targetChunkSize: 750,
              minChunkSize: 100,
              maxChunkSize: 1500,
            },
            20000 // 20k chars per batch
          );

          currentChunks = result.chunks;
          currentOffset = result.newOffset;

          dispatchChunking({
            type: 'PROGRESS',
            chunks: result.chunks,
            offset: result.newOffset,
            progress: result.newOffset / content.length,
            isComplete: result.isComplete,
          });

          // Continue if not complete and we have time
          if (!result.isComplete && deadline.timeRemaining() > 5) {
            processBatch();
          } else if (!result.isComplete) {
            // Schedule next batch
            idleCallbackIdRef.current = ric(continueInIdle, { timeout: 100 });
          }
        };

        processBatch();
      };

      // Start idle processing
      idleCallbackIdRef.current = ric(continueInIdle, { timeout: 200 });
    }

    // Cleanup
    return () => {
      if (idleCallbackIdRef.current !== null) {
        cic(idleCallbackIdRef.current);
      }
    };
  }, [content]); // Only re-run when content changes

  // Get chunks from state
  const chunks = chunkingState.chunks;

  // Development-only memory logging for large documents
  useEffect(() => {
    if (import.meta.env.DEV && isLargeDoc && !chunkingState.isChunking && chunkingState.isComplete) {
      // Log memory usage after large document is fully loaded
      logMemoryUsage(`Large doc loaded (${documentWordCount} words, ${chunks.length} chunks)`);
    }
  }, [isLargeDoc, chunkingState.isChunking, chunkingState.isComplete, documentWordCount, chunks.length]);

  // Use the virtualized editor hook
  const {
    virtualizer,
    visibleChunks,
    totalSize,
  } = useVirtualizedEditor(content, chunks, scrollContainerRef, {
    overscan: 5,
    debug: false,
    shouldPreserveScrollPosition: !(isUserEditingRef.current || isComposingRef.current),
  });

  // Calculate editor stats
  const stats = useEditorStats(chunks);

  // Check if in diff review mode
  const isReviewMode = diffReviewState?.isReviewing && diffReviewState.fileId === fileId;

  // When leaving review mode (diffReviewState cleared), assume the reviewed changes were saved.
  // Sync local save baseline so "unsaved" status doesn't get stuck.
  const prevReviewModeRef = useRef(isReviewMode);
  useEffect(() => {
    const wasInReviewMode = prevReviewModeRef.current;
    prevReviewModeRef.current = isReviewMode;

    if (wasInReviewMode && !isReviewMode) {
      // If diffReviewState is still present, we likely switched files; don't sync.
      if (!diffReviewState) {
        lastSavedContentRef.current = content;
        setIsDirty(false);
        setLastSaved(new Date());
      }
    }
  }, [isReviewMode, diffReviewState, content]);

  // Handle content scroll with RAF throttling for 60fps
  const handleContentScroll = useCallback(() => {
    const el = scrollContainerRef.current;
    if (!el) return;

    // Use requestAnimationFrame for smooth scroll handling
    requestAnimationFrame(() => {
      shouldAutoScrollRef.current = isNearBottom(el);
    });
  }, []);

  // Handle chunk content change
  const handleChunkContentChange = useCallback(
    (chunkId: string, newChunkContent: string) => {
      // Find the chunk index before updating
      const chunkIndex = chunks.findIndex(c => c.id === chunkId);
      if (chunkIndex === -1) return;

      // Get the current cursor position from the textarea
      const textarea = chunkTextareaRefs.current.get(chunkId);
      if (textarea) {
        // Store cursor state for preservation after re-render
        lastCursorStateRef.current = {
          chunkIndex,
          selectionStart: textarea.selectionStart,
          selectionEnd: textarea.selectionEnd,
          selectionDirection: textarea.selectionDirection as "forward" | "backward" | "none",
        };
        setPendingCursorRestore(lastCursorStateRef.current);

        const scrollContainer = scrollContainerRef.current;
        if (scrollContainer) {
          const containerRect = scrollContainer.getBoundingClientRect();
          const textareaRect = textarea.getBoundingClientRect();
          pendingViewportAnchorRef.current = {
            chunkId,
            offsetTop: textareaRect.top - containerRect.top,
          };
        }
      }

      // Update chunks via reducer
      const updatedChunks = updateChunkContent(chunks, chunkId, newChunkContent);
      const mergedChunks = mergeChunks(updatedChunks);
      const suffixStart = chunkingState.isComplete
        ? content.length
        : Math.min(chunkingState.chunkedOffset, content.length);
      const suffix = suffixStart < content.length ? content.slice(suffixStart) : "";
      const newFullContent = `${mergedChunks}${suffix}`;

      // Dispatch update to reducer (this updates chunkingState.chunks)
      dispatchChunking({
        type: 'UPDATE_CHUNK',
        chunkId,
        newContent: newChunkContent,
      });

      // Invalidate prepared save content - it needs to be re-prepared
      preparedSaveContentRef.current = null;

      pendingLocalContentSyncRef.current = newFullContent;
      onContentChange(newFullContent);
      setIsDirty(true);
      focusedChunkIdRef.current = chunkId;
      isUserEditingRef.current = true;
    },
    [chunks, onContentChange, chunkingState.chunkedOffset, chunkingState.isComplete, content]
  );

  // Restore cursor position after chunks are updated
  // Use layout effect to sync before paint
  useIsomorphicLayoutEffect(() => {
    if (!pendingCursorRestore) return;

    // Find the textarea for the chunk at this index
    const chunk = chunks[pendingCursorRestore.chunkIndex];
    if (!chunk) return;

    const textarea = chunkTextareaRefs.current.get(chunk.id);
    if (!textarea) return;

    // Adjust cursor position if content length changed
    const maxPos = textarea.value.length;
    const newStart = Math.min(pendingCursorRestore.selectionStart, maxPos);
    const newEnd = Math.min(pendingCursorRestore.selectionEnd, maxPos);

    textarea.setSelectionRange(
      newStart,
      newEnd,
      pendingCursorRestore.selectionDirection
    );

    // Clear pending restore
    setPendingCursorRestore(null);
  }, [chunks, pendingCursorRestore]);

  useIsomorphicLayoutEffect(() => {
    const pendingViewportAnchor = pendingViewportAnchorRef.current;
    if (!pendingViewportAnchor) return;

    const scrollContainer = scrollContainerRef.current;
    const textarea = chunkTextareaRefs.current.get(pendingViewportAnchor.chunkId);
    if (!scrollContainer || !textarea) return;

    restoreTextareaViewportOffset(scrollContainer, textarea, pendingViewportAnchor.offsetTop);
    pendingViewportAnchorRef.current = null;
  }, [chunks]);

  // Clear editing state when user stops editing (blur or idle)
  useEffect(() => {
    // Clear editing state after 2 seconds of no changes
    const idleInterval = setInterval(() => {
      if (isUserEditingRef.current && !pendingCursorRestore) {
        isUserEditingRef.current = false;
      }
    }, 2000);

    return () => {
      clearInterval(idleInterval);
      isUserEditingRef.current = false;
    };
  }, [pendingCursorRestore]);

  // Handle selection within a chunk
  const handleChunkSelection = useCallback(
    (_chunkId: string, textarea: HTMLTextAreaElement) => {
      if (selectionTimeoutRef.current) {
        clearTimeout(selectionTimeoutRef.current);
      }

      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;
      const text = textarea.value.substring(start, end).trim();

      if (!text) {
        setSelectedText("");
        setSelectionPosition(null);
        setSelectionInfo(null);
        return;
      }

      // Keep a fast "selection exists" signal for action buttons.
      setSelectedText(text);
      setSelectionInfo({ chunkId: _chunkId, start, end });

      // Delay showing toolbar by 300ms
      selectionTimeoutRef.current = setTimeout(() => {
        // Calculate selection position using the textarea's bounding rect
        // and scroll position for accurate placement
        const rect = textarea.getBoundingClientRect();
        const scrollContainer = scrollContainerRef.current;

        // Calculate approximate vertical position of selection
        // This is a simplification - for perfect accuracy we'd need a mirror div
        // like in SimpleEditor, but this works well enough for chunk context
        const lineHeight = 24; // Approximate line height
        const charsPerLine = Math.floor(textarea.clientWidth / 8); // Approximate chars per line
        const startLine = Math.floor(start / charsPerLine);
        const selectionTopOffset = startLine * lineHeight;

        // Position relative to viewport
        const x = rect.left + rect.width / 2;
        const y = rect.top + selectionTopOffset - (scrollContainer?.scrollTop ?? 0) % lineHeight;

        setSelectionPosition({ x: Math.max(x, 100), y: Math.max(y, 50) }); // Ensure visible
      }, 300);
    },
    []
  );

  // Close selection toolbar
  const closeSelectionToolbar = useCallback(() => {
    setSelectionPosition(null);
  }, []);

  // Add quote from selection
  const handleAddQuote = useCallback(() => {
    if (!selectedText || !fileId) return;
    const displayTitle = fileTitle || title;
    addQuote(selectedText, fileId, displayTitle);
    closeSelectionToolbar();
  }, [selectedText, fileId, fileTitle, title, addQuote, closeSelectionToolbar]);

  const startNaturalPolish = useCallback(async () => {
    if (isNaturalPolishRunning) return;
    if (!projectId || !fileId) {
      toast.error(
        t("editor:naturalPolishMissingContext"),
      );
      return;
    }

    if (!selectionInfo) {
      toast.info(t("editor:naturalPolishNoSelection"));
      return;
    }

    const chunk = chunks.find((c) => c.id === selectionInfo.chunkId);
    if (!chunk) {
      toast.error(t("editor:naturalPolishFailed"));
      return;
    }

    const globalStart = chunk.startOffset + selectionInfo.start;
    const globalEnd = chunk.startOffset + selectionInfo.end;
    const baselineContent = latestContentRef.current;
    const selection = baselineContent.substring(globalStart, globalEnd);
    if (!selection.trim()) {
      toast.info(t("editor:naturalPolishNoSelection"));
      return;
    }

    naturalPolishBaselineRef.current = {
      content: baselineContent,
      startOffset: globalStart,
      endOffset: globalEnd,
      selection,
    };
    naturalPolishBufferRef.current = "";
    const runId = naturalPolishRunIdRef.current + 1;
    naturalPolishRunIdRef.current = runId;

    // Cancel any previous in-flight request (defensive)
    naturalPolishAbortRef.current?.abort();

    setIsNaturalPolishRunning(true);
    const controller = new AbortController();
    naturalPolishAbortRef.current = controller;

    try {
      const rewrittenRaw = await naturalPolishApi.naturalPolish(
        {
          projectId,
          fileId,
          fileType,
          selectedText: selection,
        },
        { signal: controller.signal },
      );

      if (naturalPolishRunIdRef.current !== runId) return;
      const baseline = naturalPolishBaselineRef.current;
      setIsNaturalPolishRunning(false);

      if (!baseline) {
        naturalPolishAbortRef.current = null;
        naturalPolishBaselineRef.current = null;
        naturalPolishBufferRef.current = "";
        return;
      }
      if (latestFileIdRef.current !== fileId) {
        // File switched while request was in flight; ignore this result.
        naturalPolishAbortRef.current = null;
        naturalPolishBaselineRef.current = null;
        naturalPolishBufferRef.current = "";
        return;
      }

      const rewrittenCore = rewrittenRaw.trim();
      if (!rewrittenCore) {
        naturalPolishAbortRef.current = null;
        naturalPolishBaselineRef.current = null;
        naturalPolishBufferRef.current = "";
        toast.error(t("editor:naturalPolishEmpty"));
        return;
      }

      const replacement = preserveSelectionWhitespace(baseline.selection, rewrittenCore);
      const modifiedContent =
        baseline.content.slice(0, baseline.startOffset) +
        replacement +
        baseline.content.slice(baseline.endOffset);

      naturalPolishAbortRef.current = null;
      naturalPolishBaselineRef.current = null;
      naturalPolishBufferRef.current = "";

      onEnterDiffReview?.(fileId, baseline.content, modifiedContent);
    } catch (error) {
      if (controller.signal.aborted) {
        if (naturalPolishRunIdRef.current === runId) {
          setIsNaturalPolishRunning(false);
          naturalPolishAbortRef.current = null;
          naturalPolishBaselineRef.current = null;
          naturalPolishBufferRef.current = "";
        }
        return;
      }

      if (naturalPolishRunIdRef.current !== runId) return;
      setIsNaturalPolishRunning(false);
      naturalPolishAbortRef.current = null;
      naturalPolishBaselineRef.current = null;
      naturalPolishBufferRef.current = "";
      if (latestFileIdRef.current === fileId) {
        const errorMessage =
          error instanceof Error && error.message.trim()
            ? error.message
            : t("editor:naturalPolishFailed");
        toast.error(errorMessage);
      }
    }
  }, [
    isNaturalPolishRunning,
    projectId,
    fileId,
    fileType,
    selectionInfo,
    chunks,
    t,
    onEnterDiffReview,
  ]);

  // Abort in-flight natural polish request when unmounting
  useEffect(() => {
    return () => {
      naturalPolishAbortRef.current?.abort();
    };
  }, []);

  // Auto-scroll to bottom when streaming (only if user is already near bottom)
  // Don't auto-scroll if user is actively editing
  useEffect(() => {
    const el = scrollContainerRef.current;
    if (!el) return;

    // Don't auto-scroll if user is editing
    if (isUserEditingRef.current) return;

    // When streaming starts, default to following the output
    if (isStreaming) {
      // If the user hasn't scrolled away, keep following.
      if (shouldAutoScrollRef.current || isNearBottom(el)) {
        requestAnimationFrame(() => {
          el.scrollTop = el.scrollHeight;
        });
      }
    }
  }, [content, isStreaming]);

  // Prepare save content in background for large documents
  // This reduces the perceived save time by doing the merge during idle time
  useEffect(() => {
    if (!isLargeDoc || !isDirty || chunkingState.chunks.length === 0) return;

    // Only prepare if not already preparing
    if (isPreparingSaveRef.current) return;

    // Use requestIdleCallback to prepare content during idle time
    const prepareIdleId = ric(() => {
      if (chunkingState.chunks.length > 0) {
        const mergedChunks = mergeChunks(chunkingState.chunks);
        const suffixStart = chunkingState.isComplete
          ? content.length
          : Math.min(chunkingState.chunkedOffset, content.length);
        const suffix = suffixStart < content.length ? content.slice(suffixStart) : "";
        preparedSaveContentRef.current = `${mergedChunks}${suffix}`;
        isPreparingSaveRef.current = false;
      }
    }, { timeout: 1000 });

    isPreparingSaveRef.current = true;

    return () => {
      cic(prepareIdleId);
    };
  }, [
    isLargeDoc,
    isDirty,
    chunkingState.chunks,
    chunkingState.chunkedOffset,
    chunkingState.isComplete,
    content,
  ]);

  // Auto-save with adaptive debounce
  useEffect(() => {
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
      saveTimeoutRef.current = null;
    }
    if (!isDirty) return;
    if (isNaturalPolishRunning) return;

    saveTimeoutRef.current = setTimeout(async () => {
      await handleSaveRef.current();
    }, saveDebounceTime);

    return () => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
        saveTimeoutRef.current = null;
      }
    };
  }, [isDirty, title, content, saveDebounceTime, isNaturalPolishRunning]);

  // Handle save - optimized for large documents
  const handleSave = async () => {
    if (isSaving || !isDirty || isNaturalPolishRunning) return;

    setIsSaving(true);
    const saveStartTime = performance.now();
    const previousContent = lastSavedContentRef.current;

    try {
      // For large documents, use pre-prepared content if available
      // This reduces the merge operation time during save
      let contentToSave = content;
      if (isLargeDoc && preparedSaveContentRef.current !== null) {
        contentToSave = preparedSaveContentRef.current;
        preparedSaveContentRef.current = null; // Clear after use
      } else if (isLargeDoc && chunkingState.chunks.length > 0) {
        // Fallback: merge chunks if not pre-prepared.
        // Note: when lazy chunking is still in progress, `chunkingState.chunks`
        // covers only the chunked prefix. Append the untouched suffix from
        // `content` so we never truncate the document.
        const mergedChunks = mergeChunks(chunkingState.chunks);
        const suffixStart = chunkingState.isComplete
          ? content.length
          : Math.min(chunkingState.chunkedOffset, content.length);
        const suffix = suffixStart < content.length ? content.slice(suffixStart) : "";
        contentToSave = `${mergedChunks}${suffix}`;
      }

      // Determine if we should create a version
      // For large documents, we throttle version creation to avoid overhead
      const now = Date.now();
      const timeSinceLastVersion = now - lastVersionTimeRef.current;
      const contentLengthDiff = Math.abs(contentToSave.length - lastSavedContentRef.current.length);

      const shouldCreateVersion =
        contentToSave !== previousContent &&
        (
          // For small documents: create version on any significant change
          (!isLargeDoc && contentLengthDiff > 10) ||
          // For large documents: create version only if enough time passed or significant change
          (isLargeDoc &&
            (timeSinceLastVersion >= VERSION_THROTTLE_MS ||
              contentLengthDiff >= MIN_VERSION_CHANGE_CHARS))
        );

      let versionIntent: FileUpdateVersionIntent | undefined;
      if (contentToSave !== previousContent) {
        const wordCountToSave =
          contentToSave === content ? documentWordCount : countWords(contentToSave);
        versionIntent = shouldCreateVersion
          ? {
              change_type: isLargeDoc ? "auto_save" : "edit",
              change_source: "user",
              word_count: wordCountToSave,
            }
          : { skip_version: true, word_count: wordCountToSave };
      }

      // Perform a single save with explicit version intent to avoid
      // duplicate backend updates and conflicting version semantics.
      await onSave(versionIntent);

      if (contentToSave !== previousContent) {
        lastSavedContentRef.current = contentToSave;
        if (shouldCreateVersion) {
          lastVersionTimeRef.current = now;
        }
      }

      // Record daily writing stats for primary writing content.
      if (
        projectId &&
        (fileType === "draft" || fileType === "script") &&
        contentToSave !== previousContent
      ) {
        const previousWords = countWords(previousContent);
        const currentWords = countWords(contentToSave);
        const wordsAdded = Math.max(currentWords - previousWords, 0);
        const wordsDeleted = Math.max(previousWords - currentWords, 0);

        try {
          await writingStatsApi.recordStats(projectId, {
            word_count: currentWords,
            words_added: wordsAdded,
            words_deleted: wordsDeleted,
          });
        } catch (statsError) {
          logger.error("Failed to record writing stats:", statsError);
        }
      }

      setLastSaved(new Date());
      setIsDirty(false);

      // Log save performance for debugging (only in dev)
      if (import.meta.env.DEV) {
        const saveDuration = performance.now() - saveStartTime;
        if (isLargeDoc) {
          logger.debug(
            `[Auto-save] Large doc (${documentWordCount} words) saved in ${saveDuration.toFixed(0)}ms`
          );
        }
      }
    } catch (error) {
      logger.error("Failed to save:", error);
    } finally {
      setIsSaving(false);
    }
  };

  handleSaveRef.current = handleSave;

  // Handle keyboard shortcuts
  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Normal editor shortcuts
    if ((e.ctrlKey || e.metaKey) && e.key === "s") {
      e.preventDefault();
      handleSave();
      return;
    }

    // Diff review mode shortcuts
    // In review mode, we should not start new natural polish requests.
    if (isReviewMode) {
      // Shift+Y: Accept all
      if (e.shiftKey && (e.key === 'y' || e.key === 'Y')) {
        e.preventDefault();
        onAcceptAllEdits?.();
        return;
      }
      // Shift+N: Reject all
      if (e.shiftKey && (e.key === 'n' || e.key === 'N')) {
        e.preventDefault();
        onRejectAllEdits?.();
        return;
      }
      // Enter: Finish review
      if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        onFinishReview?.();
        return;
      }
      // Escape: Cancel review (reject all and exit)
      if (e.key === 'Escape') {
        e.preventDefault();
        onRejectAllEdits?.();
        // Small delay then finish
        setTimeout(() => onFinishReview?.(), 50);
        return;
      }
      return;
    }

    // Cmd/Ctrl + Shift + Q: Add selection to quote
    // Get text directly from the focused textarea (like SimpleEditor)
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && (e.key === 'q' || e.key === 'Q')) {
      e.preventDefault();
      const focusedChunkId = focusedChunkIdRef.current;
      if (focusedChunkId && fileId) {
        const textarea = chunkTextareaRefs.current.get(focusedChunkId);
        if (textarea) {
          const start = textarea.selectionStart;
          const end = textarea.selectionEnd;
          const text = textarea.value.substring(start, end).trim();
          if (text) {
            const displayTitle = fileTitle || title;
            addQuote(text, fileId, displayTitle);
          }
        }
      }
      return;
    }

    // Cmd/Ctrl + Shift + R: Natural polish selection
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && (e.key === 'r' || e.key === 'R')) {
      e.preventDefault();
      startNaturalPolish();
      return;
    }
  };

  // Handle title change
  const handleTitleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onTitleChange(e.target.value);
    setIsDirty(true);
  };

  // Handle rollback from version history
  const handleRollback = () => {
    setShowVersionHistory(false);
    window.location.reload(); // Simple reload for now
  };

  // Handle viewing version content
  // Preview feature deferred - users can view diff between versions instead
  // See: /apps/web/src/pages/VersionsPage.tsx for version comparison
  const handleViewVersionContent = () => {
    // Version preview via diff comparison is available in VersionsPage
    // This button is reserved for future inline preview feature
  };

  // Format last saved time
  const formatLastSaved = (date: Date) => {
    const now = new Date();
    const diff = Math.floor((now.getTime() - date.getTime()) / 1000);

    if (diff < 10) return t('editor:savedJustNow');
    if (diff < 60) return `${diff}${t('editor:secondsAgo')}`;
    if (diff < 3600) return `${Math.floor(diff / 60)}${t('editor:minutesAgo')}`;
    return date.toLocaleTimeString(getLocaleCode(), { hour: "2-digit", minute: "2-digit" });
  };

  // Cleanup selection timeout
  useEffect(() => {
    return () => {
      if (selectionTimeoutRef.current) {
        clearTimeout(selectionTimeoutRef.current);
      }
    };
  }, []);

  // Reset save/dirty state when switching files.
  useEffect(() => {
    setIsDirty(false);
    setLastSaved(null);
    lastSavedContentRef.current = latestContentRef.current;
    pendingBaselineSyncRef.current = true;
    lastVersionTimeRef.current = Date.now();
    preparedSaveContentRef.current = null;
    isPreparingSaveRef.current = false;
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
      saveTimeoutRef.current = null;
    }

    // This editor instance is often reused across file switches, so we must
    // clear selection and abort any in-flight natural polish requests.
    if (selectionTimeoutRef.current) {
      clearTimeout(selectionTimeoutRef.current);
      selectionTimeoutRef.current = null;
    }
    setSelectedText("");
    setSelectionPosition(null);
    setSelectionInfo(null);

    naturalPolishRunIdRef.current += 1;
    naturalPolishAbortRef.current?.abort();
    naturalPolishAbortRef.current = null;
    naturalPolishBaselineRef.current = null;
    naturalPolishBufferRef.current = "";
    setIsNaturalPolishRunning(false);
  }, [fileId]);

  // Some file loads are async after fileId updates; sync baseline once on first content refresh.
  useEffect(() => {
    if (!pendingBaselineSyncRef.current) return;
    if (isDirty) return;
    lastSavedContentRef.current = content;
    pendingBaselineSyncRef.current = false;
  }, [content, isDirty]);

  // Reset scroll state when file changes
  useEffect(() => {
    shouldAutoScrollRef.current = true;
    isUserEditingRef.current = false;
    lastCursorStateRef.current = null;
    setPendingCursorRestore(null);
    pendingLocalContentSyncRef.current = null;
    pendingViewportAnchorRef.current = null;
  }, [fileId]);

  // Cleanup large string references when file changes or component unmounts
  // This helps garbage collection by not holding onto old content
  useEffect(() => {
    const textareaRefs = chunkTextareaRefs.current;

    // Clear prepared save content on file change
    preparedSaveContentRef.current = null;

    return () => {
      // Cleanup on unmount
      preparedSaveContentRef.current = null;
      textareaRefs.clear();
    };
  }, [fileId]);

  // Ensure focused textarea remains visible after virtualization updates
  // Use layout effect to sync before paint
  useIsomorphicLayoutEffect(() => {
    if (!focusedChunkIdRef.current || !scrollContainerRef.current) return;
    // During typing (especially IME composition), forcing scroll correction
    // causes jarring upward jumps. Let the browser keep caret position.
    if (isComposingRef.current || isUserEditingRef.current) return;

    const textarea = chunkTextareaRefs.current.get(focusedChunkIdRef.current);
    if (!textarea) return;

    // Check if textarea is partially outside visible area
    const containerRect = scrollContainerRef.current.getBoundingClientRect();
    const textareaRect = textarea.getBoundingClientRect();
    const containerHeight = containerRect.height;
    const textareaHeight = textareaRect.height;

    // Do not force-align oversized chunks to the viewport top/bottom.
    // This can produce repeated scroll jumps while editing long sections.
    if (textareaHeight >= containerHeight) return;

    // If textarea is above visible area
    if (textareaRect.top < containerRect.top) {
      scrollContainerRef.current.scrollTop -= (containerRect.top - textareaRect.top);
    }
    // If textarea is below visible area
    else if (textareaRect.bottom > containerRect.bottom) {
      scrollContainerRef.current.scrollTop += (textareaRect.bottom - containerRect.bottom);
    }
  }, [chunks]); // Re-run when chunks change

  // Register textarea ref for a chunk
  const registerTextareaRef = useCallback((chunkId: string, el: HTMLTextAreaElement | null) => {
    if (el) {
      chunkTextareaRefs.current.set(chunkId, el);
    } else {
      chunkTextareaRefs.current.delete(chunkId);
    }
  }, []);

  // Handle chunk focus
  const handleChunkFocus = useCallback((chunkId: string) => {
    focusedChunkIdRef.current = chunkId;
    isUserEditingRef.current = true;
  }, []);

  // Handle chunk blur
  const handleChunkBlur = useCallback((chunkId: string) => {
    // Delay clearing editing state to allow for re-render restoration
    setTimeout(() => {
      if (focusedChunkIdRef.current === chunkId) {
        isUserEditingRef.current = false;
      }
    }, 100);
  }, []);

  // Handle composition start
  const handleCompositionStart = useCallback((chunkId: string) => {
    isComposingRef.current = true;
    focusedChunkIdRef.current = chunkId;
    isUserEditingRef.current = true;
  }, []);

  // Handle composition end
  const handleCompositionEnd = useCallback(() => {
    isComposingRef.current = false;
  }, []);

  // Render a single chunk using memoized component
  const renderChunk = useCallback((visibleChunk: { chunk: DocumentChunk; index: number; height: number; startY: number }) => {
    const { chunk, index, height } = visibleChunk;
    const isFocused = focusedChunkIdRef.current === chunk.id;
    const isLastChunk = index === chunks.length - 1;

    return (
      <ChunkRenderer
        key={chunk.id}
        chunk={chunk}
        index={index}
        height={height}
        isStreaming={isStreaming}
        isLastChunk={isLastChunk}
        readOnly={readOnly || isNaturalPolishRunning}
        isFocused={isFocused}
        onRegisterRef={registerTextareaRef}
        onContentChange={handleChunkContentChange}
        onSelect={handleChunkSelection}
        onFocus={handleChunkFocus}
        onBlur={handleChunkBlur}
        onCompositionStart={handleCompositionStart}
        onCompositionEnd={handleCompositionEnd}
        placeholder={t('editor:placeholder.contentPlaceholder')}
      />
    );
  }, [chunks.length, isStreaming, readOnly, isNaturalPolishRunning, registerTextareaRef, handleChunkContentChange, handleChunkSelection, handleChunkFocus, handleChunkBlur, handleCompositionStart, handleCompositionEnd, t]);

  return (
    <div className="relative flex flex-col h-full bg-[hsl(var(--bg-primary))]" onKeyDown={handleKeyDown}>
      {/* Diff Review Toolbar - shown when in review mode */}
      {isReviewMode && diffReviewState && onAcceptAllEdits && onRejectAllEdits && onFinishReview && (
        <DiffToolbar
          pendingEdits={diffReviewState.pendingEdits}
          onAcceptAll={onAcceptAllEdits}
          onRejectAll={onRejectAllEdits}
          onFinish={onFinishReview}
        />
      )}

      {/* Streaming indicator overlay */}
      {isStreaming && !isReviewMode && (
        <div className="absolute top-0 left-0 right-0 z-10 bg-gradient-to-r from-[hsl(var(--accent-primary)/0.15)] to-[hsl(var(--accent-primary)/0.05)] px-6 py-3 flex items-center gap-3 border-b border-[hsl(var(--accent-primary)/0.2)] backdrop-blur-sm">
          <div className="relative">
            <Sparkles size={18} className="text-[hsl(var(--accent-primary))]" />
            <div className="absolute inset-0 animate-ping">
              <Sparkles size={18} className="text-[hsl(var(--accent-primary))] opacity-40" />
            </div>
          </div>
          <span className="text-sm text-[hsl(var(--accent-primary))] font-medium">{t('editor:aiWriting')}</span>
          <div className="flex gap-1">
            <span className="w-1.5 h-1.5 bg-[hsl(var(--accent-primary))] rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
            <span className="w-1.5 h-1.5 bg-[hsl(var(--accent-primary))] rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
            <span className="w-1.5 h-1.5 bg-[hsl(var(--accent-primary))] rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
          </div>
          <span className="text-xs text-[hsl(var(--text-secondary))] ml-2">
            ({stats.totalChunks} {t('editor:chunks', 'chunks')})
          </span>
        </div>
      )}

      {/* Title bar */}
      <div
        className={`shrink-0 px-6 ${
          isReviewMode
            ? 'bg-[hsl(var(--bg-primary))] pb-1.5 pt-2'
            : 'bg-[hsl(var(--bg-secondary)/0.3)] py-4'
        } ${isStreaming && !isReviewMode ? 'mt-12' : ''}`}
      >
        <input
          type="text"
          value={title}
          onChange={handleTitleChange}
          disabled={readOnly || isStreaming || isReviewMode || isNaturalPolishRunning}
          placeholder={t('editor:placeholder.titlePlaceholder')}
          className={`w-full bg-transparent font-bold text-[hsl(var(--text-primary))] placeholder-[hsl(var(--text-secondary))] outline-none border-none ${
            isReviewMode ? 'text-[1.7rem] leading-tight' : 'text-xl'
          }`}
        />
      </div>

      {/* Content area - switch between normal editor and diff review */}
      {isReviewMode && diffReviewState && onAcceptEdit && onRejectEdit && onResetEdit ? (
        <DiffReviewSplitView
          originalContent={diffReviewState.originalContent}
          modifiedContent={diffReviewState.modifiedContent}
          pendingEdits={diffReviewState.pendingEdits}
          onAcceptEdit={onAcceptEdit}
          onRejectEdit={onRejectEdit}
          onResetEdit={onResetEdit}
        />
      ) : (
        <div
          ref={scrollContainerRef}
          data-editor-scroll-container="true"
          className="flex-1 overflow-auto"
          onScroll={handleContentScroll}
          style={{
            overflowAnchor: "none",
          }}
        >
          <div
            className="relative w-full px-6 py-4"
            style={{
              height: `${totalSize}px`,
            }}
          >
            {/* Virtualized chunks */}
            {visibleChunks.map((item) => (
              <div
                key={item.chunk.id}
                data-index={item.index}
                ref={virtualizer.measureElement}
                style={{
                  position: 'absolute',
                  top: item.startY,
                  left: 0,
                  width: '100%',
                }}
              >
                {renderChunk(item)}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Status bar - hide during review mode */}
      {!isReviewMode && (
        <div className="shrink-0 px-6 py-2 flex items-center justify-between bg-[hsl(var(--bg-secondary)/0.3)]">
          <div className="flex items-center gap-4 text-xs text-[hsl(var(--text-secondary))]">
            <span>
              {t('editor:wordCount')} <strong className="text-[hsl(var(--text-primary))]">{stats.totalWords}</strong>
            </span>
            <span>
              {t('editor:paragraphCount')} <strong className="text-[hsl(var(--text-primary))]">{content.split(/\n\n+/).filter(Boolean).length}</strong>
            </span>
            <span>
              {t('editor:chunks', 'Chunks')} <strong className="text-[hsl(var(--text-primary))]">{stats.totalChunks}</strong>
            </span>
            {/* Chunking progress indicator */}
            {chunkingState.isChunking && (
              <span className="flex items-center gap-1 text-[hsl(var(--accent-primary))]">
                <Loader2 size={12} className="animate-spin" />
                {t('editor:loading', 'Loading...')} {Math.round(chunkingState.progress * 100)}%
              </span>
            )}
          </div>

          <div className="flex items-center gap-3">
            {/* Version history button */}
            {fileId && (
              <button
                onClick={() => setShowVersionHistory(true)}
                className="px-2 py-1.5 text-xs text-[hsl(var(--text-secondary))] hover:text-[hsl(var(--text-primary))] hover:bg-[hsl(var(--bg-secondary))] rounded flex items-center gap-1 transition-colors"
                title={t('editor:versionHistory')}
              >
                <History size={14} />
                {t('editor:history')}
              </button>
            )}

            {/* Natural polish (selected text) */}
            {fileId && (
              <button
                onClick={startNaturalPolish}
                disabled={
                  !projectId ||
                  readOnly ||
                  isStreaming ||
                  isNaturalPolishRunning ||
                  !selectedText
                }
                className="px-2 py-1.5 text-xs text-[hsl(var(--text-secondary))] hover:text-[hsl(var(--text-primary))] hover:bg-[hsl(var(--bg-secondary))] rounded flex items-center gap-1 transition-colors disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-transparent"
                title={
                  !projectId
                    ? t("editor:naturalPolishMissingContext")
                    : !selectedText
                      ? t("editor:naturalPolishNoSelection")
                      : t("editor:naturalPolishTooltip")
                }
              >
                {isNaturalPolishRunning ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : (
                  <Sparkles size={14} />
                )}
                {isNaturalPolishRunning
                  ? t("editor:naturalPolishWorking")
                  : t("editor:naturalPolish")}
              </button>
            )}

            {/* Save status */}
            {isSaving ? (
              <span className="text-xs text-[hsl(var(--text-secondary))] flex items-center gap-1">
                <Clock size={12} className="animate-spin" />
                {t('editor:saving')}
              </span>
            ) : lastSaved ? (
              <span className="text-xs text-[hsl(var(--text-secondary))] flex items-center gap-1">
                <Check size={12} className="text-[hsl(var(--success))]" />
                {formatLastSaved(lastSaved)}
              </span>
            ) : isDirty ? (
              <span className="text-xs text-[hsl(var(--warning))]">{t('editor:unsaved')}</span>
            ) : null}

            {/* Save button */}
            <button
              onClick={handleSave}
              disabled={isSaving || !isDirty || readOnly || isStreaming || isNaturalPolishRunning}
              className="px-3 py-1.5 text-xs bg-[hsl(var(--accent-primary))] text-white rounded hover:bg-[hsl(var(--accent-dark))] disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5 transition-colors"
            >
              <Save size={14} />
              {t('editor:save')}
            </button>
          </div>
        </div>
      )}

      {/* Version History Modal */}
      {showVersionHistory && fileId && (
        <FileVersionHistory
          fileId={fileId}
          fileTitle={title}
          onClose={() => setShowVersionHistory(false)}
          onRollback={handleRollback}
          onViewContent={handleViewVersionContent}
        />
      )}

      {/* Selection Toolbar */}
      {selectedText && selectionPosition && fileId && (
        <SelectionToolbar
          text={selectedText}
          position={selectionPosition}
          onAdd={handleAddQuote}
          onClose={closeSelectionToolbar}
        />
      )}
    </div>
  );
};
