/**
 * React hook for streaming agent requests.
 *
 * Provides state management and methods for:
 * - Starting a streaming request
 * - Tracking thinking/content/tool calls state
 * - Cancelling requests
 * - Resetting state
 * 
 * Key feature: Supports message segments - each content block before/after
 * tool calls is treated as a separate segment, enabling proper chat UI display.
 */

import { useState, useCallback, useEffect, useRef } from "react";
import { produce } from "immer";
import i18n from "../lib/i18n";
import { useImmer } from "use-immer";
import { sendSteeringRequest, streamAgentRequest } from "../lib/agentApi";
import type {
  AgentContextItem,
  AgentRequest,
  AgentStreamState,
  Conflict,
  ConflictType,
  ApplyAction,
  SSEHandoffData,
  SSERoutingMetadata,
  SSEWorkflowCompleteData,
  SSEWorkflowStoppedData,
  ToolCall,
} from "../types";

/** Parallel task state for tracking multi-agent execution */
interface ParallelTask {
  id: string;
  type: string;
  description: string;
  status: "pending" | "running" | "completed" | "failed";
  resultPreview?: string;
  error?: string;
}

/** Parallel execution state tracking */
interface ParallelExecutionState {
  executionId: string;
  tasks: Map<string, ParallelTask>;
  startTime: number;
}

/** A segment of assistant response (thinking, text content, or tool calls) */
export interface MessageSegment {
  id: string;
  type: "thinking" | "content" | "tool_calls";
  content?: string;
  toolCalls?: ToolCall[];
  isStreaming?: boolean;
  isComplete?: boolean;
  timestamp?: Date;
}

export interface StreamCompletionMeta {
  assistantMessageId?: string;
  sessionId?: string;
}

export interface UseAgentStreamOptions {
  /**
   * Flush interval (ms) for streaming content batching.
   *
   * Default: 33ms.
   * Set to 0 to disable batching (flush every chunk).
   */
  contentFlushIntervalMs?: number;
  /** Called when streaming starts */
  onStart?: () => void;
  /** Called when context items are received */
  onContext?: (items: AgentContextItem[], tokenCount?: number) => void;
  /** Called when AI is thinking (with message) */
  onThinking?: (message: string) => void;
  /** Called when thinking content arrives */
  onThinkingContent?: (content: string, isComplete: boolean) => void;
  /** Called when a new message segment starts (for adding to chat) */
  onSegmentStart?: (segment: MessageSegment) => void;
  /** Called when segment content updates (for streaming text) */
  onSegmentUpdate?: (segmentId: string, content: string) => void;
  /** Called when tool calls segment updates */
  onSegmentUpdateToolCalls?: (segmentId: string, toolCalls: ToolCall[]) => void;
  /** Called when a segment completes */
  onSegmentEnd?: (segmentId: string) => void;
  /**
   * Called when content is flushed to React state.
   *
   * Note: To reduce re-renders, streaming content may be batched (e.g. flushed every ~33ms),
   * so `chunk` can contain multiple SSE chunks concatenated together.
   */
  onContent?: (chunk: string, fullContent: string) => void;
  /** Called when a conflict is detected */
  onConflict?: (conflict: Conflict) => void;
  /** Called when streaming completes successfully */
  onComplete?: (
    segments: MessageSegment[],
    applyAction: ApplyAction | null,
    completionMeta?: StreamCompletionMeta,
  ) => void;
  /** Called when an error occurs */
  onError?: (error: string, code?: string, retryable?: boolean) => void;
  /** Called when AI calls a tool */
  onToolCall?: (toolName: string, args: Record<string, unknown>, toolUseId?: string) => void;
  /** Called when tool execution completes */
  onToolResult?: (
    toolName: string,
    status: string,
    result?: Record<string, unknown>,
    error?: string,
    toolUseId?: string,
  ) => void;
  /** Called when a file is created (for auto-select) */
  onFileCreated?: (fileId: string, fileType: string, title: string) => void;
  /** Called when file content chunk is received (streaming) */
  onFileContent?: (fileId: string, chunk: string) => void;
  /** Called when file content streaming ends */
  onFileContentEnd?: (fileId: string) => void;
  /** Called when file editing starts */
  onFileEditStart?: (
    fileId: string,
    title: string,
    totalEdits: number,
    fileType?: string,
  ) => void;
  /** Called when a single edit is applied */
  onFileEditApplied?: (
    fileId: string,
    editIndex: number,
    op: string,
    oldPreview?: string,
    newPreview?: string,
    success?: boolean,
    error?: string,
  ) => void;
  /** Called when file editing ends */
  onFileEditEnd?: (
    fileId: string,
    editsApplied: number,
    newLength: number,
    newContent?: string,
    originalContent?: string,
    fileType?: string,
    title?: string,
  ) => void;
  /** Called when a skill is matched */
  onSkillMatched?: (skillId: string, skillName: string, matchedTrigger: string) => void;
  /** Called when multiple skills are matched (multi-skill activation) */
  onSkillsMatched?: (skills: Array<{ id: string; name: string; trigger: string; confidence: number }>) => void;
  /** Called when an agent is selected by the router */
  onAgentSelected?: (
    agentType: string,
    agentName: string,
    iteration?: number,
    maxIterations?: number,
    remaining?: number
  ) => void;
  /** Called when iteration limit is exhausted */
  onIterationExhausted?: (
    layer: "collaboration" | "tool_call",
    iterationsUsed: number,
    maxIterations: number,
    reason: string,
    lastAgent?: string
  ) => void;
  /** Called when router starts thinking */
  onRouterThinking?: (message: string) => void;
  /** Called when router makes a decision */
  onRouterDecided?: (
    initialAgent: string,
    workflowPlan: string,
    workflowAgents: string[],
    routingMetadata?: SSERoutingMetadata
  ) => void;
  /** Called when workflow hands off to another agent */
  onHandoff?: (data: SSEHandoffData) => void;
  /** Called when workflow stops for clarification */
  onWorkflowStopped?: (data: SSEWorkflowStoppedData) => void;
  /** Called when workflow completes successfully */
  onWorkflowComplete?: (data: SSEWorkflowCompleteData) => void;
  /** Called when session starts */
  onSessionStarted?: (sessionId: string) => void;
  /** Called when parallel execution starts */
  onParallelStart?: (executionId: string, taskCount: number, descriptions: string[]) => void;
  /** Called when a parallel task starts */
  onParallelTaskStart?: (executionId: string, taskId: string, taskType: string, description: string) => void;
  /** Called when a parallel task completes */
  onParallelTaskEnd?: (executionId: string, taskId: string, status: string, result?: unknown, error?: string) => void;
  /** Called when all parallel tasks complete */
  onParallelEnd?: (executionId: string, total: number, completed: number, failed: number, durationMs: number) => void;
  /** Called when steering message is received */
  onSteeringReceived?: (messageId: string, preview: string) => void;
  /** Called when compaction starts */
  onCompactionStart?: (tokensBefore: number, messagesCount: number) => void;
  /** Called when compaction completes */
  onCompactionDone?: (tokensAfter: number, messagesRemoved: number, summaryPreview: string) => void;
}

