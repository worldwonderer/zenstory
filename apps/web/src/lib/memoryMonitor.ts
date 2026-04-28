/**
 * Memory monitoring utilities for development and performance testing.
 *
 * This module provides tools for tracking memory usage during development,
 * particularly useful for verifying that large documents (50k+ words) stay
 * under the 500MB memory threshold. Exposed globally in development mode
 * for console access.
 *
 * Architecture:
 * - Uses Chrome's Performance Memory API (requires specific flags or DevTools open)
 * - Lightweight, zero-dependency implementation
 * - All functions fail gracefully if memory API is unavailable
 * - Development-only module (tree-shaken in production)
 * - Tracks JS heap size, DOM node count, and event listener estimates
 * - Provides interval-based tracking with automatic spike detection
 * - Supports manual garbage collection when run with --expose-gc flag
 *
 * Memory thresholds:
 * - Target: < 500MB for 50k+ word documents
 * - Warning: Significant increases (>10MB) between snapshots
 * - Limit: Browser-specific, typically 1-2GB
 *
 * Usage:
 * ```ts
 * // Start tracking memory every 5 seconds
 * startMemoryTracking(5000);
 *
 * // Get current usage
 * const usage = getMemoryUsage();
 * console.log(usage);
 *
 * // Stop tracking and get report
 * const report = stopMemoryTracking();
 * console.log(report.summary);
 *
 * // Force garbage collection (Chrome with --expose-gc)
 * forceGC();
 * ```
 *
 * @module lib/memoryMonitor
 */

import { logger } from './logger';

/**
 * Memory usage snapshot at a point in time.
 *
 * Contains heap information from the Performance Memory API (Chrome-only)
 * along with DOM metrics that are available cross-browser.
 *
 * @interface MemorySnapshot
 */
export interface MemorySnapshot {
  /** Unix timestamp when snapshot was taken */
  timestamp: number;
  /** Total JS heap size (Chrome only) */
  jsHeapSize?: number;
  /** Maximum heap size limit (Chrome only) */
  jsHeapSizeLimit?: number;
  /** Total allocated JS heap size (Chrome only) */
  totalJSHeapSize?: number;
  /** Used JS heap size (Chrome only) - the key metric */
  usedJSHeapSize?: number;
  /** Number of DOM nodes in the document */
  domNodes: number;
  /** Estimated event listener count (approximate) */
  eventListeners: number;
}

/**
 * Internal state for memory tracking.
 *
 * @interface MemoryTrackerState
 * @internal
 */
interface MemoryTrackerState {
  /** Whether tracking is currently active */
  isTracking: boolean;
  /** Array of snapshots taken during tracking */
  snapshots: MemorySnapshot[];
  /** Initial snapshot when tracking started */
  startSnapshot: MemorySnapshot | null;
  /** Timer ID for interval-based tracking */
  intervalId: ReturnType<typeof setInterval> | null;
}

const trackerState: MemoryTrackerState = {
  isTracking: false,
  snapshots: [],
  startSnapshot: null,
  intervalId: null,
};

/**
 * Check if the Performance Memory API is available.
 *
 * The Memory API is only available in Chrome and requires either:
 * - DevTools to be open
 * - Chrome launched with --enable-memory-info flag
 *
 * @returns True if performance.memory is available
 *
 * @internal
 */
function hasMemoryAPI(): boolean {
  return (
    typeof performance !== 'undefined' &&
    'memory' in performance &&
    (performance as Performance & { memory?: { usedJSHeapSize: number; totalJSHeapSize: number; jsHeapSizeLimit: number } }).memory !== undefined
  );
}

/**
 * Get current memory metrics from the Performance Memory API.
 *
 * @returns Memory metrics object or undefined if API is not available
 *
 * @internal
 */
function getPerformanceMemory():
  | {
      usedJSHeapSize: number;
      totalJSHeapSize: number;
      jsHeapSizeLimit: number;
    }
  | undefined {
  if (!hasMemoryAPI()) {
    return undefined;
  }

  const memory = (performance as Performance & { memory?: { usedJSHeapSize: number; totalJSHeapSize: number; jsHeapSizeLimit: number } }).memory;
  return memory;
}

/**
 * Count total DOM nodes in the document.
 *
 * High DOM node counts can impact performance. A good target is
 * under 1500 nodes for optimal rendering performance.
 *
 * @returns Total number of DOM elements
 *
 * @internal
 */
function countDomNodes(): number {
  return document.getElementsByTagName('*').length;
}

/**
 * Estimate the number of event listeners on the document.
 *
 * Note: This is an approximation using Chrome DevTools' getEventListeners
 * function when available. Returns 0 in other browsers.
 *
 * @returns Estimated event listener count or 0 if unavailable
 *
 * @internal
 */
