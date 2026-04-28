/**
 * Hook for managing file tree drag and drop state.
 *
 * Provides state management and handlers for HTML5 native drag and drop
 * in the virtualized file tree.
 *
 * @module hooks/useFileTreeDrag
 */

import { useState, useCallback } from 'react';
import type { DropTarget } from '../lib/fileTreeDrag';

/**
 * Drag state for the file tree.
 */
export interface FileTreeDragState {
  /** ID of the node being dragged */
  draggingId: string | null;
  /** Current drop target */
  dropTarget: DropTarget | null;
  /** Error message if drop failed */
  error: string | null;
}

/**
 * Return type for useFileTreeDragDrop hook.
 */
export interface UseFileTreeDragDropReturn {
  /** Current drag state */
  state: FileTreeDragState;
  /** Start dragging a node */
  startDrag: (nodeId: string, nodeType: string, parentId: string | null, title: string) => void;
  /** Set the current drop target */
  setDropTarget: (targetId: string, position: 'into' | 'before' | 'after') => void;
  /** End the drag operation */
  endDrag: () => void;
  /** Set an error message */
  setError: (error: string | null) => void;
  /** Execute the move operation */
  executeMove: (fileId: string, targetFolderId: string) => Promise<boolean>;
  /** Execute the reorder operation */
  executeReorder: (projectId: string, parentId: string | null, orderedIds: string[]) => Promise<boolean>;
}

/**
 * Hook for managing file tree drag and drop.
 *
 * @param onMoveFile - Callback to move a file to a new folder
 * @param onReorderFiles - Callback to reorder files within a folder
 * @returns Drag state and handlers
 */
export function useFileTreeDragDrop(
  onMoveFile: (fileId: string, targetFolderId: string) => Promise<boolean>,
  onReorderFiles: (parentId: string | null, orderedIds: string[]) => Promise<boolean>
): UseFileTreeDragDropReturn {
  const [state, setState] = useState<FileTreeDragState>({
    draggingId: null,
    dropTarget: null,
    error: null,
  });

  const startDrag = useCallback((
    nodeId: string,
    _nodeType: string,
    _parentId: string | null,
    _title: string
  ) => {
    setState({
      draggingId: nodeId,
      dropTarget: null,
      error: null,
    });
  }, []);

  const setDropTarget = useCallback((targetId: string, position: 'into' | 'before' | 'after') => {
    setState(prev => ({
      ...prev,
      dropTarget: { targetId, position },
      error: null,
    }));
  }, []);

  const endDrag = useCallback(() => {
    setState({
      draggingId: null,
      dropTarget: null,
      error: null,
    });
  }, []);

  const setError = useCallback((error: string | null) => {
    setState(prev => ({
      ...prev,
      error,
    }));
  }, []);

  const executeMove = useCallback(async (
    fileId: string,
    targetFolderId: string
  ): Promise<boolean> => {
    try {
      const success = await onMoveFile(fileId, targetFolderId);
      if (!success) {
        setState(prev => ({
          ...prev,
          error: 'Failed to move file',
        }));
      }
      return success;
    } catch (error) {
      setState(prev => ({
        ...prev,
        error: error instanceof Error ? error.message : 'Failed to move file',
      }));
      return false;
    }
  }, [onMoveFile]);

  const executeReorder = useCallback(async (
    _projectId: string,
    parentId: string | null,
    orderedIds: string[]
  ): Promise<boolean> => {
    try {
      const success = await onReorderFiles(parentId, orderedIds);
      if (!success) {
        setState(prev => ({
          ...prev,
          error: 'Failed to reorder files',
        }));
      }
      return success;
    } catch (error) {
      setState(prev => ({
        ...prev,
        error: error instanceof Error ? error.message : 'Failed to reorder files',
      }));
      return false;
    }
  }, [onReorderFiles]);

  return {
    state,
    startDrag,
    setDropTarget,
    endDrag,
    setError,
    executeMove,
    executeReorder,
  };
}
