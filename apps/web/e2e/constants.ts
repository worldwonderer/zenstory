/**
 * E2E Test Constants
 *
 * Centralized configuration for timeouts, viewports, and limits used across E2E tests.
 * This ensures consistency and makes it easy to adjust values for different environments.
 */

export const TIMEOUTS = {
  SHORT: 3000,
  MEDIUM: 10000,
  LONG: 30000,
  VERY_LONG: 60000,
  AUTO_SAVE_DEBOUNCE: 3000,
  // UI interaction timeouts
  FOLDER_EXPAND: 300,
  FILE_OPERATION: 500,
  NETWORK_LATENCY: 1000,
  TYPING_DELAY: 10,
  AI_RESPONSE_START: 10000,
  AI_STREAMING_COMPLETE: 45000,
  IDLE_SUGGESTION: 12000,
  DEBOUNCE_BUFFER: 4500, // AUTO_SAVE_DEBOUNCE + buffer
  SCROLL_DELAY: 100,
  VERSION_LOAD: 500,
  MODAL_DELAY: 500,
} as const

export const VIEWPORTS = {
  MOBILE: { width: 390, height: 844 }, // iPhone 14
  TABLET: { width: 768, height: 1024 }, // iPad
  DESKTOP: { width: 1280, height: 720 },
} as const

export const LIMITS = {
  MAX_FILE_SIZE: 5 * 1024 * 1024, // 5MB
  MAX_VERSIONS: 100,
  MAX_MESSAGE_LENGTH: 10000,
  MAX_PROJECTS: 50,
  MAX_FILENAME_LENGTH: 255,
} as const

export const PERFORMANCE = {
  FILE_TREE_RENDER_MS: 3000, // < 3 seconds for 1000 files
  FOLDER_INTERACTION_MS: 200, // < 200ms for expand/collapse
  SEARCH_RESPONSE_MS: 500, // < 500ms for search
  VERSION_LIST_LOAD_MS: 2000, // < 2 seconds for 100 versions
  VERSION_COMPARE_MS: 1000, // < 1 second for comparison
  LARGE_FILE_LOAD_MS: 5000, // < 5 seconds for 10MB file
  INPUT_RESPONSE_MS: 100, // < 100ms for input response
  VISIBLE_NODE_LIMIT: 50, // Virtual scroll should render < 50 nodes
} as const
