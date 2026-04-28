/**
 * @fileoverview Content editor component for the zenstory writing workbench.
 *
 * This component provides the main file editing interface, handling:
 * - Rich text editing for outlines, drafts, characters, and lore files
 * - Automatic version creation on file save
 * - Streaming content updates during AI generation
 * - Diff review mode for AI-suggested edits
 * - Virtualized editing for large documents
 * - Material preview and import from reference library
 *
 * The editor automatically selects between SimpleEditor and VirtualizedEditor
 * based on document size for optimal performance.
 *
 * @module components/Editor
 */
import React, { useState, useEffect, useCallback, useRef } from "react";
import { useTranslation } from "react-i18next";
import { useProject } from "../contexts/ProjectContext";
import { useMaterialLibraryContext } from "../contexts/MaterialLibraryContext";
import { useMaterialAttachment } from "../contexts/MaterialAttachmentContext";
import { fileApi, fileVersionApi } from "../lib/api";
import type { FileUpdateVersionIntent } from "../lib/api";
import { ApiError } from "../lib/apiClient";
import { handleApiError } from "../lib/errorHandler";
import { toast } from "../lib/toast";
import { logger } from "../lib/logger";
import { shouldVirtualize } from "../lib/documentChunker";
import { SimpleEditor } from "./SimpleEditor";
import { VirtualizedEditor } from "./VirtualizedEditor";
import { MaterialPreview } from "./MaterialPreview";
import { ImportMaterialDialog } from "./ImportMaterialDialog";
import type { File, FileTreeNode } from "../types";
import { FOLDER_TYPE_MAP } from "../lib/folderTypeMap";
import { FileText, Users, BookOpen, Sparkles, Folder, Zap, Keyboard, ChevronDown } from "lucide-react";
import { LoadingSpinner } from "./LoadingSpinner";
import { UpgradePromptModal } from "./subscription/UpgradePromptModal";
import { buildUpgradeUrl, getUpgradePromptDefinition } from "../config/upgradeExperience";
import { captureException, trackEvent } from "../lib/analytics";

/**
 * Props interface for the Editor component.
 * Currently accepts no props as all state is managed through ProjectContext.
 */
// eslint-disable-next-line @typescript-eslint/no-empty-object-type
export interface EditorProps {}

/**
 * Internal Editor component implementation.
 *
 * Renders the appropriate editor based on context and file state:
 * - MaterialPreview when viewing reference library content
 * - Empty state when no file is selected
 * - Folder hint when a folder is selected
 * - Loading spinner during initial file load
 * - Error message on load failure
 * - VirtualizedEditor for large documents (>10000 words)
 * - SimpleEditor for standard-sized documents
 *
 * Handles AI streaming content display and diff review mode for
 * accepting/rejecting AI-suggested edits.
 *
 * Uses React.memo for the exported component to prevent unnecessary re-renders.
 *
 * @returns The appropriate editor UI based on current state
 */
