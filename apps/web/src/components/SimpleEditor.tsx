import { useState, useEffect, useRef, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { Save, Clock, Check, History, Sparkles, Loader2 } from "lucide-react";
import type { FileUpdateVersionIntent } from "../lib/api";
import { writingStatsApi } from "../lib/writingStatsApi";
import { FileVersionHistory } from "./FileVersionHistory";
import { DiffReviewSplitView } from "./DiffReviewSplitView";
import { DiffToolbar } from "./DiffToolbar";
import { SelectionToolbar } from "./SelectionToolbar";
import { useTextQuote } from "../contexts/TextQuoteContext";
import { usePinchZoom } from "../hooks/useGestures";
import type { DiffReviewState } from "../types";
import { getLocaleCode } from "../lib/i18n-helpers";
import { countWords } from "../lib/documentChunker";
import { logger } from "../lib/logger";
import { toast } from "../lib/toast";
import { preserveSelectionWhitespace } from "../lib/naturalPolish";
import { naturalPolishApi } from "../lib/naturalPolishApi";

const isNearBottom = (el: HTMLElement, thresholdPx = 32) => {
  return el.scrollHeight - el.scrollTop - el.clientHeight < thresholdPx;
};

const SIMPLE_EDITOR_MIN_HEIGHT_PX = 200;

const restoreContainerScrollTop = (container: HTMLElement | null, prevScrollTop: number | null) => {
  if (!container || prevScrollTop === null) return;

  const restore = () => {
    const maxTop = Math.max(0, container.scrollHeight - container.clientHeight);
    container.scrollTop = Math.min(prevScrollTop, maxTop);
  };

  restore();
  requestAnimationFrame(restore);
};

interface SimpleEditorProps {
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

export const SimpleEditor = ({
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
}: SimpleEditorProps) => {
  const { t } = useTranslation(['editor']);
  const { addQuote } = useTextQuote();
  const [isSaving, setIsSaving] = useState(false);
  const [lastSaved, setLastSaved] = useState<Date | null>(null);
  const [isDirty, setIsDirty] = useState(false);
  const [showVersionHistory, setShowVersionHistory] = useState(false);
  // Selection toolbar state
  const [selectedText, setSelectedText] = useState("");
  const [selectionPosition, setSelectionPosition] = useState<{ x: number; y: number } | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const contentAreaRef = useRef<HTMLDivElement>(null);
  const mirrorRef = useRef<HTMLDivElement>(null);
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const selectionTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const selectionRangeRef = useRef<{ start: number; end: number } | null>(null);
  const lastSavedContentRef = useRef<string>(content);
  const latestContentRef = useRef(content);
  const previousFileIdRef = useRef(fileId);
  const pendingBaselineSyncRef = useRef(false);
  const shouldAutoScrollRef = useRef(true);
  const isComposingRef = useRef(false);
  const handleSaveRef = useRef<() => Promise<void>>(async () => undefined);
  const latestFileIdRef = useRef<string | undefined>(fileId);

  // Natural polish (de-AI tone) state
  const [isNaturalPolishRunning, setIsNaturalPolishRunning] = useState(false);
  const naturalPolishRunIdRef = useRef(0);
  const naturalPolishAbortRef = useRef<AbortController | null>(null);
  const naturalPolishBufferRef = useRef<string>("");
  const naturalPolishBaselineRef = useRef<{
    content: string;
    start: number;
    end: number;
    selection: string;
  } | null>(null);

  latestContentRef.current = content;
  latestFileIdRef.current = fileId;

  // Pinch-to-zoom gesture support
  const { zoom, bind: bindPinchZoom, resetZoom } = usePinchZoom(1, 0.5, 2.5);

  // Reset zoom when file changes
  useEffect(() => {
    resetZoom();
  }, [fileId, resetZoom]);

  // Auto-resize textarea
  // NOTE: Avoid a full `height="auto"` reflow on every keystroke.
  // That reintroduces the "jump back to editor top" bug for hardware keyboard input.
  // While the textarea is focused we only grow; when focus leaves (or on file switches)
  // we do a full recalculation so the editor can shrink safely.
  const adjustTextareaHeight = useCallback((force = false) => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    const container = contentAreaRef.current;
    const prevScrollTop = container ? container.scrollTop : null;
    const currentHeightPx =
      Number.parseFloat(textarea.style.height || "0") || SIMPLE_EDITOR_MIN_HEIGHT_PX;
    const isFocused = typeof document !== "undefined" && document.activeElement === textarea;

    let nextHeightPx = Math.max(textarea.scrollHeight, SIMPLE_EDITOR_MIN_HEIGHT_PX);

    if (force || !isFocused) {
      const previousHeight = textarea.style.height;
      const previousMinHeight = textarea.style.minHeight;
      textarea.style.height = "0px";
      textarea.style.minHeight = "0";
      nextHeightPx = Math.max(textarea.scrollHeight, SIMPLE_EDITOR_MIN_HEIGHT_PX);
      textarea.style.minHeight = previousMinHeight;
      textarea.style.height = previousHeight;
    } else if (nextHeightPx < currentHeightPx) {
      nextHeightPx = currentHeightPx;
    }

    if (force || Math.abs(nextHeightPx - currentHeightPx) > 1) {
      textarea.style.height = `${nextHeightPx}px`;
    }

    restoreContainerScrollTop(container, prevScrollTop);
  }, []);

  // Check if in diff review mode
  const isReviewMode = diffReviewState?.isReviewing && diffReviewState.fileId === fileId;

  useEffect(() => {
    const isFocused =
      typeof document !== "undefined" && document.activeElement === textareaRef.current;
    adjustTextareaHeight(!isFocused);
  }, [content, adjustTextareaHeight]);

  // When switching files, force a full recalculation so short files don't leave huge height.
  useEffect(() => {
    const didFileChange = previousFileIdRef.current !== fileId;
    previousFileIdRef.current = fileId;

    adjustTextareaHeight(true);
    // When opening a new file, default to "follow bottom" during streaming
    shouldAutoScrollRef.current = true;
    // Reset save/dirty state for the new file and sync baseline on first content load.
    setIsDirty(false);
    setLastSaved(null);
    lastSavedContentRef.current = latestContentRef.current;
    pendingBaselineSyncRef.current = true;
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
      saveTimeoutRef.current = null;
    }

    if (!didFileChange) {
      return;
    }

    // This editor instance is often reused across file switches, so we must
    // clear selection and abort any in-flight natural polish requests.
    if (selectionTimeoutRef.current) {
      clearTimeout(selectionTimeoutRef.current);
      selectionTimeoutRef.current = null;
    }
    setSelectedText("");
    setSelectionPosition(null);
    selectionRangeRef.current = null;

    naturalPolishRunIdRef.current += 1;
    naturalPolishAbortRef.current?.abort();
    naturalPolishAbortRef.current = null;
    naturalPolishBaselineRef.current = null;
    naturalPolishBufferRef.current = "";
    setIsNaturalPolishRunning(false);
  }, [fileId, adjustTextareaHeight]);

  // Some file switches load content asynchronously after fileId changes.
  // Sync baseline once when the new content arrives so dirty/version diff is correct.
  useEffect(() => {
    if (!pendingBaselineSyncRef.current) return;
    if (isDirty) return;
    lastSavedContentRef.current = content;
    pendingBaselineSyncRef.current = false;
  }, [content, isDirty]);

  // Re-adjust textarea height when exiting review mode
  const prevReviewModeRef = useRef(isReviewMode);
  useEffect(() => {
    const wasInReviewMode = prevReviewModeRef.current;
    prevReviewModeRef.current = isReviewMode;
    
    // If we just exited review mode, schedule a height adjustment
    if (wasInReviewMode && !isReviewMode) {
      // If diffReviewState is cleared, we assume reviewed changes were saved.
      // Sync local save baseline so "unsaved" status doesn't get stuck.
      if (!diffReviewState) {
        lastSavedContentRef.current = content;
        setIsDirty(false);
        setLastSaved(new Date());
      }

      // Use setTimeout to wait for the textarea to be rendered
      setTimeout(() => {
        adjustTextareaHeight(true);
      }, 50);
    }
  }, [isReviewMode, diffReviewState, content, adjustTextareaHeight]);

  const handleContentScroll = useCallback(() => {
    const el = contentAreaRef.current;
    if (!el) return;
    shouldAutoScrollRef.current = isNearBottom(el);
  }, []);

  // Calculate selection position using mirror div technique
  const getSelectionPosition = useCallback(() => {
    const textarea = textareaRef.current;
    const mirror = mirrorRef.current;
    if (!textarea || !mirror) return null;

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    if (start === end) return null;

    // Copy textarea styles to mirror
    const styles = window.getComputedStyle(textarea);
    mirror.style.cssText = `
      position: absolute;
      visibility: hidden;
      white-space: pre-wrap;
      word-wrap: break-word;
      overflow-wrap: break-word;
      width: ${styles.width};
      font: ${styles.font};
      padding: ${styles.padding};
      border: ${styles.border};
      line-height: ${styles.lineHeight};
      letter-spacing: ${styles.letterSpacing};
    `;

    // Create span for measuring position
    const textBefore = textarea.value.substring(0, start);
    const selectedText = textarea.value.substring(start, end);

    mirror.innerHTML = '';
    mirror.appendChild(document.createTextNode(textBefore));
    const span = document.createElement('span');
    span.textContent = selectedText;
    mirror.appendChild(span);

    const textareaRect = textarea.getBoundingClientRect();
    const spanRect = span.getBoundingClientRect();
    const mirrorRect = mirror.getBoundingClientRect();

    // Calculate position relative to viewport
    const x = textareaRect.left + (spanRect.left - mirrorRect.left) + spanRect.width / 2;
    const y = textareaRect.top + (spanRect.top - mirrorRect.top) - textarea.scrollTop - 8;

    return { x, y };
  }, []);

  // Handle text selection
  const handleSelection = useCallback((target?: HTMLTextAreaElement | null) => {
    if (selectionTimeoutRef.current) {
      clearTimeout(selectionTimeoutRef.current);
    }

    const textarea = target ?? textareaRef.current;
    if (!textarea) return;

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const text = textarea.value.substring(start, end).trim();

    if (!text) {
      setSelectedText("");
      setSelectionPosition(null);
      selectionRangeRef.current = null;
      return;
    }

    // Keep a "selection exists" signal immediate so action buttons can respond quickly.
    setSelectedText(text);
    selectionRangeRef.current = { start, end };

    // Delay showing toolbar by 300ms
    selectionTimeoutRef.current = setTimeout(() => {
      const position = getSelectionPosition();
      if (position) {
        setSelectionPosition(position);
      }
    }, 300);
  }, [getSelectionPosition]);

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

    const textarea = textareaRef.current;
    if (!textarea) return;

    const range = selectionRangeRef.current;
    if (!range || range.start === range.end) {
      toast.info(t("editor:naturalPolishNoSelection"));
      return;
    }

    const { start, end } = range;
    const selection = textarea.value.substring(start, end);
    if (!selection.trim()) {
      toast.info(t("editor:naturalPolishNoSelection"));
      return;
    }

    const baselineContent = textarea.value;
    naturalPolishBaselineRef.current = { content: baselineContent, start, end, selection };
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
        baseline.content.slice(0, baseline.start) +
        replacement +
        baseline.content.slice(baseline.end);

      naturalPolishAbortRef.current = null;
      naturalPolishBaselineRef.current = null;
      naturalPolishBufferRef.current = "";

      onEnterDiffReview?.(fileId, baseline.content, modifiedContent);
    } catch (error) {
      // Abort is user-intentional (or file-switch cleanup); keep silent.
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
    t,
    onEnterDiffReview,
  ]);

  // Cleanup selection timeout
  useEffect(() => {
    return () => {
      if (selectionTimeoutRef.current) {
        clearTimeout(selectionTimeoutRef.current);
      }
    };
  }, []);

  // Abort in-flight natural polish request when unmounting
  useEffect(() => {
    return () => {
      naturalPolishAbortRef.current?.abort();
    };
  }, []);

  // Auto-scroll to bottom when streaming (only if user is already near bottom)
  useEffect(() => {
    const el = contentAreaRef.current;
    if (!el) return;

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

  // Auto-save with debounce
  useEffect(() => {
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
      saveTimeoutRef.current = null;
    }
    if (!isDirty) return;
    if (isNaturalPolishRunning) return;

    saveTimeoutRef.current = setTimeout(async () => {
      await handleSaveRef.current();
    }, 3000);

    return () => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
        saveTimeoutRef.current = null;
      }
    };
  }, [isDirty, title, content, isNaturalPolishRunning]);

  // Handle save
  const handleSave = async () => {
    if (isSaving || !isDirty || isNaturalPolishRunning) return;

    setIsSaving(true);
    const previousContent = lastSavedContentRef.current;
    const contentChanged = content !== previousContent;
    try {
      let versionIntent: FileUpdateVersionIntent | undefined;
      if (contentChanged) {
        const currentWords = countWords(content);
        const shouldCreateVersion = Math.abs(content.length - previousContent.length) > 10;
        versionIntent = shouldCreateVersion
          ? { change_type: "edit", change_source: "user", word_count: currentWords }
          : { skip_version: true, word_count: currentWords };
      }
      await onSave(versionIntent);

      if (contentChanged) {
        lastSavedContentRef.current = content;
      }

      // Record daily writing stats for primary writing content.
      if (
        projectId &&
        (fileType === "draft" || fileType === "script") &&
        contentChanged
      ) {
        const previousWords = countWords(previousContent);
        const currentWords = countWords(content);
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
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && (e.key === 'q' || e.key === 'Q')) {
      e.preventDefault();
      const textarea = textareaRef.current;
      if (textarea && fileId) {
        const start = textarea.selectionStart;
        const end = textarea.selectionEnd;
        const text = textarea.value.substring(start, end).trim();
        if (text) {
          const displayTitle = fileTitle || title;
          addQuote(text, fileId, displayTitle);
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

  // Handle content change
  const handleContentChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    onContentChange(e.target.value);
    setIsDirty(true);

    // During IME composition (e.g. Chinese Pinyin), avoid resizing on each intermediate update.
    // We'll resize on `compositionend` / effect instead.
    if (!isComposingRef.current) {
      adjustTextareaHeight();
    }
  };

  const handleContentBlur = () => {
    adjustTextareaHeight(true);
  };

  // Handle rollback from version history
  const handleRollback = () => {
    // Reload the content after rollback
    // The parent component will handle this by re-fetching the file
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
          ref={contentAreaRef}
          data-editor-scroll-container="true"
          className="flex-1 overflow-auto"
          onScroll={handleContentScroll}
          style={{ overflowAnchor: "none" }}
          {...bindPinchZoom()}
        >
          <div className="px-6 py-4">
            <div className="relative">
              <textarea
                ref={textareaRef}
                value={content}
                onChange={handleContentChange}
                onSelect={(event) => handleSelection(event.currentTarget)}
                onMouseUp={(event) => handleSelection(event.currentTarget)}
                onBlur={handleContentBlur}
                onCompositionStart={() => {
                  isComposingRef.current = true;
                }}
                onCompositionEnd={() => {
                  isComposingRef.current = false;
                  // Resize after IME commits the final text.
                  requestAnimationFrame(() => adjustTextareaHeight());
                }}
                disabled={readOnly || isStreaming || isNaturalPolishRunning}
                placeholder={t('editor:placeholder.contentPlaceholder')}
                className={`w-full overflow-y-hidden bg-transparent text-[hsl(var(--text-primary))] placeholder-[hsl(var(--text-secondary))] outline-none border-none resize-none leading-relaxed text-base ${isStreaming ? 'cursor-default' : ''}`}
                style={{ minHeight: `${SIMPLE_EDITOR_MIN_HEIGHT_PX}px`, fontSize: `${zoom}em` }}
              />
              {/* Mirror div for calculating selection position */}
              <div ref={mirrorRef} aria-hidden="true" />
              {/* Typing cursor for streaming */}
              {isStreaming && content && (
                <span className="inline-block w-0.5 h-5 bg-[hsl(var(--accent-primary))] ml-0.5 animate-pulse absolute" style={{ transform: 'translateY(-1px)' }} />
              )}
            </div>
          </div>
        </div>
      )}

      {/* Status bar - hide during review mode */}
      {!isReviewMode && (
        <div className="shrink-0 px-6 py-2 flex items-center justify-between bg-[hsl(var(--bg-secondary)/0.3)]">
          <div className="flex items-center gap-4 text-xs text-[hsl(var(--text-secondary))]">
            <span>
              {t('editor:wordCount')} <strong className="text-[hsl(var(--text-primary))]">{countWords(content)}</strong>
            </span>
            <span>
              {t('editor:paragraphCount')} <strong className="text-[hsl(var(--text-primary))]">{content.split(/\n\n+/).filter(Boolean).length}</strong>
            </span>
            {/* Zoom indicator - only show when zoomed */}
            {zoom !== 1 && (
              <button
                onClick={resetZoom}
                className="text-[hsl(var(--text-secondary))] hover:text-[hsl(var(--text-primary))] transition-colors"
                title={t('editor:resetZoom')}
              >
                {Math.round(zoom * 100)}%
              </button>
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
