/**
 * @fileoverview VersionHistoryPanel component - Version history viewer for project files.
 *
 * This component provides a modal panel for viewing and managing version snapshots,
 * handling:
 * - Snapshot history display with file/folder counts
 * - Snapshot description editing
 * - Version rollback with confirmation
 * - Side-by-side version comparison
 * - Real-time snapshot loading with error handling
 * - Mobile-responsive layout
 *
 * @module components/VersionHistoryPanel
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Clock,
  RotateCcw,
  GitCompare,
  Edit2,
  X,
  Check,
  AlertCircle,
} from 'lucide-react';
import { logger } from '../lib/logger';
import { versionApi } from '../lib/api';
import { formatRelativeTimeWithYear } from '../lib/dateUtils';
import type { Snapshot } from '../types';
import { SnapshotComparisonDialog } from './SnapshotComparisonDialog';
import { useIsMobile } from '../hooks/useMediaQuery';

/**
 * Extended snapshot type with computed summary information.
 * Contains file and folder counts parsed from the snapshot data.
 */
interface SnapshotWithSummary extends Snapshot {
  /** Computed summary containing parsed file and folder counts */
  summary: {
    /** Number of file versions in this snapshot */
    file_count: number;
    /** Number of folders in this snapshot */
    folder_count: number;
  };
}

/**
 * Props for the VersionHistoryPanel component.
 */
interface VersionHistoryPanelProps {
  /** ID of the project to load snapshots for */
  projectId: string;
  /** Optional file ID to filter snapshots by specific file */
  outlineId?: string;
  /** Callback invoked when the panel is closed */
  onClose: () => void;
  /** Callback invoked after a successful rollback operation */
  onRollback?: (snapshotId: string) => void;
  /** Callback invoked when comparing two snapshots */
  onCompare?: (snapshot1Id: string, snapshot2Id: string) => void;
}

