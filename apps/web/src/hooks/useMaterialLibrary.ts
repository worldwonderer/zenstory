import { useState, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { materialsApi } from '../lib/materialsApi';
import { logger } from "../lib/logger";
import type {
  LibrarySummaryItem,
  MaterialEntityType,
  MaterialPreviewResponse,
} from '../lib/materialsApi';

export interface PreviewEntityInfo {
  novelId: number;
  entityType: MaterialEntityType;
  entityId: number;
}

export interface MaterialLibraryState {
  /** All completed material libraries */
  libraries: LibrarySummaryItem[];
  /** Loading state for library list */
  isLoading: boolean;
  /** Background fetching state for library list */
  isFetching: boolean;
  /** Error state */
  error: Error | null;
  /** Currently expanded novel IDs */
  expandedNovels: Set<number>;
  /** Currently expanded entity types per novel */
  expandedTypes: Map<string, boolean>;
  /** Toggle novel expansion */
  toggleNovel: (novelId: number) => void;
  /** Toggle entity type expansion */
  toggleEntityType: (novelId: number, entityType: MaterialEntityType) => void;
  /** Whether the reference library section is expanded */
  isExpanded: boolean;
  /** Toggle the reference library section */
  toggleExpanded: () => void;
  /** Current preview data */
  preview: MaterialPreviewResponse | null;
  /** Preview entity info (for import dialog) */
  previewEntityInfo: PreviewEntityInfo | null;
  /** Loading state for preview */
  isPreviewLoading: boolean;
  /** Load preview for an entity */
  loadPreview: (novelId: number, entityType: MaterialEntityType, entityId: number) => Promise<void>;
  /** Clear preview */
  clearPreview: () => void;
}

export function useMaterialLibrary(): MaterialLibraryState {
  const [isExpanded, setIsExpanded] = useState(false);
  const [expandedNovels, setExpandedNovels] = useState<Set<number>>(new Set());
  const [expandedTypes, setExpandedTypes] = useState<Map<string, boolean>>(new Map());
  const [preview, setPreview] = useState<MaterialPreviewResponse | null>(null);
  const [previewEntityInfo, setPreviewEntityInfo] = useState<PreviewEntityInfo | null>(null);
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);

  // Fetch library summary - auto-load when component mounts
  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: ['material-library-summary'],
    queryFn: () => materialsApi.getLibrarySummary(),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });

  const toggleExpanded = useCallback(() => {
    setIsExpanded(prev => !prev);
  }, []);

  const toggleNovel = useCallback((novelId: number) => {
    setExpandedNovels(prev => {
      const next = new Set(prev);
      if (next.has(novelId)) {
        next.delete(novelId);
      } else {
        next.add(novelId);
      }
      return next;
    });
  }, []);

  const toggleEntityType = useCallback((novelId: number, entityType: MaterialEntityType) => {
    const key = `${novelId}:${entityType}`;
    setExpandedTypes(prev => {
      const next = new Map(prev);
      next.set(key, !prev.get(key));
      return next;
    });
  }, []);

  const loadPreview = useCallback(async (
    novelId: number,
    entityType: MaterialEntityType,
    entityId: number,
  ) => {
    setIsPreviewLoading(true);
    try {
      const data = await materialsApi.getPreview(novelId, entityType, entityId);
      setPreview(data);
      setPreviewEntityInfo({ novelId, entityType, entityId });
    } catch (err) {
      logger.error('Failed to load material preview:', err);
    } finally {
      setIsPreviewLoading(false);
    }
  }, []);

  const clearPreview = useCallback(() => {
    setPreview(null);
    setPreviewEntityInfo(null);
  }, []);

  return {
    libraries: data ?? [],
    isLoading,
    isFetching: Boolean(isFetching),
    error: error as Error | null,
    expandedNovels,
    expandedTypes,
    toggleNovel,
    toggleEntityType,
    isExpanded,
    toggleExpanded,
    preview,
    previewEntityInfo,
    isPreviewLoading,
    loadPreview,
    clearPreview,
  };
}
