/**
 * React hook for virtualizing a file tree for efficient rendering.
 *
 * Provides state management and methods for:
 * - Flattening hierarchical tree into a visible-items list
 * - Virtualizing large trees with @tanstack/react-virtual
 * - Scrolling to specific nodes
 * - Supporting file/folder creation UI states
 *
 * Key feature: Only renders visible items, enabling smooth performance
 * with trees containing thousands of files.
 */

import { useMemo, useCallback, type RefObject } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import type { FileTreeNode } from '../types';

/**
 * Types of items that can appear in the virtualized tree.
 * - 'node': Regular file or folder node
 * - 'create-input': Input field for creating new items
 * - 'empty-folder': Placeholder for empty expanded folders
 */
export type VirtualItemType = 'node' | 'create-input' | 'empty-folder';

/**
 * Represents a single visible item in the flattened tree.
 * Used by the virtualizer to render only visible nodes.
 */
export interface VisibleTreeItem {
  /** Unique key for React rendering */
  key: string;
  /** Type of virtual item */
  type: VirtualItemType;
  /** The tree node (null for non-node types) */
  node: FileTreeNode | null;
  /** Depth level (for indentation) */
  depth: number;
  /** Whether this node is a folder */
  isFolder: boolean;
  /** Whether this folder is expanded (only meaningful for folders) */
  isExpanded: boolean;
  /** Parent folder ID for create-input and empty-folder types */
  parentFolderId?: string;
}

/**
 * Options for the useVirtualizedTree hook.
 */
export interface UseVirtualizedTreeOptions {
  /** Root-level tree nodes to virtualize */
  tree: FileTreeNode[];
  /** Set of folder IDs that are currently expanded */
  expandedFolders: Set<string>;
  /** Ref to the scrollable container element */
  scrollElementRef: RefObject<HTMLDivElement | null>;
  /** ID of folder where new item is being created (optional) */
  creatingFolderId?: string | null;
}

/**
 * Return type for the useVirtualizedTree hook.
 */
export interface UseVirtualizedTreeReturn {
  /** Flattened list of visible items based on expansion state */
  visibleItems: VisibleTreeItem[];
  /** The @tanstack/react-virtual virtualizer instance */
  virtualizer: ReturnType<typeof useVirtualizer>;
  /** Scroll a specific node into view by its ID */
  scrollToNode: (nodeId: string) => void;
  /** Total size of all items in pixels */
  totalSize: number;
  /** Currently visible virtual items to render */
  virtualItems: ReturnType<typeof useVirtualizer>['getVirtualItems'] extends () => infer R ? R : never;
}

/** Height of each tree row in pixels */
const ITEM_HEIGHT = 32;
/** Height for create input row (slightly taller) */
const CREATE_INPUT_HEIGHT = 36;
/** Number of items to render beyond the visible area */
const OVERSCAN_COUNT = 10;

/**
 * Hook that virtualizes a file tree for efficient rendering.
 *
 * Flattens the tree into a visible-items list based on which folders
 * are expanded, then feeds that list to @tanstack/react-virtual.
 *
 * @param tree - Root-level tree nodes
 * @param expandedFolders - Set of folder IDs that are currently expanded
 * @param scrollElementRef - Ref to the scrollable container element
 * @param creatingFolderId - ID of folder where new item is being created (optional)
 *
 * @example
 * ```tsx
 * const scrollRef = useRef<HTMLDivElement>(null);
 * const [expandedFolders, setExpandedFolders] = useState(new Set(['folder-1']));
 *
 * const { visibleItems, virtualItems, totalSize, scrollToNode } = useVirtualizedTree(
 *   fileTree,
 *   expandedFolders,
 *   scrollRef,
 *   creatingFolderId
 * );
 *
 * // Render virtualized list
 * <div ref={scrollRef} style={{ height: '400px', overflow: 'auto' }}>
 *   <div style={{ height: totalSize }}>
 *     {virtualItems.map(virtualItem => {
 *       const item = visibleItems[virtualItem.index];
 *       return (
 *         <div
 *           key={item.key}
 *           style={{ transform: `translateY(${virtualItem.start}px)` }}
 *         >
 *           {item.node?.title}
 *         </div>
 *       );
 *     })}
 *   </div>
 * </div>
 * ```
 */
export function useVirtualizedTree(
  tree: FileTreeNode[],
  expandedFolders: Set<string>,
  scrollElementRef: RefObject<HTMLDivElement | null>,
  creatingFolderId?: string | null,
) {
  // Flatten tree into a list of visible items based on expanded state
  const visibleItems = useMemo(() => {
    const items: VisibleTreeItem[] = [];

    function flattenNodes(nodes: FileTreeNode[], depth: number) {
      for (let i = 0; i < nodes.length; i++) {
        const node = nodes[i];
        const isFolder = node.file_type === 'folder';
        const isExpanded = isFolder && expandedFolders.has(node.id);
        const hasChildren = node.children && node.children.length > 0;

        // Add the node itself
        items.push({
          key: node.id,
          type: 'node',
          node,
          depth,
          isFolder,
          isExpanded,
        });

        // For expanded folders, add children and special rows
        if (isFolder && isExpanded) {
          const childDepth = depth + 1;

          // Add create input row if this folder is in creation mode
          if (creatingFolderId === node.id) {
            items.push({
              key: `${node.id}-create`,
              type: 'create-input',
              node: null,
              depth: childDepth,
              isFolder: false,
              isExpanded: false,
              parentFolderId: node.id,
            });
          }

          // Add child nodes if any
          if (hasChildren) {
            flattenNodes(node.children!, childDepth);
          } else if (creatingFolderId !== node.id) {
            // Add empty folder indicator only if not in creation mode
            items.push({
              key: `${node.id}-empty`,
              type: 'empty-folder',
              node: null,
              depth: childDepth,
              isFolder: false,
              isExpanded: false,
              parentFolderId: node.id,
            });
          }
        }
      }
    }

    flattenNodes(tree, 0);
    return items;
  }, [tree, expandedFolders, creatingFolderId]);

  // Estimate size based on item type
  const estimateSize = useCallback(
    (index: number) => {
      const item = visibleItems[index];
      if (item?.type === 'create-input') {
        return CREATE_INPUT_HEIGHT;
      }
      return ITEM_HEIGHT;
    },
    [visibleItems],
  );

  // Create virtualizer instance
  // eslint-disable-next-line react-hooks/incompatible-library
  const virtualizer = useVirtualizer({
    count: visibleItems.length,
    getScrollElement: () => scrollElementRef.current,
    estimateSize,
    overscan: OVERSCAN_COUNT,
  });

  // Scroll a specific node into view by its ID
  const scrollToNode = useCallback(
    (nodeId: string) => {
      const index = visibleItems.findIndex((item) => item.node?.id === nodeId);
      if (index !== -1) {
        virtualizer.scrollToIndex(index, { align: 'auto' });
      }
    },
    [visibleItems, virtualizer],
  );

  return {
    visibleItems,
    virtualizer,
    scrollToNode,
    totalSize: virtualizer.getTotalSize(),
    virtualItems: virtualizer.getVirtualItems(),
  };
}