function estimateEventListenerCount(): number {
  // Use getEventListeners if available (Chrome DevTools)
  if (typeof (window as Window & { getEventListeners?: (target: unknown) => Record<string, unknown[]> }).getEventListeners === 'function') {
    try {
      const listeners = (window as unknown as Window & { getEventListeners: (target: unknown) => Record<string, unknown[]> }).getEventListeners(document);
      return Object.values(listeners).reduce((sum, arr) => sum + arr.length, 0);
    } catch {
      // Ignore if it fails
    }
  }
  return 0;
}

/**
 * Take a memory usage snapshot.
 *
 * Captures current memory metrics including JS heap size (Chrome only),
 * DOM node count, and estimated event listeners. Use for one-time
 * measurements or as part of custom tracking logic.
 *
 * @returns MemorySnapshot with current memory metrics
 *
 * @example
 * ```ts
 * const snapshot = takeSnapshot();
 * console.log(`Memory: ${formatBytes(snapshot.usedJSHeapSize)}`);
 * console.log(`DOM Nodes: ${snapshot.domNodes}`);
 * ```
 */
export function takeSnapshot(): MemorySnapshot {
  const memory = getPerformanceMemory();

  return {
    timestamp: Date.now(),
    jsHeapSize: memory?.totalJSHeapSize,
    jsHeapSizeLimit: memory?.jsHeapSizeLimit,
    totalJSHeapSize: memory?.totalJSHeapSize,
    usedJSHeapSize: memory?.usedJSHeapSize,
    domNodes: countDomNodes(),
    eventListeners: estimateEventListenerCount(),
  };
}

/**
 * Format bytes to a human-readable string with appropriate units.
 *
 * Automatically selects the best unit (B, KB, MB, GB) based on size
 * and formats to 2 decimal places.
 *
 * @param bytes - Number of bytes, or undefined for 'N/A'
 * @returns Formatted string like "256.00 MB" or "N/A" if bytes is undefined
 *
 * @example
 * ```ts
 * formatBytes(1024);        // "1.00 KB"
 * formatBytes(524288000);   // "500.00 MB"
 * formatBytes(undefined);   // "N/A"
 * ```
 */
export function formatBytes(bytes: number | undefined): string {
  if (bytes === undefined) return 'N/A';
  if (bytes === 0) return '0 B';

  const units = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  const value = bytes / Math.pow(1024, i);

  return `${value.toFixed(2)} ${units[i]}`;
}

/**
 * Get current memory usage in a human-readable format.
 *
 * Returns an object with formatted memory metrics suitable for display
 * or logging. All byte values are formatted as human-readable strings.
 *
 * @returns Object with used, total, limit, percentage, and domNodes
 *
 * @example
 * ```ts
 * const usage = getMemoryUsage();
 * console.log(`Memory: ${usage.used} / ${usage.limit} (${usage.percentage})`);
 * console.log(`DOM Nodes: ${usage.domNodes}`);
 *
 * // Check against threshold
 * if (parseFloat(usage.percentage) > 50) {
 *   console.warn('High memory usage!');
 * }
 * ```
 */
export function getMemoryUsage(): {
  used: string;
  total: string;
  limit: string;
  percentage: string;
  domNodes: number;
} {
  const memory = getPerformanceMemory();

  return {
    used: formatBytes(memory?.usedJSHeapSize),
    total: formatBytes(memory?.totalJSHeapSize),
    limit: formatBytes(memory?.jsHeapSizeLimit),
    percentage: memory ? `${((memory.usedJSHeapSize / memory.jsHeapSizeLimit) * 100).toFixed(1)}%` : 'N/A',
    domNodes: countDomNodes(),
  };
}

/**
 * Start tracking memory usage over time.
 *
 * Begins taking memory snapshots at the specified interval. Logs a warning
 * to the console when memory increases significantly (>10MB between snapshots).
 * Call stopMemoryTracking() to end tracking and get a summary report.
 *
 * Note: Only one tracking session can be active at a time.
 *
 * @param intervalMs - Interval between snapshots in milliseconds. Default: 5000 (5 seconds)
 *
 * @example
 * ```ts
 * // Start tracking before heavy operation
 * startMemoryTracking(2000); // Every 2 seconds
 *
 * // Perform memory-intensive operation
 * await loadLargeDocument();
 *
 * // Stop and get results
 * const report = stopMemoryTracking();
 * console.log(`Peak usage: ${formatBytes(report.peakUsage)}`);
 * ```
 */