export interface UseAgentStreamReturn {
  /** Current stream state */
  state: AgentStreamState;
  /** All message segments from this stream */
  segments: MessageSegment[];
  /** Start streaming request */
  startStream: (request: Omit<AgentRequest, "project_id">) => void;
  /** Cancel ongoing stream */
  cancel: () => void;
  /** Reset state to initial */
  reset: () => void;
  /** Whether currently streaming */
  isStreaming: boolean;
  /** Whether waiting for thinking step */
  isThinking: boolean;
  /** Current thinking content */
  thinkingContent: string;
  /** Current content (cumulative) */
  content: string;
  /** Detected conflicts */
  conflicts: Conflict[];
  /** Error message if any */
  error: string | null;
  /** Backend error code if provided by SSE error event */
  errorCode: string | null;
  /** Current session ID for steering */
  sessionId: string | null;
  /** Send a steering message to the active session */
  sendSteeringMessage: (message: string) => Promise<void>;
}

const initialState: AgentStreamState = {
  isStreaming: false,
  isThinking: false,
  thinkingMessage: "",
  thinkingContent: "",
  content: "",
  conflicts: [],
  contextItems: [],
  contextTokenCount: null,
  error: null,
  errorCode: null,
  applyAction: null,
  refs: [],
  toolCalls: [],
};

// Flush streaming content to React state at most once per interval.
// This avoids re-rendering on every token/chunk, which can make the UI
// appear "slow" even when the backend streams quickly.
const STREAM_CONTENT_FLUSH_INTERVAL_MS = 33;