export const VersionHistoryPanel: React.FC<VersionHistoryPanelProps> = ({
  projectId,
  outlineId,
  onClose,
  onRollback,
  onCompare,
}) => {
  const isMobile = useIsMobile();
  const { t } = useTranslation(['editor', 'common']);
  const [snapshots, setSnapshots] = useState<SnapshotWithSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDescription, setEditDescription] = useState('');
  const [selectedForCompare, setSelectedForCompare] = useState<string[]>([]);
  const [showComparison, setShowComparison] = useState(false);

  const loadSnapshots = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await versionApi.getSnapshots(projectId, {
        fileId: outlineId,
        limit: 50,
      });

      // Parse data field to compute summary for each snapshot
      const snapshotsWithSummary: SnapshotWithSummary[] = response.map((snapshot) => {
        let fileCount = 0;
        let folderCount = 0;

        try {
          if (snapshot.data) {
            const data = JSON.parse(snapshot.data);
            fileCount = data.file_versions?.length || 0;
            folderCount = data.files_metadata?.filter(
              (f: { file_type?: string }) => f.file_type === 'folder'
            )?.length || 0;
          }
        } catch (e) {
          logger.warn('Failed to parse snapshot data:', e);
        }

        return {
          ...snapshot,
          summary: {
            file_count: fileCount,
            folder_count: folderCount,
          },
        };
      });

      setSnapshots(snapshotsWithSummary);
    } catch (err) {
      setError(t('editor:versionHistory.loadFailed'));
      logger.error('Failed to load snapshots:', err);
    } finally {
      setLoading(false);
    }
  }, [projectId, outlineId, t]);

  useEffect(() => {
    loadSnapshots();
  }, [loadSnapshots]);

  const handleSaveDescription = async (snapshotId: string) => {
    try {
      await versionApi.updateSnapshot(snapshotId, { description: editDescription });
      setEditingId(null);
      setEditDescription('');
      loadSnapshots();
    } catch (err) {
      logger.error('Failed to update description:', err);
    }
  };

  const handleRollback = async (snapshotId: string) => {
    if (!confirm(t('editor:versionHistory.confirmRollback'))) {
      return;
    }

    try {
      await versionApi.rollback(snapshotId);
      loadSnapshots();
      if (onRollback) {
        onRollback(snapshotId);
      }
    } catch (err) {
      logger.error('Rollback failed:', err);
      alert(t('editor:versionHistory.rollbackFailed'));
    }
  };

  const handleSelectForCompare = (snapshotId: string) => {
    if (selectedForCompare.includes(snapshotId)) {
      setSelectedForCompare(selectedForCompare.filter((id) => id !== snapshotId));
    } else if (selectedForCompare.length < 2) {
      setSelectedForCompare([...selectedForCompare, snapshotId]);
    } else {
      // Replace the older selection
      setSelectedForCompare([selectedForCompare[1], snapshotId]);
    }
  };

  const handleCompare = () => {
    if (selectedForCompare.length === 2) {
      setShowComparison(true);
      if (onCompare) {
        onCompare(selectedForCompare[0], selectedForCompare[1]);
      }
    }
  };


  const getTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      auto: t('editor:versionHistory.auto'),
      manual: t('editor:versionHistory.manual'),
      pre_ai_edit: t('editor:versionHistory.beforeAI'),
      pre_rollback: t('editor:versionHistory.beforeRollback'),
    };
    return labels[type] || type;
  };

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className={`bg-[hsl(var(--bg-secondary))] rounded-2xl flex flex-col shadow-2xl ${
        isMobile ? 'w-full max-h-[80vh]' : 'max-w-3xl w-full max-h-[80vh]'
      }`}>
        {/* Header */}
        <div className="flex items-center justify-between p-4">
          <div className="flex items-center gap-2">
            <Clock className="w-5 h-5 text-[hsl(var(--accent-primary))]" />
            <h2 className="text-lg font-semibold text-[hsl(var(--text-primary))]">{t('editor:versionHistory.title')}</h2>
          </div>

          <div className="flex items-center gap-2">

            {selectedForCompare.length === 2 && (
              <button
                onClick={handleCompare}
                className="flex items-center gap-1 px-3 py-1.5 bg-[hsl(var(--accent-primary))] text-white rounded-md text-sm hover:bg-[hsl(var(--accent-primary-hover))]"
              >
                <GitCompare className="w-4 h-4" />
                {t('editor:versionHistory.compare')}
              </button>
            )}

            <button
              onClick={onClose}
              className="p-1.5 hover:bg-[hsl(var(--bg-tertiary))] rounded-md text-[hsl(var(--text-primary))]"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4">
          {loading && (
            <div className="text-center text-[hsl(var(--text-secondary))] py-8">{t('common:loading')}</div>
          )}

          {error && (
            <div className="flex items-center gap-2 text-[hsl(var(--error))] p-4 bg-[hsl(var(--error)/0.1)] rounded-lg">
              <AlertCircle className="w-5 h-5" />
              <span>{error}</span>
            </div>
          )}

          {!loading && !error && snapshots.length === 0 && (
            <div className="text-center text-[hsl(var(--text-secondary))] py-8">{t('editor:versionHistory.empty')}</div>
          )}

          {!loading && !error && snapshots.length > 0 && (
            <div className="space-y-3">
              {snapshots.map((snapshot, index) => {
                const snapshotId = snapshot.id;
                const isSelectable = typeof snapshotId === 'string' && snapshotId.length > 0;
                const isSelected = isSelectable ? selectedForCompare.includes(snapshotId) : false;

                return (
                <div
                  key={isSelectable ? snapshotId : `snapshot-${index}`}
                  className={`border rounded-lg p-4 transition-colors ${
                    isSelected
                      ? 'border-[hsl(var(--accent-primary))] bg-[hsl(var(--accent-primary)/0.1)]'
                      : 'border-[hsl(var(--border-color))] bg-[hsl(var(--bg-tertiary))] hover:bg-[hsl(var(--bg-hover))]'
                  }`}
                >
                  {/* Header Row */}
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex-1">
                      {index === 0 && (
                        <span className="inline-block px-2 py-0.5 text-xs bg-[hsl(var(--success))] text-white rounded mr-2">
                          {t('editor:versionHistory.currentVersion')}
                        </span>
                      )}
                      <span className="text-xs text-[hsl(var(--text-secondary))]">
                        {getTypeLabel(snapshot.snapshot_type || 'auto')}
                      </span>
                      <div className="text-sm text-[hsl(var(--text-primary))] mt-1">
                        {snapshot.created_at ? formatRelativeTimeWithYear(snapshot.created_at) : '-'}
                      </div>
                    </div>

                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => {
                          if (snapshotId) handleSelectForCompare(snapshotId);
                        }}
                        disabled={!isSelectable}
                        className={`p-1.5 rounded ${
                          isSelected
                            ? 'bg-[hsl(var(--accent-primary))] text-white'
                            : 'hover:bg-[hsl(var(--bg-hover))] text-[hsl(var(--text-primary))]'
                        } ${!isSelectable ? 'opacity-50 cursor-not-allowed' : ''}`}
                        title={t('editor:versionHistory.selectCompare')}
                      >
                        <GitCompare className="w-4 h-4" />
                      </button>

                      {index !== 0 && (
                        <button
                          onClick={() => {
                            if (snapshotId) handleRollback(snapshotId);
                          }}
                          disabled={!isSelectable}
                          className={`p-1.5 hover:bg-[hsl(var(--bg-hover))] rounded text-[hsl(var(--text-primary))] ${!isSelectable ? 'opacity-50 cursor-not-allowed' : ''}`}
                          title={t('editor:versionHistory.rollbackTo')}
                        >
                          <RotateCcw className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Description */}
                  {editingId === snapshot.id ? (
                    <div className="flex items-center gap-2 mb-2">
                      <input
                        type="text"
                        value={editDescription}
                        onChange={(e) => setEditDescription(e.target.value)}
                        className="flex-1 px-2 py-1 bg-[hsl(var(--bg-tertiary))] border border-[hsl(var(--border-color))] rounded text-sm text-[hsl(var(--text-primary))]"
                        placeholder={t('editor:versionHistory.addDescription')}
                        autoFocus
                      />
                      <button
                        onClick={() => {
                          if (snapshotId) handleSaveDescription(snapshotId);
                        }}
                        disabled={!isSelectable}
                        className={`p-1.5 bg-[hsl(var(--success))] text-white rounded hover:bg-[hsl(var(--success-dark))] ${!isSelectable ? 'opacity-50 cursor-not-allowed' : ''}`}
                      >
                        <Check className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => {
                          setEditingId(null);
                          setEditDescription('');
                        }}
                        className="p-1.5 bg-[hsl(var(--bg-tertiary))] text-[hsl(var(--text-primary))] rounded hover:bg-[hsl(var(--bg-hover))]"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  ) : (
                    <div className="flex items-start gap-2 mb-2">
                      <p className="flex-1 text-sm text-[hsl(var(--text-secondary))]">
                        {snapshot.description || (
                          <span className="text-[hsl(var(--text-secondary))]">{t('editor:versionHistory.noDescription')}</span>
                        )}
                      </p>
                      <button
                        onClick={() => {
                          if (!snapshotId) return;
                          setEditingId(snapshotId);
                          setEditDescription(snapshot.description || '');
                        }}
                        disabled={!isSelectable}
                        className={`p-1 hover:bg-[hsl(var(--bg-hover))] rounded text-[hsl(var(--text-secondary))] ${!isSelectable ? 'opacity-50 cursor-not-allowed' : ''}`}
                      >
                        <Edit2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  )}

                  {/* Summary */}
                  <div className="flex items-center gap-4 text-xs text-[hsl(var(--text-secondary))]">
                    <span>{snapshot.summary.file_count} {t('editor:versionHistory.files')}</span>
                    <span>{snapshot.summary.folder_count} {t('editor:versionHistory.folders')}</span>
                  </div>
                </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Comparison Dialog */}
      {showComparison && selectedForCompare.length === 2 && (
        <SnapshotComparisonDialog
          snapshotId1={selectedForCompare[0]}
          snapshotId2={selectedForCompare[1]}
          onClose={() => {
            setShowComparison(false);
            setSelectedForCompare([]);
          }}
        />
      )}
    </div>
  );
};

export default VersionHistoryPanel;