export function startMemoryTracking(intervalMs: number = 5000): void {
  if (trackerState.isTracking) {
    logger.warn('[MemoryMonitor] Already tracking memory');
    return;
  }

  trackerState.isTracking = true;
  trackerState.snapshots = [];
  trackerState.startSnapshot = takeSnapshot();

  logger.log('[MemoryMonitor] Started tracking memory');
  logger.log('[MemoryMonitor] Initial usage:', getMemoryUsage());

  trackerState.intervalId = setInterval(() => {
    const snapshot = takeSnapshot();
    trackerState.snapshots.push(snapshot);

    // Log if memory increases significantly (>10MB jump)
    if (trackerState.snapshots.length > 1) {
      const prev = trackerState.snapshots[trackerState.snapshots.length - 2];
      const curr = snapshot;
      if (prev.usedJSHeapSize && curr.usedJSHeapSize) {
        const diff = curr.usedJSHeapSize - prev.usedJSHeapSize;
        if (diff > 10 * 1024 * 1024) {
          // 10MB
          logger.warn(`[MemoryMonitor] Significant memory increase: ${formatBytes(diff)}`);
        }
      }
    }
  }, intervalMs);
}

/**
 * Stop tracking and get a comprehensive report.
 *
 * Ends the current tracking session and returns detailed results including
 * start/end snapshots, peak usage, all collected snapshots, and a formatted
 * summary string. Also logs the summary to the console.
 *
 * The summary includes a warning if peak usage exceeded 500MB threshold.
 *
 * @returns Object with tracking results:
 *   - startSnapshot: Initial memory state when tracking began
 *   - endSnapshot: Final memory state when tracking stopped
 *   - peakUsage: Highest memory usage observed during tracking
 *   - snapshots: All snapshots taken during the session
 *   - summary: Human-readable summary string
 *
 * @example
 * ```ts
 * startMemoryTracking(1000);
 * // ... perform operations ...
 * const result = stopMemoryTracking();
 *
 * if (result.peakUsage && result.peakUsage > 500 * 1024 * 1024) {
 *   console.error('Memory exceeded 500MB threshold!');
 * }
 *
 * console.log(result.summary);
 * // Memory Tracking Summary:
 * // ------------------------
 * // Duration: 30 seconds (approx)
 * // Start: 150.00 MB
 * // End: 320.00 MB
 * // Peak: 350.00 MB
 * // ...
 * ```
 */
export function stopMemoryTracking(): {
  startSnapshot: MemorySnapshot | null;
  endSnapshot: MemorySnapshot | null;
  peakUsage: number | null;
  snapshots: MemorySnapshot[];
  summary: string;
} {
  if (!trackerState.isTracking) {
    logger.warn('[MemoryMonitor] Not currently tracking');
    return {
      startSnapshot: null,
      endSnapshot: null,
      peakUsage: null,
      snapshots: [],
      summary: 'No tracking data available',
    };
  }

  if (trackerState.intervalId) {
    clearInterval(trackerState.intervalId);
    trackerState.intervalId = null;
  }

  const endSnapshot = takeSnapshot();
  trackerState.isTracking = false;

  // Calculate peak usage
  let peakUsage: number | null = null;
  if (trackerState.startSnapshot?.usedJSHeapSize && endSnapshot.usedJSHeapSize) {
    peakUsage = Math.max(
      trackerState.startSnapshot.usedJSHeapSize,
      ...trackerState.snapshots.map((s) => s.usedJSHeapSize ?? 0),
      endSnapshot.usedJSHeapSize
    );
  }

  // Generate summary
  let summary = 'Memory Tracking Summary:\n';
  summary += '------------------------\n';
  summary += `Duration: ${trackerState.snapshots.length * 5} seconds (approx)\n`;
  summary += `Start: ${formatBytes(trackerState.startSnapshot?.usedJSHeapSize)}\n`;
  summary += `End: ${formatBytes(endSnapshot.usedJSHeapSize)}\n`;
  summary += `Peak: ${formatBytes(peakUsage ?? undefined)}\n`;
  summary += `DOM Nodes: ${endSnapshot.domNodes}\n`;
  summary += `Memory Limit: ${formatBytes(endSnapshot.jsHeapSizeLimit)}\n`;

  if (peakUsage && endSnapshot.jsHeapSizeLimit) {
    const percentage = (peakUsage / endSnapshot.jsHeapSizeLimit) * 100;
    summary += `\nPeak usage: ${percentage.toFixed(1)}% of limit`;

    if (peakUsage > 500 * 1024 * 1024) {
      summary += '\n⚠️ WARNING: Peak usage exceeds 500MB threshold!';
    } else {
      summary += '\n✅ Memory usage is within acceptable limits (<500MB)';
    }
  }

  logger.log(summary);

  return {
    startSnapshot: trackerState.startSnapshot,
    endSnapshot,
    peakUsage,
    snapshots: [...trackerState.snapshots],
    summary,
  };
}

