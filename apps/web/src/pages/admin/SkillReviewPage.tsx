import { useState, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { LazyMarkdown } from "../../components/LazyMarkdown";
import { Check, X, Zap, ChevronDown, ChevronUp, AlertTriangle, RefreshCw } from "lucide-react";
import { AdminPageState } from "../../components/admin";
import { adminApi, type PendingSkill } from "../../lib/adminApi";
import { logger } from "../../lib/logger";

export default function SkillReviewPage() {
  const { t } = useTranslation(["admin", "common"]);
  const [skills, setSkills] = useState<PendingSkill[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [processingId, setProcessingId] = useState<string | null>(null);
  const [rejectingId, setRejectingId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState("");

  const loadPendingSkills = useCallback(async (showLoadingIndicator = true) => {
    setLoadError(null);
    try {
      if (showLoadingIndicator) {
        setLoading(true);
      }
      const data = await adminApi.getPendingSkills();
      setSkills(Array.isArray(data) ? data : []);
    } catch (error) {
      logger.error("Failed to load pending skills:", error);
      const fallbackError = t("admin:dashboard.loadError", "加载失败，请稍后重试");
      setLoadError(error instanceof Error && error.message ? error.message : fallbackError);
    } finally {
      if (showLoadingIndicator) {
        setLoading(false);
      }
    }
  }, [t]);

  useEffect(() => {
    void loadPendingSkills();
  }, [loadPendingSkills]);

  const handleApprove = async (skillId: string) => {
    try {
      setProcessingId(skillId);
      await adminApi.approveSkill(skillId);
      setSkills((prev) => prev.filter((s) => s.id !== skillId));
      // Refresh without loading indicator to avoid flashing
      await loadPendingSkills(false);
    } catch (error) {
      logger.error("Failed to approve skill:", error);
    } finally {
      setProcessingId(null);
    }
  };

  const handleReject = async (skillId: string) => {
    try {
      setProcessingId(skillId);
      await adminApi.rejectSkill(skillId, rejectReason || undefined);
      setSkills((prev) => prev.filter((s) => s.id !== skillId));
      setRejectingId(null);
      setRejectReason("");
      // Refresh without loading indicator to avoid flashing
      await loadPendingSkills(false);
    } catch (error) {
      logger.error("Failed to reject skill:", error);
    } finally {
      setProcessingId(null);
    }
  };

  const hasBlockingError = Boolean(loadError) && skills.length === 0;
  const displayError = loadError ?? t("admin:dashboard.loadError", "加载失败，请稍后重试");

  return (
    <div className="admin-page">
      <div>
        <h1 className="admin-page-title">
          {t("admin:skills.title", "技能审核")}
        </h1>
        <p className="admin-page-subtitle">
          {t("admin:skills.description", "审核社区提交的技能")}
        </p>
      </div>

      {loadError && skills.length > 0 && (
        <div className="mb-4 rounded-lg border border-[hsl(var(--error)/0.3)] bg-[hsl(var(--error)/0.08)] p-4 text-sm">
          <div className="flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 text-[hsl(var(--error))] mt-0.5 shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="font-medium text-[hsl(var(--error))]">
                {t("admin:dashboard.loadError", "加载失败，请稍后重试")}
              </p>
              <p className="mt-1 text-[hsl(var(--text-secondary))] break-words">{loadError}</p>
            </div>
            <button
              onClick={() => void loadPendingSkills(true)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-[hsl(var(--separator-color))] px-3 py-1.5 text-xs text-[hsl(var(--text-primary))] hover:bg-[hsl(var(--bg-tertiary))] transition-colors"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              {t("common:retry")}
            </button>
          </div>
        </div>
      )}

      <AdminPageState
        isLoading={loading}
        isError={hasBlockingError}
        isEmpty={skills.length === 0}
        loadingText={t("common:loading")}
        errorText={displayError}
        emptyText={t("admin:skills.noPending", "没有待审核的技能")}
        retryText={t("common:retry")}
        onRetry={() => {
          void loadPendingSkills(true);
        }}
      >
        <div className="space-y-4">
          {skills.map((skill) => (
            <SkillReviewCard
              key={skill.id}
              skill={skill}
              onApprove={() => handleApprove(skill.id)}
              onReject={() => setRejectingId(skill.id)}
              processing={processingId === skill.id}
            />
          ))}
        </div>
      </AdminPageState>

      {/* Reject Modal */}
      {rejectingId && (
        <RejectModal
          onConfirm={() => handleReject(rejectingId)}
          onCancel={() => {
            setRejectingId(null);
            setRejectReason("");
          }}
          reason={rejectReason}
          setReason={setRejectReason}
          processing={processingId === rejectingId}
        />
      )}
    </div>
  );
}

function SkillReviewCard({
  skill,
  onApprove,
  onReject,
  processing,
}: {
  skill: PendingSkill;
  onApprove: () => void;
  onReject: () => void;
  processing: boolean;
}) {
  const { t } = useTranslation(["admin"]);
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-[hsl(var(--bg-secondary))] rounded-xl border border-[hsl(var(--border-color))] p-4">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-10 h-10 rounded-lg bg-[hsl(var(--bg-tertiary))] flex items-center justify-center">
              <Zap className="w-5 h-5 text-[hsl(var(--text-secondary))]" />
            </div>
            <div>
              <h3 className="font-semibold text-[hsl(var(--text-primary))]">
                {skill.name}
              </h3>
              <p className="text-xs text-[hsl(var(--text-tertiary))]">
                {t("admin:skills.submittedBy", "提交者")}: {skill.author_name || "Unknown"}
              </p>
            </div>
          </div>
          {skill.description && (
            <p className="text-sm text-[hsl(var(--text-secondary))] mb-2">
              {skill.description}
            </p>
          )}
          <div className="flex items-center gap-2">
            <span className="text-xs px-2 py-0.5 rounded-full bg-[hsl(var(--bg-tertiary))] text-[hsl(var(--text-secondary))]">
              {skill.category}
            </span>
            <span className="text-xs text-[hsl(var(--text-tertiary))]">
              {new Date(skill.created_at).toLocaleDateString()}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={onApprove}
            disabled={processing}
            className="p-2 rounded-lg bg-[hsl(var(--success)/0.1)] text-[hsl(var(--success))] hover:bg-[hsl(var(--success)/0.2)] transition-colors disabled:opacity-50"
            title={t("admin:skills.approve", "批准")}
          >
            {processing ? (
              <div className="w-5 h-5 animate-spin rounded-full border-2 border-[hsl(var(--success))] border-t-transparent" />
            ) : (
              <Check className="w-5 h-5" />
            )}
          </button>
          <button
            onClick={onReject}
            disabled={processing}
            className="p-2 rounded-lg bg-[hsl(var(--error)/0.1)] text-[hsl(var(--error))] hover:bg-[hsl(var(--error)/0.2)] transition-colors disabled:opacity-50"
            title={t("admin:skills.reject", "拒绝")}
          >
            <X className="w-5 h-5" />
          </button>
          <button
            onClick={() => setExpanded(!expanded)}
            className="p-2 rounded-lg text-[hsl(var(--text-secondary))] hover:bg-[hsl(var(--bg-tertiary))] transition-colors"
          >
            {expanded ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
          </button>
        </div>
      </div>

      {expanded && (
        <div className="mt-4 pt-4 border-t border-[hsl(var(--border-color))]">
          <p className="text-xs font-medium text-[hsl(var(--text-tertiary))] mb-2">
            {t("admin:skills.instructions", "指令内容")}
          </p>
          <div className="markdown-content bg-[hsl(var(--bg-tertiary))] rounded-lg p-4 text-sm max-h-64 overflow-y-auto">
            <LazyMarkdown>{skill.instructions}</LazyMarkdown>
          </div>
        </div>
      )}
    </div>
  );
}

function RejectModal({
  onConfirm,
  onCancel,
  reason,
  setReason,
  processing,
}: {
  onConfirm: () => void;
  onCancel: () => void;
  reason: string;
  setReason: (r: string) => void;
  processing: boolean;
}) {
  const { t } = useTranslation(["admin", "common"]);

  return (
    <div className="modal-overlay flex items-center justify-center p-4" onClick={onCancel}>
      <div className="modal w-full max-w-md animate-scale-in" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-lg font-semibold text-[hsl(var(--text-primary))] mb-4">
          {t("admin:skills.rejectTitle", "拒绝技能")}
        </h2>
        <div className="mb-4">
          <label className="block text-sm font-medium text-[hsl(var(--text-secondary))] mb-1">
            {t("admin:skills.rejectReason", "拒绝原因（可选）")}
          </label>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            className="input w-full min-h-[100px] resize-y"
            placeholder={t("admin:skills.rejectPlaceholder", "请输入拒绝原因...")}
          />
        </div>
        <div className="flex gap-3">
          <button onClick={onCancel} className="btn-ghost flex-1 h-11">
            {t("common:cancel")}
          </button>
          <button
            onClick={onConfirm}
            disabled={processing}
            className="btn-danger flex-1 h-11 flex items-center justify-center gap-2"
          >
            {processing && <div className="w-4 h-4 animate-spin rounded-full border-2 border-white border-t-transparent" />}
            {t("admin:skills.confirmReject", "确认拒绝")}
          </button>
        </div>
      </div>
    </div>
  );
}
