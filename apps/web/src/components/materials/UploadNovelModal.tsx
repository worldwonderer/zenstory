import { useState, useRef, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { X, Upload, FileText, AlertCircle, CheckCircle } from "../icons";
import Modal from "../ui/Modal";
import { materialsApi } from "../../lib/materialsApi";
import {
  resolveMaterialUploadErrorMessage,
  validateMaterialUploadFile,
} from "../../lib/materialUploadValidation";
import type { MaterialUploadResponse } from "../../lib/materialsApi";

interface UploadNovelModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess: (response: MaterialUploadResponse) => void;
}

export function UploadNovelModal({
  open,
  onClose,
  onSuccess,
}: UploadNovelModalProps) {
  const { t } = useTranslation(["materials", "common"]);
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = useCallback(async (selectedFile: File) => {
    const validationError = await validateMaterialUploadFile(selectedFile, t);
    if (validationError) {
      setFile(null);
      setError(validationError);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      return;
    }

    setFile(selectedFile);
    setError(null);

    // Auto-fill title from filename if not set
    if (!title) {
      const filename = selectedFile.name.replace(/\.txt$/, "");
      setTitle(filename);
    }
  }, [t, title]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const droppedFiles = Array.from(e.dataTransfer.files);
    if (droppedFiles.length > 0) {
      void handleFileSelect(droppedFiles[0]);
    }
  }, [handleFileSelect]);

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = e.target.files;
    if (selectedFiles && selectedFiles.length > 0) {
      void handleFileSelect(selectedFiles[0]);
    }
  };

  const handleBrowseClick = () => {
    fileInputRef.current?.click();
  };

  const handleUpload = async () => {
    if (!file) {
      setError(t("materials:uploadModal.errors.noFile"));
      return;
    }

    setUploading(true);
    setUploadProgress(0);
    setError(null);

    try {
      // Simulate progress (since we don't have real progress tracking)
      const progressInterval = setInterval(() => {
        setUploadProgress((prev) => {
          if (prev >= 90) {
            clearInterval(progressInterval);
            return 90;
          }
          return prev + 10;
        });
      }, 200);

      const response = await materialsApi.upload(file, title || undefined);

      clearInterval(progressInterval);
      setUploadProgress(100);

      // Wait a moment to show 100% before closing
      setTimeout(() => {
        onSuccess(response);
        onClose();
      }, 500);
    } catch (err) {
      setError(
        resolveMaterialUploadErrorMessage(
          err,
          t,
          t("materials:uploadModal.errors.uploadFailed")
        )
      );
      setUploadProgress(0);
    } finally {
      setUploading(false);
    }
  };

  const handleRemoveFile = () => {
    setFile(null);
    setError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={t("materials:uploadModal.title")}
      size="md"
      footer={
        <>
          <button
            onClick={onClose}
            disabled={uploading}
            className="btn-ghost flex-1 h-11"
          >
            {t("common:cancel")}
          </button>
          <button
            onClick={handleUpload}
            disabled={!file || uploading}
            className="btn-primary flex-1 h-11 flex items-center justify-center gap-2"
          >
            {uploading ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
                {t("materials:uploadModal.uploading")}
              </>
            ) : (
              <>
                <Upload className="w-4 h-4" />
                {t("materials:uploadModal.upload")}
              </>
            )}
          </button>
        </>
      }
    >
      <div className="space-y-4">
        {/* File Drop Zone */}
        {!file ? (
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={handleBrowseClick}
            className={`
              relative border-2 border-dashed rounded-lg p-8 text-center cursor-pointer
              transition-colors duration-200
              ${
                isDragging
                  ? "border-[hsl(var(--accent-primary))] bg-[hsl(var(--accent-primary))]/5"
                  : "border-[hsl(var(--border-color))] hover:border-[hsl(var(--accent-primary))]/50 hover:bg-[hsl(var(--bg-tertiary))]"
              }
            `}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".txt"
              onChange={handleFileInputChange}
              className="hidden"
            />
            <Upload className="w-12 h-12 mx-auto mb-4 text-[hsl(var(--text-secondary))]" />
            <p className="text-sm font-medium text-[hsl(var(--text-primary))] mb-1">
              {t("materials:uploadModal.clickToSelect")}
            </p>
            <p className="text-xs text-[hsl(var(--text-secondary))]">
              {t("materials:uploadModal.supportedFormats")}
            </p>
          </div>
        ) : (
          /* Selected File Display */
          <div className="p-4 bg-[hsl(var(--bg-tertiary))] rounded-lg">
            <div className="flex items-start gap-3">
              <FileText className="w-5 h-5 text-[hsl(var(--accent-primary))] flex-shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-[hsl(var(--text-primary))] truncate">
                  {file.name}
                </p>
                <p className="text-xs text-[hsl(var(--text-secondary))] mt-1">
                  {(file.size / 1024).toFixed(2)} KB
                </p>
              </div>
              {!uploading && (
                <button
                  onClick={handleRemoveFile}
                  className="p-1 rounded text-[hsl(var(--text-secondary))] hover:bg-[hsl(var(--bg-primary))]"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>
          </div>
        )}

        {/* Title Input */}
        <div>
          <label className="block text-sm font-medium text-[hsl(var(--text-secondary))] mb-2">
            {t("materials:uploadModal.titleLabel")}
            <span className="text-xs text-[hsl(var(--text-tertiary))] ml-2">
              {t("materials:uploadModal.titleOptional")}
            </span>
          </label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder={t("materials:uploadModal.titlePlaceholder")}
            disabled={uploading}
            className="input w-full"
          />
        </div>

        {/* Upload Progress */}
        {uploading && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-[hsl(var(--text-secondary))]">
                {t("materials:uploadModal.uploading")}
              </span>
              <span className="text-[hsl(var(--text-primary))] font-medium">
                {uploadProgress}%
              </span>
            </div>
            <div className="h-2 bg-[hsl(var(--bg-tertiary))] rounded-full overflow-hidden">
              <div
                className="h-full bg-[hsl(var(--accent-primary))] transition-all duration-300"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
          </div>
        )}

        {/* Error Message */}
        {error && (
          <div className="flex items-start gap-2 p-3 bg-[hsl(var(--error))]/10 border border-[hsl(var(--error))]/20 rounded-lg">
            <AlertCircle className="w-4 h-4 text-[hsl(var(--error))] flex-shrink-0 mt-0.5" />
            <p className="text-sm text-[hsl(var(--error))]">{error}</p>
          </div>
        )}

        {/* Success Message */}
        {uploadProgress === 100 && !error && (
          <div className="flex items-start gap-2 p-3 bg-[hsl(var(--success))]/10 border border-[hsl(var(--success))]/20 rounded-lg">
            <CheckCircle className="w-4 h-4 text-[hsl(var(--success))] flex-shrink-0 mt-0.5" />
            <p className="text-sm text-[hsl(var(--success))]">
              {t("materials:uploadModal.success")}
            </p>
          </div>
        )}

        {/* Info Notice */}
        {!uploading && !error && (
          <p className="text-xs text-[hsl(var(--text-tertiary))]">
            {t("materials:uploadModal.supportedFormats")}
          </p>
        )}
      </div>
    </Modal>
  );
}
