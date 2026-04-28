/**
 * @fileoverview Thinking Content Component
 * @module components/ThinkingContent
 *
 * Displays AI reasoning process (thinking) in a collapsible panel.
 * Shows the model's intermediate reasoning steps before producing
 * the final response, helping users understand the AI's thought process.
 *
 * Features:
 * - Collapsible with expand/collapse toggle
 * - Animated dots when streaming (indicates active thinking)
 * - Markdown rendering with GFM support (tables, lists, code blocks)
 * - Returns null when content is empty
 * - Persists expand/collapse state to localStorage
 * - Global visibility control via useThinkingVisibility hook
 * - i18n support (English/Chinese labels)
 *
 * @example
 * // Basic usage with static content
 * <ThinkingContent content="Analyzing the request..." />
 *
 * @example
 * // Streaming mode with animated dots
 * <ThinkingContent
 *   content="Let me think about this..."
 *   isStreaming={true}
 * />
 *
 * @see useThinkingVisibility - Hook for global thinking visibility control
 */

import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { ChevronDown, ChevronUp } from "lucide-react";
import { LazyMarkdown } from "./LazyMarkdown";
import { useThinkingVisibility } from "../hooks/useThinkingVisibility";

/**
 * Props for the ThinkingContent component.
 *
 * @interface ThinkingContentProps
 */
interface ThinkingContentProps {
  /**
   * The thinking/reasoning content to display.
   * Rendered as Markdown with GFM support.
   * If empty or whitespace-only, the component returns null.
   */
  content: string;

  /**
   * Whether the AI is currently streaming thinking content.
   * When true, shows animated dots next to the "Thinking" label.
   * @default false
   */
  isStreaming?: boolean;
}

/**
 * localStorage key for persisting the expanded/collapsed state.
 * @constant {string}
 */
const STORAGE_KEY = "zenstory_thinking_expanded";

/**
 * Renders a collapsible panel displaying AI thinking/reasoning content.
 *
 * This component displays the AI's intermediate reasoning steps in a
 * collapsible panel with the following behavior:
 *
 * - **Visibility**: Controlled globally via useThinkingVisibility hook
 *   (returns null if thinking is disabled in settings)
 * - **Empty state**: Returns null if content is empty or whitespace-only
 * - **Expand/collapse**: Persists to localStorage, defaults to expanded
 * - **Streaming indicator**: Shows animated dots when isStreaming is true
 * - **Markdown rendering**: Uses ReactMarkdown with GFM support
 *
 * @param {ThinkingContentProps} props - Component props
 * @param {string} props.content - The thinking content to display (Markdown)
 * @param {boolean} [props.isStreaming=false] - Whether AI is actively thinking
 * @returns {React.ReactElement | null} The thinking panel, or null if hidden/empty
 *
 * @example
 * // In a chat message component
 * const message = useAgentStream();
 *
 * return (
 *   <div>
 *     {message.thinking && (
 *       <ThinkingContent
 *         content={message.thinking}
 *         isStreaming={message.isStreamingThinking}
 *       />
 *     )}
 *     <div>{message.text}</div>
 *   </div>
 * );
 */
export function ThinkingContent({ content, isStreaming = false }: ThinkingContentProps) {
  const { t } = useTranslation('chat');
  // Global visibility control reserved for future UI toggle
  // Currently controlled by localStorage via useThinkingVisibility hook
  const { showThinking } = useThinkingVisibility();

  // Initialize state from localStorage or default to true (expanded)
  // Note: Hooks must be called unconditionally before any early returns
  const [isExpanded, setIsExpanded] = useState(() => {
    if (typeof window === "undefined") return true;
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return stored !== null ? stored === "true" : true;
    } catch {
      return true;
    }
  });

  // Save state to localStorage whenever it changes
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, String(isExpanded));
    } catch {
      // Ignore localStorage errors
    }
  }, [isExpanded]);

  // Don't render if global setting is disabled
  if (!showThinking) {
    return null;
  }

  // Return null if no content
  if (!content || content.trim().length === 0) {
    return null;
  }

  return (
    <div className="max-w-full rounded-lg mb-2 opacity-60 hover:opacity-80 transition-opacity duration-700">
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-2 py-1.5 flex items-center justify-between rounded hover:bg-[hsl(var(--bg-tertiary)/0.5)] transition-colors"
        aria-label={isExpanded
          ? t('chat:thinking.collapse', '收起思考过程')
          : t('chat:thinking.expand', '展开思考过程')}
      >
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-[hsl(var(--text-secondary))]">
            {t('chat:thinking.title')}
          </span>
          {isStreaming && (
            <div className="flex items-center gap-0.5">
              <span className="w-1 h-1 bg-[hsl(var(--text-secondary))] rounded-full animate-pulse"></span>
              <span className="w-1 h-1 bg-[hsl(var(--text-secondary))] rounded-full animate-pulse" style={{ animationDelay: "0.2s" }}></span>
              <span className="w-1 h-1 bg-[hsl(var(--text-secondary))] rounded-full animate-pulse" style={{ animationDelay: "0.4s" }}></span>
            </div>
          )}
        </div>
        <div className="flex items-center">
          {isExpanded ? (
            <ChevronUp className="w-3 h-3 text-[hsl(var(--text-secondary))]" />
          ) : (
            <ChevronDown className="w-3 h-3 text-[hsl(var(--text-secondary))]" />
          )}
        </div>
      </button>

      {/* Content */}
      {isExpanded && (
        <div className="px-2 py-1.5">
          <div className="prose prose-xs max-w-none text-[hsl(var(--text-secondary))] opacity-80">
            <LazyMarkdown>{content}</LazyMarkdown>
          </div>
        </div>
      )}
    </div>
  );
}

export default ThinkingContent;
