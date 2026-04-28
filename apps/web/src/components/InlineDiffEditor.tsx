/**
 * InlineDiffEditor — renders an inline diff between original and modified content.
 *
 * Diff Review B 方案: this view is read-only (no inline ✅/❌ actions). Users review edits
 * via the right-side review queue, and can "locate" an edit in this diff view.
 */
import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import type { PendingEdit } from "../types";
import { cn } from "../lib/utils";
import {
  buildReviewSegmentsFromDiffs,
  computeParagraphReviewDiffs,
  type ReviewDiffSegment,
} from "../lib/diffReview";

export interface InlineDiffEditorHandle {
  scrollToEdit: (editId: string) => void;
}

interface InlineDiffEditorProps {
  originalContent: string;
  modifiedContent: string;
  pendingEdits: PendingEdit[];
  activeEditId?: string | null;
  onSelectEdit?: (editId: string) => void;
}

interface DiffRow {
  id: string;
  segments: ReviewDiffSegment[];
  hasEdits: boolean;
  estimatedHeight: number;
  content: string;
}

const VIRTUALIZATION_THRESHOLD = 50000;

function estimateRowHeight(content: string, hasEdits: boolean): number {
  const lineHeight = 24;
  const charsPerLine = 80;
  const lineCount = Math.ceil(content.length / charsPerLine);
  const editPadding = hasEdits ? 12 : 0;
  return Math.max(lineCount * lineHeight + editPadding, 28);
}

function groupSegmentsIntoRows(segments: ReviewDiffSegment[]): DiffRow[] {
  const rows: DiffRow[] = [];
  let currentSegments: ReviewDiffSegment[] = [];
  let currentContent = "";
  let currentHasEdits = false;
  const targetRowSize = 500;
  let rowIdCounter = 0;

  for (const segment of segments) {
    const isEdit = segment.type !== "equal";

    if (isEdit && currentContent.length > 100) {
      if (currentSegments.length > 0) {
        rows.push({
          id: `row-${rowIdCounter++}`,
          segments: currentSegments,
          hasEdits: currentHasEdits,
          estimatedHeight: estimateRowHeight(currentContent, currentHasEdits),
          content: currentContent,
        });
        currentSegments = [];
        currentContent = "";
        currentHasEdits = false;
      }
    }

    currentSegments.push(segment);
    currentContent += segment.text + (segment.newText || "");
    currentHasEdits = currentHasEdits || isEdit;

    if (isEdit) {
      rows.push({
        id: `row-${rowIdCounter++}`,
        segments: currentSegments,
        hasEdits: currentHasEdits,
        estimatedHeight: estimateRowHeight(currentContent, currentHasEdits),
        content: currentContent,
      });
      currentSegments = [];
      currentContent = "";
      currentHasEdits = false;
    } else if (currentContent.length >= targetRowSize) {
      rows.push({
        id: `row-${rowIdCounter++}`,
        segments: currentSegments,
        hasEdits: currentHasEdits,
        estimatedHeight: estimateRowHeight(currentContent, currentHasEdits),
        content: currentContent,
      });
      currentSegments = [];
      currentContent = "";
      currentHasEdits = false;
    }
  }

  if (currentSegments.length > 0) {
    rows.push({
      id: `row-${rowIdCounter++}`,
      segments: currentSegments,
      hasEdits: currentHasEdits,
      estimatedHeight: estimateRowHeight(currentContent, currentHasEdits),
      content: currentContent,
    });
  }

  return rows;
}