/**
 * Force garbage collection if available.
 *
 * Attempts to trigger the browser's garbage collector. This only works
 * when Chrome is launched with the --expose-gc flag. Useful for getting
 * accurate memory measurements after cleanup operations.
 *
 * @returns True if GC was triggered, false if GC is not available
 *
 * @example
 * ```ts
 * // Before measuring memory, force GC to get accurate reading
 * if (forceGC()) {
 *   const usage = getMemoryUsage();
 *   console.log(`Memory after GC: ${usage.used}`);
 * } else {
 *   console.log('GC not available. Start Chrome with --expose-gc flag.');
 * }
 * ```
 */
export function forceGC(): boolean {
  if (typeof (window as Window & { gc?: () => void }).gc === 'function') {
    (window as unknown as Window & { gc: () => void }).gc();
    logger.log('[MemoryMonitor] Forced garbage collection');
    return true;
  }
  logger.warn('[MemoryMonitor] GC not available. Start Chrome with --expose-gc flag.');
  return false;
}

/**
 * Get a detailed memory report string.
 *
 * Returns a multi-line string with comprehensive memory information,
 * including current usage, threshold checks (500MB, 1GB), and tracking
 * status. Suitable for logging or display in debug UIs.
 *
 * @returns Formatted multi-line string with complete memory report
 *
 * @example
 * ```ts
 * // Get report for logging
 * const report = getMemoryReport();
 * console.log(report);
 *
 * // === Memory Report ===
 * //
 * // Current Usage:
 * //   Used JS Heap: 250.00 MB
 * //   Total JS Heap: 300.00 MB
 * //   Heap Limit: 2.00 GB
 * //   Usage: 12.5%
 * //   DOM Nodes: 856
 * //
 * // Thresholds:
 * //   Under 500MB: ✅ Yes
 * //   Under 1GB: ✅ Yes
 * //
 * // Tracking Status:
 * //   Currently tracking: No
 * //   Snapshots collected: 0
 * ```
 */
export function getMemoryReport(): string {
  const memory = getPerformanceMemory();
  const usage = getMemoryUsage();

  let report = '=== Memory Report ===\n\n';

  report += 'Current Usage:\n';
  report += `  Used JS Heap: ${usage.used}\n`;
  report += `  Total JS Heap: ${usage.total}\n`;
  report += `  Heap Limit: ${usage.limit}\n`;
  report += `  Usage: ${usage.percentage}\n`;
  report += `  DOM Nodes: ${usage.domNodes}\n\n`;

  report += 'Thresholds:\n';
  if (memory) {
    const threshold500MB = 500 * 1024 * 1024;
    const threshold1GB = 1024 * 1024 * 1024;

    report += `  Under 500MB: ${memory.usedJSHeapSize < threshold500MB ? '✅ Yes' : '❌ No'}\n`;
    report += `  Under 1GB: ${memory.usedJSHeapSize < threshold1GB ? '✅ Yes' : '❌ No'}\n\n`;
  }

  report += 'Tracking Status:\n';
  report += `  Currently tracking: ${trackerState.isTracking ? 'Yes' : 'No'}\n`;
  report += `  Snapshots collected: ${trackerState.snapshots.length}\n`;

  return report;
}

/**
 * Log memory usage to console with a custom label.
 *
 * Convenience function for quick memory logging during development.
 * Prefixes output with [MemoryMonitor] and the provided label.
 *
 * @param label - Custom label to identify this log entry
 *
 * @example
 * ```ts
 * logMemoryUsage('After loading document');
 * // [MemoryMonitor] After loading document: {
 * //   used: "250.00 MB",
 * //   total: "300.00 MB",
 * //   limit: "2.00 GB",
 * //   percentage: "12.5%",
 * //   domNodes: 856
 * // }
 *
 * logMemoryUsage('After cleanup');
 * // [MemoryMonitor] After cleanup: { ... }
 * ```
 */
export function logMemoryUsage(label: string): void {
  const usage = getMemoryUsage();
  logger.log(`[MemoryMonitor] ${label}:`, usage);
}

// Expose to window for console access in development
if (import.meta.env.DEV && typeof window !== 'undefined') {
  (window as Window & { __memoryMonitor?: typeof memoryMonitorExports }).__memoryMonitor = {
    getMemoryUsage,
    getMemoryReport,
    startMemoryTracking,
    stopMemoryTracking,
    forceGC,
    takeSnapshot,
    formatBytes,
    logMemoryUsage,
  };
  if (import.meta.env.MODE !== 'test') {
    logger.log('[MemoryMonitor] Available at window.__memoryMonitor');
  }
}

const memoryMonitorExports = {
  getMemoryUsage,
  getMemoryReport,
  startMemoryTracking,
  stopMemoryTracking,
  forceGC,
  takeSnapshot,
  formatBytes,
  logMemoryUsage,
};

export default memoryMonitorExports;
