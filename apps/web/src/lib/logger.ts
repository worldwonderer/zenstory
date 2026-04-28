/**
 * Production-safe logging utility.
 * In development: logs debug, info, warn, and error messages.
 * In production: only warns and errors are shown.
 */

const isDev = import.meta.env.DEV;

/**
 * Logger object with environment-aware logging methods.
 */
export const logger = {
  /**
   * Log debug messages (development only).
   * @param args - Arguments to log
   */
  debug: (...args: unknown[]): void => {
    if (isDev) {
      console.log('[DEBUG]', ...args);
    }
  },

  /**
   * Log info messages (development only).
   * @param args - Arguments to log
   */
  info: (...args: unknown[]): void => {
    if (isDev) {
      console.info('[INFO]', ...args);
    }
  },

  /**
   * Log warning messages (always shown).
   * @param args - Arguments to log
   */
  warn: (...args: unknown[]): void => {
    console.warn('[WARN]', ...args);
  },

  /**
   * Log error messages (always shown).
   * @param args - Arguments to log
   */
  error: (...args: unknown[]): void => {
    console.error('[ERROR]', ...args);
  },

  /**
   * Generic log messages (development only).
   * @param args - Arguments to log
   */
  log: (...args: unknown[]): void => {
    if (isDev) {
      console.log(...args);
    }
  },
};

export default logger;