const EditorComponent: React.FC<EditorProps> = () => {
  const { t } = useTranslation(['editor', 'common']);
  const fileVersionUpgradePrompt = getUpgradePromptDefinition("file_version_quota_blocked");
  const {
    selectedItem,
    currentProjectId,
    streamingFileId,
    streamingContent,
    triggerFileTreeRefresh,
    setSelectedItem,
    editorRefreshVersion,
    lastEditedFileId,
    // Diff review state
    diffReviewState,
    enterDiffReview,
    acceptEdit,
    rejectEdit,
    resetEdit,
    acceptAllEdits,
    rejectAllEdits,
    exitDiffReview,
    applyDiffReviewChanges,
  } = useProject();

  // Material library context
  const materialLib = useMaterialLibraryContext();
  const { addMaterial } = useMaterialAttachment();
  const [importDialogOpen, setImportDialogOpen] = useState(false);

  // Data states
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Creation loading state
  const [isCreating, setIsCreating] = useState<string | null>(null);

  // Empty state more options toggle
  const [showMore, setShowMore] = useState(false);
  const [showFileVersionUpgradeModal, setShowFileVersionUpgradeModal] = useState(false);

  // Local editing states
  const [editTitle, setEditTitle] = useState("");
  const [editContent, setEditContent] = useState("");
  const hasLoadedRef = useRef(false);

  /**
   * Resolve the best parent folder for a new file based on file type.
   *
   * Priority:
   * 1) Canonical deterministic folder ID (<projectId>-<type>-folder)
   * 2) Folder title mapping fallback (for legacy/migrated projects)
   */
  const resolveCreateParentId = useCallback(async (fileType: 'draft' | 'outline' | 'character' | 'lore'): Promise<string | undefined> => {
    if (!currentProjectId) return undefined;

    try {
      const { tree } = await fileApi.getTree(currentProjectId);

      const rootFolders = (tree || []).filter((node) => node.file_type === 'folder');
      const rootFolderIds = new Set(rootFolders.map((node) => node.id));

      const canonicalSuffixByType: Record<'draft' | 'outline' | 'character' | 'lore', string> = {
        draft: 'draft-folder',
        outline: 'outline-folder',
        character: 'character-folder',
        lore: 'lore-folder',
      };

      const canonicalFolderId = `${currentProjectId}-${canonicalSuffixByType[fileType]}`;
      if (rootFolderIds.has(canonicalFolderId)) {
        return canonicalFolderId;
      }

      const queue: FileTreeNode[] = [...(tree || [])];
      while (queue.length > 0) {
        const node = queue.shift();
        if (!node) continue;

        if (node.file_type === 'folder' && FOLDER_TYPE_MAP[node.title] === fileType) {
          return node.id;
        }

        if (node.children?.length) {
          queue.push(...node.children);
        }
      }
    } catch (err) {
      logger.warn('Failed to resolve create parent folder, falling back to root create', err);
    }

    return undefined;
  }, [currentProjectId]);

  /**
   * Loads the file data for the currently selected item.
   *
   * Fetches file content from the API, creates an initial version if none exists,
   * and updates local editing state. Only shows loading spinner on initial load
   * to prevent UI flicker when switching between files.
   */
  const loadData = useCallback(async () => {
    if (!selectedItem || !currentProjectId) {
      setFile(null);
      hasLoadedRef.current = false;
      return;
    }

    // Don't load folder content
    if (selectedItem.type === "folder") {
      setFile(null);
      hasLoadedRef.current = false;
      return;
    }

    // Only show loading state if no file is currently loaded (initial load)
    // This prevents flicker when switching between files
    if (!hasLoadedRef.current) {
      setLoading(true);
    }
    setError(null);

    try {
      const data = await fileApi.get(selectedItem.id);
      setFile(data);
      hasLoadedRef.current = true;
      setEditTitle(data.title);
      setEditContent(data.content || "");

      // Check if file has any versions, create initial version if needed
      try {
        const versions = await fileVersionApi.getVersions(selectedItem.id, { limit: 1 });

        // If no versions exist and file has content, create initial version
        if (versions.total === 0 && data.content) {
          await fileVersionApi.createVersion(selectedItem.id, data.content, {
            changeType: "create",
            changeSource: "system",
            changeSummary: "Initial version",
          });
        }
      } catch (versionErr) {
        if (
          versionErr instanceof ApiError &&
          versionErr.errorCode === "ERR_QUOTA_FILE_VERSIONS_EXCEEDED"
        ) {
          toast.error(handleApiError(versionErr));
          if (fileVersionUpgradePrompt.surface === "modal") {
            setShowFileVersionUpgradeModal(true);
          }
        } else {
          logger.error("Failed to check/create initial version:", versionErr);
        }
      }
    } catch (err: unknown) {
      const error = err as { status?: number };
      if (error?.status !== 401) {
        logger.error("Failed to load data:", err);
        setError(t('editor:placeholder.loadFailed'));
      }
    } finally {
      setLoading(false);
    }
  }, [
    selectedItem,
    currentProjectId,
    t,
    fileVersionUpgradePrompt.surface,
  ]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Track previous streaming file id to detect when streaming ends
  const prevStreamingFileIdRef = useRef<string | null>(null);
  
  // Reload file content when streaming ends for this file
  useEffect(() => {
    const prevId = prevStreamingFileIdRef.current;
    prevStreamingFileIdRef.current = streamingFileId;
    
    // If streaming just ended for the current file, reload to get final content
    if (prevId && prevId === file?.id && streamingFileId === null) {
      // Small delay to ensure backend has updated the content
      setTimeout(() => {
        loadData();
      }, 100);
    }
  }, [streamingFileId, file?.id, loadData]);

  // Reload file content when AI edits the currently selected file
  useEffect(() => {
    if (lastEditedFileId && lastEditedFileId === file?.id && editorRefreshVersion > 0) {
      // Small delay to ensure backend has committed the changes
      setTimeout(() => {
        loadData();
      }, 100);
    }
  }, [editorRefreshVersion, lastEditedFileId, file?.id, loadData]);

  const renderWithUpgradeModal = (content: React.ReactNode) => (
    <>
      {content}
      <UpgradePromptModal
        open={showFileVersionUpgradeModal}
        onClose={() => setShowFileVersionUpgradeModal(false)}
        source={fileVersionUpgradePrompt.source}
        primaryDestination="billing"
        secondaryDestination="pricing"
        title={t("editor:versionHistory.fileVersionLimitTitle", {
          defaultValue: "文件版本额度已达上限",
        })}
        description={t("editor:versionHistory.fileVersionLimitUpgrade", {
          defaultValue:
            "当前套餐可保留的文件版本已达上限。可前往订阅页升级，或先查看套餐对比后再决定。",
        })}
        primaryLabel={t("common:viewUpgrade", { defaultValue: "查看升级方案" })}
        onPrimary={() => {
          window.location.assign(
            buildUpgradeUrl(fileVersionUpgradePrompt.billingPath, fileVersionUpgradePrompt.source)
          );
        }}
        secondaryLabel={t("common:viewPlans", { defaultValue: "查看套餐对比" })}
        onSecondary={() => {
          window.location.assign(
            buildUpgradeUrl(fileVersionUpgradePrompt.pricingPath, fileVersionUpgradePrompt.source)
          );
        }}
      />
    </>
  );

  /**
   * Saves the current file with updated title and content.
   *
   * Updates the file via API, syncs local state, and triggers file tree
   * refresh if the title has changed to keep the navigation in sync.
   */
  const handleSaveFile = async (versionIntent?: FileUpdateVersionIntent) => {
    if (!file?.id) return;

    const titleChanged = editTitle !== file.title;

    try {
      await fileApi.update(file.id, {
        title: editTitle,
        content: editContent,
        ...versionIntent,
      });
    } catch (error) {
      if (
        error instanceof ApiError &&
        error.errorCode === "ERR_QUOTA_FILE_VERSIONS_EXCEEDED"
      ) {
        toast.error(handleApiError(error));
        if (fileVersionUpgradePrompt.surface === "modal") {
          setShowFileVersionUpgradeModal(true);
        }
        return;
      }
      throw error;
    }

    // Update local state
    setFile((prev) => prev ? { ...prev, title: editTitle, content: editContent } : null);

    // If title changed, refresh file tree and update selected item
    if (titleChanged) {
      triggerFileTreeRefresh();
      // Update the selected item title to keep it in sync
      if (selectedItem) {
        setSelectedItem({ ...selectedItem, title: editTitle });
      }
    }
  };

  /**
   * Completes the diff review process and applies accepted changes.
   *
   * Gets the final content after all accept/reject decisions, updates the file,
   * creates a new version for the reviewed changes, and exits review mode.
   */
  const handleFinishReview = useCallback(async () => {
    if (!diffReviewState || !file?.id) return;
    
    // Get the final content based on accept/reject decisions
    const finalContent = applyDiffReviewChanges();
    
    // Update the file with the final content
    try {
      await fileApi.update(file.id, {
        content: finalContent,
        change_type: "ai_edit",
        change_source: "ai",
        change_summary: "AI edit (reviewed)",
      });
      
      // Update local state
      setEditContent(finalContent);
      setFile((prev) => prev ? { ...prev, content: finalContent } : null);
      
      // Exit diff review mode
      exitDiffReview();

      trackEvent("ai_edit_review_applied", {
        project_id: file.project_id,
        file_id: file.id,
        accepted_edit_count: diffReviewState.pendingEdits.filter(
          (edit) => edit.status !== "rejected"
        ).length,
        rejected_edit_count: diffReviewState.pendingEdits.filter(
          (edit) => edit.status === "rejected"
        ).length,
      });
      
      // Refresh file tree
      triggerFileTreeRefresh();
    } catch (err) {
      logger.error("Failed to save reviewed changes:", err);
      captureException(err, {
        feature_area: "editor",
        action: "ai_edit_review_apply",
        file_id: file.id,
      });
    }
  }, [diffReviewState, file?.id, file?.project_id, applyDiffReviewChanges, exitDiffReview, triggerFileTreeRefresh]);

  /**
   * Creates a new file from the empty state action cards.
   *
   * Creates a file with the specified type, refreshes the file tree,
   * selects the new file in the editor, and shows success/error feedback.
   *
   * @param fileType - The type of file to create ('draft', 'outline', 'character', 'lore')
   */
  const handleCreateFromEmptyState = useCallback(async (fileType: 'draft' | 'outline' | 'character' | 'lore') => {
    if (!currentProjectId) {
      toast.error(t('editor:error.noProject', { defaultValue: 'No project selected' }));
      return;
    }

    // Set loading state to prevent multiple clicks
    setIsCreating(fileType);

    // Default titles based on type
    const defaultTitles: Record<string, string> = {
      draft: t('editor:fileTree.newDraft'),
      outline: t('editor:fileTree.newOutline'),
      character: t('editor:fileTree.newCharacter'),
      lore: t('editor:fileTree.newLore'),
    };

    try {
      const parentId = await resolveCreateParentId(fileType);
      const newFile = await fileApi.create(currentProjectId, {
        title: defaultTitles[fileType],
        file_type: fileType,
        parent_id: parentId,
        content: '',
      });

      triggerFileTreeRefresh();
      setSelectedItem({
        id: newFile.id,
        type: newFile.file_type,
        title: newFile.title,
      });

      toast.success(t('editor:success.fileCreated', { defaultValue: 'File created successfully' }));
    } catch (error) {
      toast.error(t('editor:error.createFailed', { defaultValue: 'Failed to create file' }));
      logger.error('Failed to create file:', error);
    } finally {
      setIsCreating(null);
    }
  }, [currentProjectId, triggerFileTreeRefresh, setSelectedItem, t, resolveCreateParentId]);

  // Render material preview mode
  if (materialLib.preview && materialLib.previewEntityInfo) {
    return renderWithUpgradeModal(
      <>
        <MaterialPreview
          preview={materialLib.preview}
          isLoading={materialLib.isPreviewLoading}
          onAddToProject={() => setImportDialogOpen(true)}
          onAttachToChat={() => {
            if (materialLib.preview && materialLib.previewEntityInfo) {
              addMaterial(
                `material_${Date.now()}`,
                materialLib.preview.title,
                {
                  novelId: materialLib.previewEntityInfo.novelId,
                  entityType: materialLib.previewEntityInfo.entityType,
                  entityId: materialLib.previewEntityInfo.entityId,
                }
              );
            }
            materialLib.clearPreview();
          }}
          onBack={() => materialLib.clearPreview()}
        />
        {importDialogOpen && (
          <ImportMaterialDialog
            isOpen={importDialogOpen}
            onClose={() => setImportDialogOpen(false)}
            preview={materialLib.preview}
            novelId={materialLib.previewEntityInfo.novelId}
            entityType={materialLib.previewEntityInfo.entityType}
            entityId={materialLib.previewEntityInfo.entityId}
            onSuccess={() => {
              setImportDialogOpen(false);
              materialLib.clearPreview();
              triggerFileTreeRefresh();
            }}
          />
        )}
      </>
    );
  }

  // Render empty state
  if (!selectedItem) {
    return renderWithUpgradeModal(
      <div className="flex flex-col items-center justify-center h-full p-6 md:p-8 relative overflow-hidden">
        {/* Background ambient glow */}
        <div className="absolute inset-0 bg-gradient-to-br from-[hsl(var(--accent-primary)/0.03)] via-transparent to-[hsl(var(--accent-primary)/0.02)] pointer-events-none" />

        {/* Floating orbs for depth */}
        <div className="absolute top-1/4 left-1/4 w-64 h-64 rounded-full bg-[hsl(var(--accent-primary)/0.05)] blur-3xl pointer-events-none animate-pulse will-change-transform" style={{ animationDuration: '4s' }} />
        <div className="absolute bottom-1/4 right-1/4 w-48 h-48 rounded-full bg-[hsl(var(--accent-primary)/0.04)] blur-2xl pointer-events-none animate-pulse will-change-transform" style={{ animationDuration: '5s', animationDelay: '1s' }} />

        <div className="max-w-md w-full space-y-6 relative z-10">
          {/* Headline */}
          <div className="text-center space-y-3">
            <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-br from-[hsl(var(--accent-primary)/0.15)] to-[hsl(var(--accent-primary)/0.05)] mb-3 shadow-lg shadow-[hsl(var(--accent-primary)/0.1)] transform hover:scale-105 transition-transform duration-300">
              <Sparkles className="w-7 h-7 text-[hsl(var(--accent-primary))]" />
            </div>
            <h2 className="text-xl md:text-2xl font-semibold text-[hsl(var(--text-primary))]">
              {t('editor:emptyStateTitle')}
            </h2>
            <p className="text-sm text-[hsl(var(--text-secondary))]">
              {t('editor:emptyStateDescription')}
            </p>
          </div>

          {/* Primary Actions - 2 cards */}
          <div className="grid grid-cols-2 gap-3">
            {/* Create Draft */}
            <div
              onClick={() => handleCreateFromEmptyState('draft')}
              className={`group relative flex flex-col items-center gap-2.5 p-4 rounded-xl bg-gradient-to-br from-[hsl(var(--bg-secondary))] to-[hsl(var(--bg-tertiary)/0.5)] border border-[hsl(var(--border-color))] hover:border-[hsl(var(--accent-primary)/0.4)] hover:shadow-xl hover:shadow-[hsl(var(--accent-primary)/0.08)] transition-all duration-300 cursor-pointer transform hover:-translate-y-0.5 ${isCreating === 'draft' ? 'opacity-50 pointer-events-none' : ''}`}
            >
              <div className="absolute inset-0 rounded-xl bg-gradient-to-br from-[hsl(var(--accent-primary)/0.1)] to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
              <div className="relative w-11 h-11 rounded-xl bg-gradient-to-br from-[hsl(var(--accent-primary)/0.12)] to-[hsl(var(--accent-primary)/0.06)] flex items-center justify-center group-hover:scale-110 transition-transform duration-300 shadow-sm">
                {isCreating === 'draft' ? <LoadingSpinner size="md" color="primary" /> : <BookOpen className="w-5 h-5 text-[hsl(var(--accent-primary))]" />}
              </div>
              <span className="relative text-sm font-medium text-[hsl(var(--text-primary))] text-center">
                {t('editor:fileTree.newDraft')}
              </span>
            </div>

            {/* Create Outline */}
            <div
              onClick={() => handleCreateFromEmptyState('outline')}
              className={`group relative flex flex-col items-center gap-2.5 p-4 rounded-xl bg-gradient-to-br from-[hsl(var(--bg-secondary))] to-[hsl(var(--bg-tertiary)/0.5)] border border-[hsl(var(--border-color))] hover:border-[hsl(var(--accent-primary)/0.4)] hover:shadow-xl hover:shadow-[hsl(var(--accent-primary)/0.08)] transition-all duration-300 cursor-pointer transform hover:-translate-y-0.5 ${isCreating === 'outline' ? 'opacity-50 pointer-events-none' : ''}`}
            >
              <div className="absolute inset-0 rounded-xl bg-gradient-to-br from-[hsl(var(--accent-primary)/0.1)] to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
              <div className="relative w-11 h-11 rounded-xl bg-gradient-to-br from-[hsl(var(--accent-primary)/0.12)] to-[hsl(var(--accent-primary)/0.06)] flex items-center justify-center group-hover:scale-110 transition-transform duration-300 shadow-sm">
                {isCreating === 'outline' ? <LoadingSpinner size="md" color="primary" /> : <FileText className="w-5 h-5 text-[hsl(var(--accent-primary))]" />}
              </div>
              <span className="relative text-sm font-medium text-[hsl(var(--text-primary))] text-center">
                {t('editor:fileTree.newOutline')}
              </span>
            </div>
          </div>

          {/* More Options Toggle */}
          <div className="space-y-2">
            <button
              onClick={() => setShowMore(!showMore)}
              className="w-full flex items-center justify-center gap-1.5 text-xs text-[hsl(var(--text-secondary))] hover:text-[hsl(var(--accent-primary))] transition-colors py-2 group"
            >
              <span>{showMore ? t('editor:showLess', { defaultValue: '收起' }) : t('editor:showMore', { defaultValue: '更多选项' })}</span>
              <ChevronDown className={`w-3.5 h-3.5 transition-transform duration-300 ${showMore ? 'rotate-180' : ''}`} />
            </button>

            {/* Secondary Actions - collapsible */}
            {showMore && (
              <div className="grid grid-cols-2 gap-3 animate-fade-in" style={{ animationDuration: '200ms' }}>
                {/* Create Character */}
                <div
                  onClick={() => handleCreateFromEmptyState('character')}
                  className={`group relative flex flex-col items-center gap-2 p-3 rounded-xl bg-gradient-to-br from-[hsl(var(--bg-secondary))] to-[hsl(var(--bg-tertiary)/0.5)] border border-[hsl(var(--border-color))] hover:border-[hsl(var(--accent-primary)/0.4)] hover:shadow-xl hover:shadow-[hsl(var(--accent-primary)/0.08)] transition-all duration-300 cursor-pointer transform hover:-translate-y-0.5 ${isCreating === 'character' ? 'opacity-50 pointer-events-none' : ''}`}
                >
                  <div className="absolute inset-0 rounded-xl bg-gradient-to-br from-[hsl(var(--accent-primary)/0.1)] to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                  <div className="relative w-9 h-9 rounded-lg bg-gradient-to-br from-[hsl(var(--accent-primary)/0.12)] to-[hsl(var(--accent-primary)/0.06)] flex items-center justify-center group-hover:scale-110 transition-transform duration-300">
                    {isCreating === 'character' ? <LoadingSpinner size="sm" color="primary" /> : <Users className="w-4 h-4 text-[hsl(var(--accent-primary))]" />}
                  </div>
                  <span className="relative text-xs font-medium text-[hsl(var(--text-primary))] text-center">
                    {t('editor:fileTree.newCharacter')}
                  </span>
                </div>

                {/* Create Lore */}
                <div
                  onClick={() => handleCreateFromEmptyState('lore')}
                  className={`group relative flex flex-col items-center gap-2 p-3 rounded-xl bg-gradient-to-br from-[hsl(var(--bg-secondary))] to-[hsl(var(--bg-tertiary)/0.5)] border border-[hsl(var(--border-color))] hover:border-[hsl(var(--accent-primary)/0.4)] hover:shadow-xl hover:shadow-[hsl(var(--accent-primary)/0.08)] transition-all duration-300 cursor-pointer transform hover:-translate-y-0.5 ${isCreating === 'lore' ? 'opacity-50 pointer-events-none' : ''}`}
                >
                  <div className="absolute inset-0 rounded-xl bg-gradient-to-br from-[hsl(var(--accent-primary)/0.1)] to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                  <div className="relative w-9 h-9 rounded-lg bg-gradient-to-br from-[hsl(var(--accent-primary)/0.12)] to-[hsl(var(--accent-primary)/0.06)] flex items-center justify-center group-hover:scale-110 transition-transform duration-300">
                    {isCreating === 'lore' ? <LoadingSpinner size="sm" color="primary" /> : <Sparkles className="w-4 h-4 text-[hsl(var(--accent-primary))]" />}
                  </div>
                  <span className="relative text-xs font-medium text-[hsl(var(--text-primary))] text-center">
                    {t('editor:fileTree.newLore')}
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* Hints Section */}
          <div className="space-y-3 pt-2">
            {/* AI Hint */}
            <div className="flex items-center justify-center gap-2 text-xs text-[hsl(var(--text-secondary))] group cursor-default">
              <div className="p-1.5 rounded-md bg-[hsl(var(--accent-primary)/0.08)] group-hover:bg-[hsl(var(--accent-primary)/0.12)] transition-colors">
                <Zap className="w-3.5 h-3.5 text-[hsl(var(--accent-primary))]" />
              </div>
              <span>{t('editor:emptyStateHint')}</span>
            </div>

            {/* Keyboard Shortcut Hint */}
            <div className="flex items-center justify-center gap-2 text-xs text-[hsl(var(--text-secondary))] group cursor-default">
              <div className="p-1.5 rounded-md bg-[hsl(var(--bg-tertiary))] group-hover:bg-[hsl(var(--accent-primary)/0.08)] transition-colors">
                <Keyboard className="w-3.5 h-3.5" />
              </div>
              <span className="flex items-center gap-1.5">
                <kbd className="px-1.5 py-0.5 rounded bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-color))] text-[10px] font-mono shadow-sm">Ctrl</kbd>
                <kbd className="px-1.5 py-0.5 rounded bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-color))] text-[10px] font-mono shadow-sm">K</kbd>
                <span className="text-[hsl(var(--text-tertiary))]">{t('editor:fileTree.searchFiles')}</span>
              </span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Render folder selected state
  if (selectedItem.type === "folder") {
    return renderWithUpgradeModal(
      <div className="flex flex-col items-center justify-center h-full text-[hsl(var(--text-secondary))] gap-4">
        <Folder size={48} className="opacity-50" />
        <p className="text-sm">{t('editor:placeholder.folderSelected')}{selectedItem.title}</p>
        <p className="text-xs">{t('editor:placeholder.folderHint')}</p>
      </div>
    );
  }

  // Render loading state
  if (loading) {
    return renderWithUpgradeModal(
      <div className="flex flex-col items-center justify-center h-full gap-4">
        <LoadingSpinner size="lg" color="primary" />
        <p className="text-sm text-[hsl(var(--text-secondary))]">{t('common:loading')}</p>
      </div>
    );
  }

  // Render error state
  if (error) {
    return renderWithUpgradeModal(
      <div className="flex items-center justify-center h-full text-[hsl(var(--error))]">
        <p className="text-sm">{error}</p>
      </div>
    );
  }

  // Render file editor for all file types
  if (file) {
    // Check if this file is currently being streamed
    const isStreaming = file.id === streamingFileId;
    const displayContent = isStreaming ? streamingContent : editContent;

    // Check if this file is in diff review mode
    const isInReviewMode = diffReviewState?.isReviewing && diffReviewState.fileId === file.id;

    // Determine if virtualized editor should be used based on document size
    // Threshold: 10000 words (configurable in documentChunker.ts)
    // Temporarily disabled — virtualized editor has spacing issues with large docs
    const useVirtualized = false; // shouldVirtualize(displayContent);

    // Common props for both editors
    const editorProps = {
      fileId: file.id,
      projectId: currentProjectId || undefined,
      fileType: file.file_type,
      fileTitle: editTitle,
      title: editTitle,
      content: displayContent,
      onTitleChange: setEditTitle,
      onContentChange: setEditContent,
      onSave: handleSaveFile,
      isStreaming,
      onEnterDiffReview: enterDiffReview,
      // Diff review props
      diffReviewState: isInReviewMode ? diffReviewState : null,
      onAcceptEdit: acceptEdit,
      onRejectEdit: rejectEdit,
      onResetEdit: resetEdit,
      onAcceptAllEdits: acceptAllEdits,
      onRejectAllEdits: rejectAllEdits,
      onFinishReview: handleFinishReview,
    };

    // Use VirtualizedEditor for large documents, SimpleEditor for small ones
    return renderWithUpgradeModal(
      useVirtualized ? (
        <VirtualizedEditor {...editorProps} />
      ) : (
        <SimpleEditor {...editorProps} />
      )
    );
  }

  return renderWithUpgradeModal(null);
};

export const Editor = React.memo(EditorComponent);