export const InlineDiffEditor = forwardRef<InlineDiffEditorHandle, InlineDiffEditorProps>(function InlineDiffEditor(
  { originalContent, modifiedContent, pendingEdits, activeEditId, onSelectEdit },
  ref
) {
  const containerRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const initialAutoScrollDoneRef = useRef(false);

  const shouldVirtualize = useMemo(() => {
    return false;
    const totalLength = originalContent.length + modifiedContent.length;
    return totalLength > VIRTUALIZATION_THRESHOLD;
  }, [originalContent, modifiedContent]);

  const diffSegments = useMemo((): ReviewDiffSegment[] => {
    const diffs = computeParagraphReviewDiffs(originalContent, modifiedContent);
    return buildReviewSegmentsFromDiffs(diffs);
  }, [originalContent, modifiedContent]);

  const diffRows = useMemo(() => {
    if (!shouldVirtualize) return [];
    return groupSegmentsIntoRows(diffSegments);
  }, [diffSegments, shouldVirtualize]);

  // eslint-disable-next-line react-hooks/incompatible-library
  const virtualizer = useVirtualizer({
    count: diffRows.length,
    getScrollElement: () => scrollContainerRef.current,
    estimateSize: (index) => diffRows[index]?.estimatedHeight || 28,
    overscan: 5,
  });

  useEffect(() => {
    // If content changes, allow auto-scroll again.
    initialAutoScrollDoneRef.current = false;
  }, [originalContent, modifiedContent]);

  const editIndexToRowIndexMap = useMemo(() => {
    const map = new Map<number, number>();
    if (!shouldVirtualize) return map;

    diffRows.forEach((row, rowIndex) => {
      row.segments.forEach((seg) => {
        if (seg.editIndex == null) return;
        if (!map.has(seg.editIndex)) {
          map.set(seg.editIndex, rowIndex);
        }
      });
    });

    return map;
  }, [diffRows, shouldVirtualize]);

  const editIdToIndexMap = useMemo(() => {
    const map = new Map<string, number>();
    pendingEdits.forEach((edit, index) => map.set(edit.id, index));
    return map;
  }, [pendingEdits]);

  const scrollToEdit = useCallback((editId: string) => {
    if (!editId) return;

    const editIndex = editIdToIndexMap.get(editId);
    if (editIndex == null) return;

    try {
      if (shouldVirtualize) {
        const rowIndex = editIndexToRowIndexMap.get(editIndex);
        if (rowIndex != null) {
          virtualizer.scrollToIndex(rowIndex, { align: "center" });
        }

        // Try to bring the exact segment into view after virtual rows are mounted.
        let attempt = 0;
        const maxAttempts = 4;
        const tryScrollIntoView = () => {
          const el = scrollContainerRef.current?.querySelector<HTMLElement>(
            `[data-edit-id="${editId}"]`
          );
          if (el) {
            el.scrollIntoView({ block: "center" });
            return;
          }
          attempt += 1;
          if (attempt < maxAttempts) {
            requestAnimationFrame(tryScrollIntoView);
          }
        };

        requestAnimationFrame(tryScrollIntoView);
        return;
      }

      const el = containerRef.current?.querySelector<HTMLElement>(`[data-edit-id="${editId}"]`);
      el?.scrollIntoView({ behavior: "smooth", block: "center" });
    } catch (error) {
      if (import.meta.env.DEV) {
        console.debug("[InlineDiffEditor] scrollToEdit failed", { editId, error });
      }
    }
  }, [editIdToIndexMap, editIndexToRowIndexMap, shouldVirtualize, virtualizer]);

  useEffect(() => {
    // Only auto-scroll when entering diff review (or when the underlying content changes),
    // to avoid jumpiness while the user is actively reviewing.
    if (initialAutoScrollDoneRef.current) return;

    const firstPendingId = pendingEdits.find((e) => e.status === "pending")?.id;
    const firstAnyId = pendingEdits[0]?.id;
    const targetId = firstPendingId ?? firstAnyId;
    if (!targetId) return;

    initialAutoScrollDoneRef.current = true;

    const timer = setTimeout(() => {
      scrollToEdit(targetId);
    }, 100);

    return () => clearTimeout(timer);
  }, [pendingEdits, scrollToEdit]);

  useImperativeHandle(ref, () => ({ scrollToEdit }), [scrollToEdit]);

  const renderSegment = useCallback((segment: ReviewDiffSegment, index: number) => {
    if (segment.type === "equal") {
      return (
        <span key={index} className="text-[hsl(var(--text-primary))]">
          {segment.text}
        </span>
      );
    }

    const edit = segment.editIndex != null ? pendingEdits[segment.editIndex] : undefined;
    const editId = edit?.id;
    const status = edit?.status;
    const isActive = !!activeEditId && !!editId && activeEditId === editId;

    const statusClass = status === "accepted"
      ? "opacity-75"
      : status === "rejected"
        ? "opacity-45"
        : "";

    const activeClass = isActive
      ? "outline outline-2 outline-[hsl(var(--accent-primary)/0.55)] outline-offset-2"
      : "";

    const clickable = editId && onSelectEdit ? "cursor-pointer" : "";
    const onClick = editId && onSelectEdit ? () => onSelectEdit(editId) : undefined;
    const onKeyDown = editId && onSelectEdit
      ? (event: ReactKeyboardEvent<HTMLSpanElement>) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            onSelectEdit(editId);
          }
        }
      : undefined;
    const interactiveProps = editId && onSelectEdit
      ? {
          role: "button" as const,
          tabIndex: 0,
          onKeyDown,
          "aria-label": `Locate change ${editId}`,
        }
      : {};

    if (segment.type === "delete") {
      return (
        <span
          key={index}
          data-edit-id={editId}
          data-status={status}
          onClick={onClick}
          {...interactiveProps}
          className={cn(
            "diff-remove rounded-sm border-l border-[hsl(var(--diff-remove-text)/0.75)] px-1.5 py-0.5",
            statusClass,
            activeClass,
            clickable
          )}
        >
          {segment.text}
        </span>
      );
    }

    if (segment.type === "insert") {
      return (
        <span
          key={index}
          data-edit-id={editId}
          data-status={status}
          onClick={onClick}
          {...interactiveProps}
          className={cn(
            "diff-add rounded-sm border-l border-[hsl(var(--diff-add-text)/0.75)] px-1.5 py-0.5",
            statusClass,
            activeClass,
            clickable
          )}
        >
          {segment.text}
        </span>
      );
    }

    return (
      <span
        key={index}
        data-edit-id={editId}
        data-status={status}
        onClick={onClick}
        {...interactiveProps}
        className={cn("inline-flex rounded-sm overflow-hidden", statusClass, activeClass, clickable)}
      >
        <span className="diff-remove border-l border-[hsl(var(--diff-remove-text)/0.75)] px-1.5 py-0.5">
          {segment.text}
        </span>
        <span className="diff-add border-r border-[hsl(var(--diff-add-text)/0.75)] px-1.5 py-0.5">
          {segment.newText}
        </span>
      </span>
    );
  }, [activeEditId, onSelectEdit, pendingEdits]);

  const renderRow = useCallback((row: DiffRow) => {
    return (
      <div className="whitespace-pre-wrap leading-[1.8] text-base">
        {row.segments.map((segment, index) => renderSegment(segment, index))}
      </div>
    );
  }, [renderSegment]);

  if (shouldVirtualize) {
    return (
      <div ref={containerRef} className="flex-1 min-h-0 overflow-hidden bg-[hsl(var(--bg-primary))]">
        <div ref={scrollContainerRef} className="h-full overflow-auto px-6 pb-4 pt-2">
          <div className="relative w-full" style={{ height: `${virtualizer.getTotalSize()}px` }}>
            {virtualizer.getVirtualItems().map((virtualRow) => {
              const row = diffRows[virtualRow.index];
              if (!row) return null;

              return (
                <div
                  key={row.id}
                  data-index={virtualRow.index}
                  ref={virtualizer.measureElement}
                  style={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    width: "100%",
                    transform: `translateY(${virtualRow.start}px)`,
                  }}
                >
                  {renderRow(row)}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="flex-1 min-h-0 overflow-auto bg-[hsl(var(--bg-primary))] px-6 pb-4 pt-2">
      <div className="whitespace-pre-wrap leading-[1.8] text-base">
        {diffSegments.map((segment, index) => renderSegment(segment, index))}
      </div>
    </div>
  );
});
