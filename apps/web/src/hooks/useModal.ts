import { useState, useCallback, useMemo } from "react";

/**
 * Return type for useModal hook
 */
interface UseModalReturn {
  /** Whether the modal is currently open */
  isOpen: boolean;
  /** Function to open the modal */
  open: () => void;
  /** Function to close the modal */
  close: () => void;
  /** Function to toggle the modal state */
  toggle: () => void;
  /** Props object to spread onto a modal component */
  modalProps: {
    open: boolean;
    onClose: () => void;
  };
}

/**
 * Hook to manage modal state
 *
 * Provides a simple interface for controlling modal open/close state with
 * convenience methods and pre-packaged props for modal components.
 *
 * @param initialState - Initial open state (defaults to false)
 * @returns Object containing modal state and control functions
 *
 * @example
 * ```tsx
 * // Basic usage
 * const { isOpen, open, close, modalProps } = useModal();
 *
 * return (
 *   <>
 *     <button onClick={open}>Open Modal</button>
 *     <Dialog {...modalProps}>
 *       <p>Modal content</p>
 *       <button onClick={close}>Close</button>
 *     </Dialog>
 *   </>
 * );
 * ```
 *
 * @example
 * ```tsx
 * // With initial state
 * const { isOpen, toggle } = useModal(true);
 *
 * return (
 *   <button onClick={toggle}>
 *     {isOpen ? 'Close' : 'Open'}
 *   </button>
 * );
 * ```
 */
export function useModal(initialState = false): UseModalReturn {
  const [isOpen, setIsOpen] = useState(initialState);

  const open = useCallback(() => setIsOpen(true), []);
  const close = useCallback(() => setIsOpen(false), []);
  const toggle = useCallback(() => setIsOpen((prev) => !prev), []);

  const modalProps = useMemo(
    () => ({
      open: isOpen,
      onClose: close,
    }),
    [isOpen, close]
  );

  return {
    isOpen,
    open,
    close,
    toggle,
    modalProps,
  };
}

export default useModal;
