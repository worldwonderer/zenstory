/**
 * File tree drag and drop utilities.
 *
 * Provides types, validation, and helper functions for implementing
 * native HTML5 drag and drop in the virtualized file tree.
 *
 * @module lib/fileTreeDrag
 */

import type { FileTreeNode } from '../types';

/**
 * Data transferred during drag operations.
 */
export interface DragItem {
  /** ID of the dragged node */
  nodeId: string;
  /** Type of the dragged node (folder, draft, outline, etc.) */
  nodeType: string;
  /** Parent ID of the dragged node */
  parentId: string | null;
  /** Display title of the dragged node */
  title: string;
}

/**
 * Target location for drop operations.
 */
export interface DropTarget {
  /** ID of the target node */
  targetId: string;
  /** Type of drop: 'into' folder or 'before'/'after' for reordering */
  position: 'into' | 'before' | 'after';
}

/**
 * MIME type for drag data.
 */
export const DRAG_MIME_TYPE = 'application/x-zenstory-filetree-drag';

/**
 * Set drag data on a drag event.
 */
export function setDragData(
  e: DragEvent | React.DragEvent,
  item: DragItem
): void {
  e.dataTransfer!.setData(DRAG_MIME_TYPE, JSON.stringify(item));
  e.dataTransfer!.effectAllowed = 'move';
}

/**
 * Get drag data from a drag event.
 */
export function getDragData(e: DragEvent | React.DragEvent): DragItem | null {
  try {
    const data = e.dataTransfer!.getData(DRAG_MIME_TYPE);
    return data ? JSON.parse(data) : null;
  } catch {
    return null;
  }
}

/**
 * Build a map of node depths for cycle detection.
 */
export function buildNodeDepthMap(
  nodes: FileTreeNode[],
  depth = 0
): Map<string, number> {
  const map = new Map<string, number>();

  function traverse(node: FileTreeNode, d: number) {
    map.set(node.id, d);
    if (node.children) {
      for (const child of node.children) {
        traverse(child, d + 1);
      }
    }
  }

  for (const node of nodes) {
    traverse(node, depth);
  }

  return map;
}

/**
 * Get all descendant IDs of a node (for cycle detection).
 */
export function getDescendantIds(node: FileTreeNode): string[] {
  const ids: string[] = [];

  function collect(n: FileTreeNode) {
    if (n.children) {
      for (const child of n.children) {
        ids.push(child.id);
        collect(child);
      }
    }
  }

  collect(node);
  return ids;
}

/**
 * Find a node by ID in the tree.
 */
export function findNodeById(
  nodes: FileTreeNode[],
  id: string
): FileTreeNode | null {
  for (const node of nodes) {
    if (node.id === id) return node;
    if (node.children) {
      const found = findNodeById(node.children, id);
      if (found) return found;
    }
  }
  return null;
}

/**
 * Check if a drop is valid.
 *
 * Rules:
 * - Cannot drop a node onto itself
 * - Cannot drop a folder into its own descendants
 * - Cannot drop into non-folder (except for reordering)
 * - Cannot drop root folders
 */
export function canDrop(
  dragItem: DragItem,
  dropTarget: DropTarget,
  nodes: FileTreeNode[]
): { valid: boolean; error?: string } {
  // Cannot drop onto itself
  if (dragItem.nodeId === dropTarget.targetId) {
    return { valid: false, error: 'Cannot drop onto itself' };
  }

  // Check for descendant cycle (if dragging a folder)
  if (dragItem.nodeType === 'folder') {
    const draggedNode = findNodeById(nodes, dragItem.nodeId);
    if (draggedNode) {
      const descendantIds = getDescendantIds(draggedNode);
      if (descendantIds.includes(dropTarget.targetId)) {
        return { valid: false, error: 'Cannot drop folder into its own descendant' };
      }
    }
  }

  // Check target type for 'into' drops
  if (dropTarget.position === 'into') {
    const targetNode = findNodeById(nodes, dropTarget.targetId);
    if (targetNode && targetNode.file_type !== 'folder') {
      return { valid: false, error: 'Can only drop into folders' };
    }
  }

  return { valid: true };
}

/**
 * Determine drop position based on Y coordinate relative to element.
 *
 * - Top 25%: 'before'
 * - Middle 50%: 'into' (for folders only, otherwise 'before')
 * - Bottom 25%: 'after'
 */
export function getDropPosition(
  y: number,
  elementHeight: number,
  isFolder: boolean
): 'into' | 'before' | 'after' {
  const relativeY = y / elementHeight;

  if (relativeY < 0.25) {
    return 'before';
  } else if (relativeY > 0.75) {
    return 'after';
  } else {
    // Middle 50%
    return isFolder ? 'into' : 'before';
  }
}
