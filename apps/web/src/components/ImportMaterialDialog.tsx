import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useProject } from '../contexts/ProjectContext';
import { fileApi } from '../lib/api';
import { materialsApi } from '../lib/materialsApi';
import Modal from './ui/Modal';
import type { MaterialPreviewResponse, MaterialEntityType } from '../lib/materialsApi';
import type { FileTreeNode } from '../types';
import { logger } from "../lib/logger";

interface ImportMaterialDialogProps {
  isOpen: boolean;
  onClose: () => void;
  preview: MaterialPreviewResponse;
  novelId: number;
  entityType: MaterialEntityType;
  entityId: number;
  onSuccess: (fileId: string, folderName: string) => void;
}

export const ImportMaterialDialog: React.FC<ImportMaterialDialogProps> = ({
  isOpen,
  onClose,
  preview,
  novelId,
  entityType,
  entityId,
  onSuccess,
}) => {
  const { t } = useTranslation(['editor', 'common']);
  const { currentProjectId } = useProject();
  const [fileName, setFileName] = useState(preview.suggested_file_name);
  const [targetFolderId, setTargetFolderId] = useState<string | null>(null);
  const [folders, setFolders] = useState<{ id: string; title: string }[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load project folders
  useEffect(() => {
    if (!isOpen || !currentProjectId) return;

    const loadFolders = async () => {
      try {
        const response = await fileApi.getTree(currentProjectId);
        const folderList = response.tree
          .filter((n: FileTreeNode) => n.file_type === 'folder')
          .map((n: FileTreeNode) => ({ id: n.id, title: n.title }));
        setFolders(folderList);

        // Auto-select recommended folder
        const recommended = folderList.find(
          (f: { id: string; title: string }) => f.title === preview.suggested_folder_name
        );
        if (recommended) {
          setTargetFolderId(recommended.id);
        } else {
          setTargetFolderId(null);
        }
      } catch (err) {
        logger.error('Failed to load folders:', err);
      }
    };

    loadFolders();
  }, [isOpen, currentProjectId, preview.suggested_folder_name]);

  // Reset state when dialog opens
  useEffect(() => {
    if (isOpen) {
      setFileName(preview.suggested_file_name);
      setTargetFolderId(null);
      setError(null);
    }
  }, [isOpen, preview.suggested_file_name]);

  const handleSubmit = async () => {
    if (!currentProjectId || isSubmitting) return;

    setIsSubmitting(true);
    setError(null);
    try {
      const result = await materialsApi.importToProject({
        project_id: currentProjectId,
        novel_id: novelId,
        entity_type: entityType,
        entity_id: entityId,
        file_name: fileName || undefined,
        target_folder_id: targetFolderId || undefined,
      });

      onSuccess(result.file_id, result.folder_name);
      onClose();
    } catch (err) {
      logger.error('Failed to import material:', err);
      setError(t('editor:fileTree.importDialog.importFailed'));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      open={isOpen}
      onClose={onClose}
      size="sm"
    >
      <Modal.Header>{t('editor:fileTree.importDialog.title')}</Modal.Header>

      <Modal.Body className="space-y-4">
        {/* Error message */}
        {error && (
          <div className="p-3 text-sm text-[hsl(var(--error))] bg-[hsl(var(--error)/0.1)] rounded border border-[hsl(var(--error)/0.3)]">
            {error}
          </div>
        )}

        {/* File name input */}
        <div>
          <label className="block text-sm text-[hsl(var(--text-secondary))] mb-1">
            {t('editor:fileTree.importDialog.fileName')}
          </label>
          <input
            type="text"
            value={fileName}
            onChange={(e) => setFileName(e.target.value)}
            className="w-full px-3 py-2 text-sm rounded border border-[hsl(var(--border-primary))] bg-[hsl(var(--bg-secondary))] text-[hsl(var(--text-primary))] focus:outline-none focus:border-[hsl(var(--accent-primary))]"
          />
        </div>

        {/* Target folder select */}
        <div>
          <label className="block text-sm text-[hsl(var(--text-secondary))] mb-1">
            {t('editor:fileTree.importDialog.targetFolder')}
          </label>
          <select
            value={targetFolderId || ''}
            onChange={(e) => setTargetFolderId(e.target.value || null)}
            className="w-full px-3 py-2 text-sm rounded border border-[hsl(var(--border-primary))] bg-[hsl(var(--bg-secondary))] text-[hsl(var(--text-primary))] focus:outline-none focus:border-[hsl(var(--accent-primary))]"
          >
            <option value="">
              {preview.suggested_folder_name} ({t('editor:fileTree.importDialog.recommended')})
            </option>
            {folders
              .filter((f) => f.title !== preview.suggested_folder_name)
              .map((f) => (
                <option key={f.id} value={f.id}>
                  {f.title}
                </option>
              ))}
          </select>
        </div>
      </Modal.Body>

      <Modal.Footer>
        <button
          onClick={onClose}
          className="px-4 py-2 text-sm rounded border border-[hsl(var(--border-primary))] text-[hsl(var(--text-secondary))] hover:bg-[hsl(var(--bg-tertiary))] transition-colors"
        >
          {t('editor:fileTree.importDialog.cancel')}
        </button>
        <button
          onClick={handleSubmit}
          disabled={isSubmitting || !fileName.trim()}
          className="px-4 py-2 text-sm rounded bg-[hsl(var(--accent-primary))] text-white hover:opacity-90 transition-opacity disabled:opacity-50"
        >
          {isSubmitting ? t('common:loading') : t('editor:fileTree.importDialog.confirm')}
        </button>
      </Modal.Footer>
    </Modal>
  );
};
