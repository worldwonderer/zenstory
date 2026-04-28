/**
 * Lightweight event-based toast notification utility.
 *
 * This module provides a simple, decoupled toast notification system using
 * an in-memory pub/sub channel. Components can emit toast messages without
 * importing UI components directly.
 *
 * Architecture:
 * - Uses module-scoped listener registry (no global window event surface)
 * - Toast UI components subscribe and render messages
 * - Auto-incrementing IDs ensure unique toast identification
 *
 * Usage:
 * ```ts
 * import { toast } from '../lib/toast';
 * toast.error('Something went wrong');
 * toast.success('Operation completed!');
 * toast.info('File saved successfully');
 * ```
 *
 * @module lib/toast
 */

/**
 * Toast notification severity types.
 *
 * - 'error': Red styling, used for failures and exceptions
 * - 'success': Green styling, used for successful operations
 * - 'info': Blue styling, used for informational messages
 */
export type ToastType = 'error' | 'success' | 'info';

/**
 * Toast event payload dispatched to listeners.
 *
 * @property id - Unique auto-incremented identifier for this toast
 * @property message - Human-readable message to display
 * @property type - Severity level determining visual styling
 */
export interface ToastEvent {
  id: number;
  message: string;
  type: ToastType;
}

export type ToastListener = (event: ToastEvent) => void;

/** Auto-incrementing counter for unique toast IDs */
let nextId = 0;
const listeners = new Set<ToastListener>();

/**
 * Register a toast listener.
 *
 * @param listener - Callback invoked whenever a toast is emitted
 * @returns Cleanup function that unsubscribes the listener
 */
export function subscribeToast(listener: ToastListener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/**
 * Dispatch a toast event to all listeners.
 *
 * @param message - Message to display in the toast
 * @param type - Severity type determining visual styling
 */
function emit(message: string, type: ToastType): void {
  const event: ToastEvent = { id: nextId++, message, type };
  listeners.forEach((listener) => listener(event));
}

/**
 * Toast notification API for displaying user feedback messages.
 *
 * Each method dispatches an event that toast UI components will render.
 *
 * @example
 * ```ts
 * // Show error toast
 * toast.error('Failed to save file');
 *
 * // Show success toast
 * toast.success('File saved successfully');
 *
 * // Show info toast
 * toast.info('Auto-saving in 30 seconds');
 * ```
 */
export const toast = {
  /**
   * Display an error toast notification.
   *
   * Use for operation failures, validation errors, or exceptions.
   * Typically styled with red/danger colors.
   *
   * @param message - Error message to display
   */
  error: (message: string) => emit(message, 'error'),

  /**
   * Display a success toast notification.
   *
   * Use for successful operations, confirmations, or completions.
   * Typically styled with green/success colors.
   *
   * @param message - Success message to display
   */
  success: (message: string) => emit(message, 'success'),

  /**
   * Display an informational toast notification.
   *
   * Use for neutral information, tips, or non-critical updates.
   * Typically styled with blue/info colors.
   *
   * @param message - Info message to display
   */
  info: (message: string) => emit(message, 'info'),
};
