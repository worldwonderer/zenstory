import { useState, useEffect } from "react";
import { logger } from "../lib/logger";

const STORAGE_KEY = "zenstory_show_thinking";

/**
 * Return type for useThinkingVisibility hook
 */
export interface ThinkingVisibilityResult {
  /** Current visibility state of thinking content */
  showThinking: boolean;
  /** Function to set visibility state directly */
  setShowThinking: (value: boolean) => void;
  /** Function to toggle visibility state */
  toggleThinking: () => void;
}

/**
 * Hook to manage thinking content visibility preference.
 *
 * Persists the visibility state to localStorage with key 'zenstory_show_thinking'.
 * Defaults to true (visible) if no stored preference exists.
 *
 * @returns Object containing visibility state and control functions
 *
 * @example
 * ```tsx
 * const { showThinking, toggleThinking } = useThinkingVisibility();
 *
 * return (
 *   <div>
 *     <button onClick={toggleThinking}>
 *       {showThinking ? 'Hide' : 'Show'} Thinking
 *     </button>
 *     {showThinking && <ThinkingContent />}
 *   </div>
 * );
 * ```
 */
export function useThinkingVisibility(): ThinkingVisibilityResult {
  const [showThinking, setShowThinking] = useState(() => {
    if (typeof window === "undefined") return true;
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return stored !== null ? stored === "true" : true;
    } catch {
      return true;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, String(showThinking));
    } catch (error) {
      logger.error("Failed to save thinking visibility state:", error);
    }
  }, [showThinking]);

  const toggleThinking = () => {
    setShowThinking((prev) => !prev);
  };

  return {
    showThinking,
    setShowThinking,
    toggleThinking,
  };
}

export default useThinkingVisibility;