export function useAgentStream(
  projectId: string,
  options: UseAgentStreamOptions = {},
): UseAgentStreamReturn {
  const [state, setState] = useState<AgentStreamState>(initialState);
  const [segments, updateSegmentsState] = useImmer<MessageSegment[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const errorTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Ref to track current segments value for onComplete callback (avoids stale closure)
  // This is updated synchronously alongside state updates using produce()
  const segmentsRef = useRef<MessageSegment[]>([]);

  // Helper to update both state and ref synchronously - ensures ref is always current
  const updateSegmentsSync = useCallback((updater: (draft: MessageSegment[]) => void) => {
    segmentsRef.current = produce(segmentsRef.current, updater);
    updateSegmentsState(updater);
  }, [updateSegmentsState]);

  // Track current segment for streaming
  const currentSegmentIdRef = useRef<string | null>(null);
  const currentSegmentContentRef = useRef<string>("");
  const pendingToolCallsRef = useRef<ToolCall[]>([]);

  // Streaming content batching (frontend perf)
  const contentRef = useRef<string>("");
  const pendingContentChunkRef = useRef<string>("");
  const flushTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Track current tool calls segment (for live updates)
  const currentToolCallsSegmentIdRef = useRef<string | null>(null);

  // Track if onComplete has been called (prevent duplicate calls)
  const onCompleteCalledRef = useRef<boolean>(false);

  // Session and parallel execution refs
  const sessionIdRef = useRef<string | null>(null);
  const parallelStateRef = useRef<ParallelExecutionState | null>(null);
  const streamEpochRef = useRef(0);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const currentProjectIdRef = useRef(projectId);
  const lastProjectIdRef = useRef(projectId);

  useEffect(() => {
    currentProjectIdRef.current = projectId;
  }, [projectId]);

  const {
    contentFlushIntervalMs,
    onStart,
    onContext: onContextOption,
    onThinking: onThinkingOption,
    onThinkingContent: onThinkingContentOption,
    onSegmentStart,
    onSegmentUpdate,
    onSegmentUpdateToolCalls,
    onSegmentEnd,
    onContent,
    onConflict,
    onComplete,
    onError,
    onToolCall,
    onToolResult,
    onFileCreated,
    onFileContent,
    onFileContentEnd,
    onFileEditStart,
    onFileEditApplied,
    onFileEditEnd,
    onSkillMatched,
    onSkillsMatched,
    onAgentSelected,
    onIterationExhausted,
    onRouterThinking,
    onRouterDecided,
    onHandoff,
    onWorkflowStopped,
    onWorkflowComplete,
    onSessionStarted,
    onParallelStart,
    onParallelTaskStart,
    onParallelTaskEnd,
    onParallelEnd,
    onSteeringReceived,
    onCompactionStart,
    onCompactionDone,
  } = options;

  const flushIntervalMs =
    Number.isFinite(contentFlushIntervalMs)
      ? Math.max(0, Math.floor(contentFlushIntervalMs as number))
      : STREAM_CONTENT_FLUSH_INTERVAL_MS;

  /** Clear any scheduled content flush timer */
  const clearFlushTimer = useCallback(() => {
    if (flushTimerRef.current) {
      clearTimeout(flushTimerRef.current);
      flushTimerRef.current = null;
    }
  }, []);

  // Cleanup timers on unmount to avoid setState after unmount.
  useEffect(() => {
    return () => {
      clearFlushTimer();
      if (errorTimeoutRef.current) {
        clearTimeout(errorTimeoutRef.current);
        errorTimeoutRef.current = null;
      }
    };
  }, [clearFlushTimer]);

  /** 清除错误消息和 timeout */
  const clearError = useCallback(() => {
    // 清除之前的 timeout
    if (errorTimeoutRef.current) {
      clearTimeout(errorTimeoutRef.current);
      errorTimeoutRef.current = null;
    }
    // 清除错误状态
    setError(null);
    setErrorCode(null);
  }, []);

  /**
   * Flush pending streamed content into React state / segments.
   *
   * Important:
   * - This function is called frequently; keep it minimal.
   * - It uses refs to avoid string concatenation on every token causing re-renders.
   */
  const flushPendingContent = useCallback(() => {
    clearFlushTimer();

    const chunk = pendingContentChunkRef.current;
    if (!chunk) return;

    pendingContentChunkRef.current = "";

    const segmentId = currentSegmentIdRef.current;
    const segmentContent = currentSegmentContentRef.current;
    const fullContent = contentRef.current;

    if (segmentId) {
      updateSegmentsSync(draft => {
        const seg = draft.find(s => s.id === segmentId);
        if (seg) {
          seg.content = segmentContent;
        }
      });
      onSegmentUpdate?.(segmentId, segmentContent);
    }

    setState((prev) => {
      // Use ref value for content to avoid repeated string concatenations.
      onContent?.(chunk, fullContent);
      return {
        ...prev,
        isThinking: false,
        content: fullContent,
      };
    });
  }, [clearFlushTimer, onContent, onSegmentUpdate, updateSegmentsSync]);

  /** Schedule a flush if not already scheduled */
  const scheduleContentFlush = useCallback(() => {
    if (flushIntervalMs <= 0) {
      flushPendingContent();
      return;
    }
    if (flushTimerRef.current) return;

    flushTimerRef.current = setTimeout(() => {
      flushTimerRef.current = null;
      flushPendingContent();
    }, flushIntervalMs);
  }, [flushIntervalMs, flushPendingContent]);

  // Prevent session_id reuse across different projects.
  useEffect(() => {
    if (lastProjectIdRef.current === projectId) {
      return;
    }

    lastProjectIdRef.current = projectId;
    streamEpochRef.current += 1;
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    clearFlushTimer();
    pendingContentChunkRef.current = "";
    contentRef.current = "";
    sessionIdRef.current = null;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional reset on project switch
    setSessionId(null);
    parallelStateRef.current = null;
    setState((prev) => ({
      ...prev,
      isStreaming: false,
      isThinking: false,
    }));
  }, [projectId, clearFlushTimer]);

  /** 设置错误消息，3秒后自动清除 */
  const showError = useCallback((message: string) => {
    // 清除之前的 timeout
    if (errorTimeoutRef.current) {
      clearTimeout(errorTimeoutRef.current);
    }
    // 设置新错误
    setError(message);
    // 3秒后自动清除
    errorTimeoutRef.current = setTimeout(() => {
      setError(null);
      errorTimeoutRef.current = null;
    }, 3000);
  }, []);

  /** Generate unique segment ID */
  const generateSegmentId = () => `segment-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

  /** Start a new content segment */
  const startContentSegment = useCallback(() => {
    // Ensure any pending content is flushed before ending the previous segment.
    flushPendingContent();

    // End previous segment if exists
    if (currentSegmentIdRef.current) {
      onSegmentEnd?.(currentSegmentIdRef.current);
    }
    
    const segmentId = generateSegmentId();
    currentSegmentIdRef.current = segmentId;
    currentSegmentContentRef.current = "";
    
    const segment: MessageSegment = {
      id: segmentId,
      type: "content",
      content: "",
      isStreaming: true,
    };
    
    updateSegmentsSync(draft => { draft.push(segment); });
    onSegmentStart?.(segment);

    return segmentId;
  // updateSegmentsSync is stable from useImmer, included to satisfy lint
  }, [flushPendingContent, onSegmentStart, onSegmentEnd, updateSegmentsSync]);

  /** Create or update tool calls segment (called on each tool call) */
  const upsertToolCallsSegment = useCallback((toolCalls: ToolCall[], isComplete: boolean = false) => {
    // End current content segment if exists and this is the first tool call
    if (!currentToolCallsSegmentIdRef.current && currentSegmentIdRef.current) {
      onSegmentEnd?.(currentSegmentIdRef.current);
      currentSegmentIdRef.current = null;
    }

    if (!currentToolCallsSegmentIdRef.current) {
      // Create new tool calls segment
      const segmentId = generateSegmentId();
      currentToolCallsSegmentIdRef.current = segmentId;

      const segment: MessageSegment = {
        id: segmentId,
        type: "tool_calls",
        toolCalls,
        isStreaming: !isComplete, // streaming until all tool calls complete
      };

      updateSegmentsSync(draft => { draft.push(segment); });
      onSegmentStart?.(segment);
    } else {
      // Update existing segment
      const segmentId = currentToolCallsSegmentIdRef.current;
      updateSegmentsSync(draft => {
        const seg = draft.find(s => s.id === segmentId);
        if (seg) {
          seg.toolCalls = toolCalls;
          seg.isStreaming = !isComplete;
        }
      });
      // Notify ChatPanel to update streamRenderItems
      onSegmentUpdateToolCalls?.(segmentId, toolCalls);
    }

    // If complete, end the segment
    if (isComplete && currentToolCallsSegmentIdRef.current) {
      onSegmentEnd?.(currentToolCallsSegmentIdRef.current);
      currentToolCallsSegmentIdRef.current = null;
    }
  // updateSegmentsSync is stable from useImmer, included to satisfy lint
  }, [onSegmentStart, onSegmentEnd, onSegmentUpdateToolCalls, updateSegmentsSync]);

  /**
   * Best-effort: resolve pending control tool calls when workflow control events
   * (handoff/workflow_stopped) arrive before a tool_result callback.
   *
   * This keeps frontend tool-call lifecycle robust against backend event ordering
   * differences and prevents stale pending tool cards.
   */
  const resolvePendingControlTool = useCallback((
    toolName: "handoff_to_agent" | "request_clarification",
    status: "success" | "error" = "success",
    result?: Record<string, unknown>,
    error?: string,
  ) => {
    let updated = false;
    const nextPending = pendingToolCallsRef.current.map((tc) => {
      if (!updated && tc.tool_name === toolName && tc.status === "pending") {
        updated = true;
        return { ...tc, status, result, error };
      }
      return tc;
    });

    if (!updated) {
      return;
    }

    pendingToolCallsRef.current = nextPending;
    const allDone = nextPending.every(tc => tc.status !== "pending");
    upsertToolCallsSegment(nextPending, allDone);
    if (allDone && nextPending.length > 0) {
      pendingToolCallsRef.current = [];
    }

    setState((prev) => {
      let stateUpdated = false;
      return {
        ...prev,
        toolCalls: prev.toolCalls.map((tc) => {
          if (!stateUpdated && tc.tool_name === toolName && tc.status === "pending") {
            stateUpdated = true;
            return { ...tc, status, result, error };
          }
          return tc;
        }),
      };
    });
  }, [upsertToolCallsSegment]);

  /**
   * Send a steering message to the active session.
   */
  const sendSteeringMessage = useCallback(async (message: string) => {
    const currentSessionId = sessionIdRef.current;
    if (!currentSessionId) {
      throw new Error("No active session for steering");
    }

    await sendSteeringRequest(currentSessionId, message);
  }, []);

  /**
   * Reset state to initial values.
   */
  const reset = useCallback(() => {
    streamEpochRef.current += 1;
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    clearFlushTimer();
    pendingContentChunkRef.current = "";
    contentRef.current = "";
    // 清除错误和 timeout
    clearError();
    setState(initialState);
    updateSegmentsSync(draft => { draft.length = 0; });
    currentSegmentIdRef.current = null;
    currentToolCallsSegmentIdRef.current = null;
    currentSegmentContentRef.current = "";
    pendingToolCallsRef.current = [];
    sessionIdRef.current = null;
    setSessionId(null);
    parallelStateRef.current = null;
    onCompleteCalledRef.current = false;
  // updateSegmentsSync is stable from useImmer, included to satisfy lint
  }, [clearError, clearFlushTimer, updateSegmentsSync]);

  /**
   * Cancel ongoing stream.
   */
  const cancel = useCallback(() => {
    streamEpochRef.current += 1;
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    // Flush what we already received so the UI doesn't "lose" the last chunk.
    flushPendingContent();
    clearFlushTimer();
    
    // End current segment
    if (currentSegmentIdRef.current) {
      onSegmentEnd?.(currentSegmentIdRef.current);
      currentSegmentIdRef.current = null;
    }
    
    setState((prev) => ({
      ...prev,
      isStreaming: false,
      isThinking: false,
    }));
  }, [clearFlushTimer, flushPendingContent, onSegmentEnd]);

  /**
   * Start a streaming request.
   */
  const startStream = useCallback(
    (request: Omit<AgentRequest, "project_id">) => {
      const streamProjectId = projectId;
      const streamEpoch = ++streamEpochRef.current;
      currentProjectIdRef.current = streamProjectId;

      // Cancel any existing stream
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      // 清除之前的错误
      clearError();
      clearFlushTimer();
      pendingContentChunkRef.current = "";
      contentRef.current = "";

      // Reset state
      setState({
        ...initialState,
        isStreaming: true,
        isThinking: true,
        thinkingMessage: i18n.t('chat:stream.processing'),
      });
      updateSegmentsSync(draft => { draft.length = 0; });
      currentSegmentIdRef.current = null;
      currentSegmentContentRef.current = "";
      pendingToolCallsRef.current = [];
      currentToolCallsSegmentIdRef.current = null;
      onCompleteCalledRef.current = false;

      onStart?.();

      const isStaleEvent = () =>
        streamEpoch !== streamEpochRef.current
        || currentProjectIdRef.current !== streamProjectId;

      // Start streaming
      abortControllerRef.current = streamAgentRequest(
        {
          project_id: streamProjectId,
          message: request.message,
          session_id: request.session_id ?? sessionIdRef.current ?? undefined,
          selected_text: request.selected_text,
          context_before: request.context_before,
          context_after: request.context_after,
          outline_id: request.outline_id,
          metadata: request.metadata,
        },
        {
          onThinking: (message) => {
            if (isStaleEvent()) return;
            setState((prev) => ({
              ...prev,
              isThinking: true,
              thinkingMessage: message,
            }));

            // 调用外部回调
            onThinkingOption?.(message);
          },

          onThinkingContent: (content, isComplete) => {
            if (isStaleEvent()) return;
            // 不再累积到 state，只通过回调处理，避免重复
            // 调用外部回调
            onThinkingContentOption?.(content, isComplete ?? false);
          },

          onContext: (items, tokenCount) => {
            if (isStaleEvent()) return;
            onContextOption?.(items, tokenCount);
            setState((prev) => ({
              ...prev,
              contextItems: items,
              contextTokenCount: tokenCount ?? null,
            }));
          },

          onContentStart: () => {
            if (isStaleEvent()) return;
            flushPendingContent();
            setState((prev) => ({
              ...prev,
              isThinking: false,
            }));
            // Start a new content segment
            startContentSegment();
          },

          onContent: (text) => {
            if (isStaleEvent()) return;
            // Ensure we have a content segment
            if (!currentSegmentIdRef.current) {
              setState((prev) => ({
                ...prev,
                isThinking: false,
              }));
              startContentSegment();
            }
            
            // Batch content updates for smoother UI.
            currentSegmentContentRef.current += text;
            contentRef.current += text;
            pendingContentChunkRef.current += text;
            scheduleContentFlush();
          },

          onContentEnd: () => {
            if (isStaleEvent()) return;
            flushPendingContent();
            // Mark current segment as done streaming
            if (currentSegmentIdRef.current) {
              const segmentId = currentSegmentIdRef.current;
              updateSegmentsSync(draft => {
                const seg = draft.find(s => s.id === segmentId);
                if (seg) {
                  seg.isStreaming = false;
                }
              });
            }
          },

          onToolCall: (toolName, args, toolUseId) => {
            if (isStaleEvent()) return;
            flushPendingContent();
            const toolCall: ToolCall = {
              id: (toolUseId && toolUseId.trim()) || Date.now().toString(),
              tool_name: toolName,
              arguments: args,
              status: "pending",
            };
            
            pendingToolCallsRef.current.push(toolCall);
            
            // Immediately create/update tool calls segment with pending status
            upsertToolCallsSegment([...pendingToolCallsRef.current], false);
            
            setState((prev) => ({
              ...prev,
              toolCalls: [...prev.toolCalls, toolCall],
            }));
            if (toolUseId) {
              onToolCall?.(toolName, args, toolUseId);
            } else {
              onToolCall?.(toolName, args);
            }
          },

          onToolResult: (toolName, status, result, error, toolUseId) => {
            if (isStaleEvent()) return;
            flushPendingContent();
            const normalizedToolUseId = (toolUseId || "").trim();
            // Update tool call status (prefer tool_use_id match, fallback to first pending by name)
            let updated = false;
            const updatedToolCalls = pendingToolCallsRef.current.map((tc) => {
              const idMatched = normalizedToolUseId ? tc.id === normalizedToolUseId : false;
              const nameMatched =
                !normalizedToolUseId && tc.tool_name === toolName && tc.status === "pending";
              if (!updated && (idMatched || nameMatched) && tc.status === "pending") {
                updated = true;
                return {
                  ...tc,
                  status: status as "success" | "error",
                  result,
                  error,
                };
              }
              return tc;
            });
            pendingToolCallsRef.current = updatedToolCalls;
            
            // Check if all pending tool calls are done
            const allDone = updatedToolCalls.every(tc => tc.status !== "pending");
            
            // Update the tool calls segment with new status
            upsertToolCallsSegment(updatedToolCalls, allDone);
            
            if (allDone && updatedToolCalls.length > 0) {
              // Clear pending tool calls for next round
              pendingToolCallsRef.current = [];
            }
            
            setState((prev) => {
              let stateUpdated = false;
              return {
                ...prev,
                toolCalls: prev.toolCalls.map((tc) => {
                  const idMatched = normalizedToolUseId ? tc.id === normalizedToolUseId : false;
                  const nameMatched =
                    !normalizedToolUseId && tc.tool_name === toolName && tc.status === "pending";
                  if (!stateUpdated && (idMatched || nameMatched) && tc.status === "pending") {
                    stateUpdated = true;
                    return {
                      ...tc,
                      status: status as "success" | "error",
                      result,
                      error,
                    };
                  }
                  return tc;
                }),
              };
            });
            if (toolUseId) {
              onToolResult?.(toolName, status, result, error, toolUseId);
            } else {
              onToolResult?.(toolName, status, result, error);
            }
          },

          onFileCreated: (fileId, fileType, title) => {
            if (isStaleEvent()) return;
            onFileCreated?.(fileId, fileType, title);
          },

          onFileContent: (fileId, chunk) => {
            if (isStaleEvent()) return;
            onFileContent?.(fileId, chunk);
          },

          onFileContentEnd: (fileId) => {
            if (isStaleEvent()) return;
            onFileContentEnd?.(fileId);
          },

          onFileEditStart: (fileId, title, totalEdits, fileType) => {
            if (isStaleEvent()) return;
            onFileEditStart?.(fileId, title, totalEdits, fileType);
          },

          onFileEditApplied: (fileId, editIndex, op, oldPreview, newPreview, success, error) => {
            if (isStaleEvent()) return;
            onFileEditApplied?.(fileId, editIndex, op, oldPreview, newPreview, success, error);
          },

          onFileEditEnd: (fileId, editsApplied, newLength, newContent, originalContent, fileType, title) => {
            if (isStaleEvent()) return;
            onFileEditEnd?.(
              fileId,
              editsApplied,
              newLength,
              newContent,
              originalContent,
              fileType,
              title,
            );
          },

          onSkillMatched: (skillId, skillName, matchedTrigger) => {
            if (isStaleEvent()) return;
            onSkillMatched?.(skillId, skillName, matchedTrigger);
          },

          onSkillsMatched: (skills) => {
            if (isStaleEvent()) return;
            onSkillsMatched?.(skills);
          },

          onAgentSelected: (agentType, agentName, iteration, maxIterations, remaining) => {
            if (isStaleEvent()) return;
            onAgentSelected?.(agentType, agentName, iteration, maxIterations, remaining);
          },

          onIterationExhausted: (layer, iterationsUsed, maxIterations, reason, lastAgent) => {
            if (isStaleEvent()) return;
            onIterationExhausted?.(layer, iterationsUsed, maxIterations, reason, lastAgent);
          },

          onRouterThinking: (message) => {
            if (isStaleEvent()) return;
            setState((prev) => ({
              ...prev,
              isThinking: true,
              thinkingMessage: message,
            }));
            onRouterThinking?.(message);
          },

          onRouterDecided: (initialAgent, workflowPlan, workflowAgents, routingMetadata) => {
            if (isStaleEvent()) return;
            setState((prev) => ({
              ...prev,
              isThinking: false,
            }));
            onRouterDecided?.(initialAgent, workflowPlan, workflowAgents, routingMetadata);
          },

          onHandoff: (data) => {
            if (isStaleEvent()) return;
            resolvePendingControlTool(
              "handoff_to_agent",
              "success",
              data as unknown as Record<string, unknown>,
            );
            onHandoff?.(data);
          },

          onWorkflowStopped: (data) => {
            if (isStaleEvent()) return;
            flushPendingContent();
            if (data.reason === "clarification_needed") {
              resolvePendingControlTool(
                "request_clarification",
                "success",
                data as unknown as Record<string, unknown>,
              );
            }
            setState((prev) => ({
              ...prev,
              isStreaming: false,
              isThinking: false,
            }));
            onWorkflowStopped?.(data);
          },

          onWorkflowComplete: (data) => {
            if (isStaleEvent()) return;
            flushPendingContent();
            setState((prev) => ({
              ...prev,
              isStreaming: false,
              isThinking: false,
            }));
            onWorkflowComplete?.(data);
          },

          onSessionStarted: (session_id) => {
            if (isStaleEvent()) return;
            sessionIdRef.current = session_id;
            setSessionId(session_id);
            onSessionStarted?.(session_id);
          },

          onParallelStart: (execution_id, task_count, task_descriptions) => {
            if (isStaleEvent()) return;
            parallelStateRef.current = {
              executionId: execution_id,
              tasks: new Map(),
              startTime: Date.now(),
            };
            onParallelStart?.(execution_id, task_count, task_descriptions);
          },

          onParallelTaskStart: (execution_id, task_id, task_type, description) => {
            if (isStaleEvent()) return;
            if (parallelStateRef.current) {
              parallelStateRef.current.tasks.set(task_id, {
                id: task_id,
                type: task_type,
                description,
                status: "running",
              });
            }
            onParallelTaskStart?.(execution_id, task_id, task_type, description);
          },

          onParallelTaskEnd: (execution_id, task_id, status, result_preview, error) => {
            if (isStaleEvent()) return;
            if (parallelStateRef.current) {
              const task = parallelStateRef.current.tasks.get(task_id);
              if (task) {
                task.status = status as "completed" | "failed";
                task.resultPreview = result_preview;
                task.error = error;
              }
            }
            onParallelTaskEnd?.(execution_id, task_id, status, result_preview, error);
          },

          onParallelEnd: (execution_id, total_tasks, completed, failed, duration_ms) => {
            if (isStaleEvent()) return;
            onParallelEnd?.(execution_id, total_tasks, completed, failed, duration_ms);
            parallelStateRef.current = null;
          },

          onSteeringReceived: (message_id, preview) => {
            if (isStaleEvent()) return;
            onSteeringReceived?.(message_id, preview);
          },

          onCompactionStart: (tokens_before, messages_count) => {
            if (isStaleEvent()) return;
            onCompactionStart?.(tokens_before, messages_count);
          },

          onCompactionDone: (tokens_after, messages_removed, summary_preview) => {
            if (isStaleEvent()) return;
            onCompactionDone?.(tokens_after, messages_removed, summary_preview);
          },

          onConflict: (conflictData) => {
            if (isStaleEvent()) return;
            const conflict: Conflict = {
              type: conflictData.type as ConflictType,
              severity: conflictData.severity as "low" | "medium" | "high",
              title: conflictData.title,
              description: conflictData.description,
              suggestions: conflictData.suggestions,
              references: [],
            };

            setState((prev) => ({
              ...prev,
              conflicts: [...prev.conflicts, conflict],
            }));

            onConflict?.(conflict);
          },

          onDone: (data) => {
            if (isStaleEvent()) return;
            flushPendingContent();
            const applyAction = data.apply_action as ApplyAction | undefined;

            // End current segment
            if (currentSegmentIdRef.current) {
              const segmentId = currentSegmentIdRef.current;
              updateSegmentsSync(draft => {
                const seg = draft.find(s => s.id === segmentId);
                if (seg) {
                  seg.isStreaming = false;
                }
              });
              onSegmentEnd?.(segmentId);
              currentSegmentIdRef.current = null;
            }

            setState((prev) => {
              return {
                ...prev,
                isStreaming: false,
                isThinking: false,
                applyAction: applyAction || null,
                refs: data.refs || [],
              };
            });

            // Get final segments for callback
            // 🔥 防止重复调用 onComplete（在回调内部也要检查，因为 React 可能多次调用此回调）
            // Use segmentsRef.current to avoid stale closure issue with segments
            if (!onCompleteCalledRef.current) {
              onCompleteCalledRef.current = true;
              const completionMeta = {
                assistantMessageId:
                  typeof data.assistant_message_id === "string" && data.assistant_message_id.trim()
                    ? data.assistant_message_id
                    : undefined,
                sessionId:
                  typeof data.session_id === "string" && data.session_id.trim()
                    ? data.session_id
                    : undefined,
              };
              if (completionMeta.assistantMessageId || completionMeta.sessionId) {
                onComplete?.(segmentsRef.current, applyAction || null, completionMeta);
              } else {
                onComplete?.(segmentsRef.current, applyAction || null);
              }
            }
          },

          onError: (message, code, retryable) => {
            if (isStaleEvent()) return;
            flushPendingContent();
            // End current segment
            if (currentSegmentIdRef.current) {
              onSegmentEnd?.(currentSegmentIdRef.current);
              currentSegmentIdRef.current = null;
            }

            // 重置 onComplete 调用标志
            onCompleteCalledRef.current = false;

            // 使用独立的error状态管理，3秒后自动清除
            showError(message);
            setErrorCode(code ?? null);

            setState((prev) => ({
              ...prev,
              isStreaming: false,
              isThinking: false,
              error: message,
              errorCode: code ?? null,
            }));

            if (code !== undefined || retryable !== undefined) {
              onError?.(message, code, retryable);
            } else {
              onError?.(message);
            }
          },
        },
      );
    },
    [
      projectId,
      onStart,
      onSegmentEnd,
      onConflict,
      onComplete,
      onError,
      onToolCall,
      onToolResult,
      onFileCreated,
      onFileContent,
      onFileContentEnd,
      onFileEditStart,
      onFileEditApplied,
      onFileEditEnd,
      onSkillMatched,
      onSkillsMatched,
      onAgentSelected,
      onIterationExhausted,
      onRouterThinking,
      onRouterDecided,
      onHandoff,
      onWorkflowStopped,
      onWorkflowComplete,
      onSessionStarted,
      onParallelStart,
      onParallelTaskStart,
      onParallelTaskEnd,
      onParallelEnd,
      onSteeringReceived,
      onCompactionStart,
      onCompactionDone,
      onThinkingOption,
      onThinkingContentOption,
      startContentSegment,
      upsertToolCallsSegment,
      resolvePendingControlTool,
      onContextOption,
      clearError,
      clearFlushTimer,
      showError,
      flushPendingContent,
      scheduleContentFlush,
      // updateSegmentsSync is stable from useImmer, included to satisfy lint
      updateSegmentsSync,
    ],
  );

  return {
    state,
    segments,
    startStream,
    cancel,
    reset,
    isStreaming: state.isStreaming,
    isThinking: state.isThinking,
    thinkingContent: state.thinkingContent,
    content: state.content,
    conflicts: state.conflicts,
    error,
    errorCode,
    sessionId,
    sendSteeringMessage,
  };
}

export default useAgentStream;
