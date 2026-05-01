import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Key, Plus, Copy, Trash2, RefreshCw, Shield, ShieldOff, Check, Zap, X } from 'lucide-react';
import { agentApiKeysApi } from '../../lib/api';
import { getLocaleCode } from '../../lib/i18n-helpers';
import type {
  AgentApiKey,
  CreateAgentApiKeyRequest,
} from '../../types';

const SKILL_MD_URL = 'https://api.zenstory.ai/skill.md';

const SCOPES = [
  { value: 'read', labelKey: 'settings:apiKeys.permissions.read' },
  { value: 'write', labelKey: 'settings:apiKeys.permissions.write' },
] as const;

const copyToClipboard = async (text: string): Promise<boolean> => {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
};

const formatDate = (dateStr?: string) => {
  if (!dateStr) return '-';
  return new Date(dateStr).toLocaleDateString(getLocaleCode());
};

function ScopeBadge({ label }: { scope: string; label: string }) {
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-[hsl(var(--bg-tertiary))] text-[hsl(var(--text-secondary))]">
      {label}
    </span>
  );
}

function StatusBadge({ isActive, label }: { isActive: boolean; label: string }) {
  return isActive ? (
    <span className="inline-flex items-center gap-1 text-xs text-green-500">
      <Shield size={12} />
      {label}
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 text-xs text-[hsl(var(--text-secondary))]">
      <ShieldOff size={12} />
      {label}
    </span>
  );
}

function ConfirmDialog({
  title,
  message,
  onConfirm,
  onCancel,
  confirmLabel,
}: {
  title: string;
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
  confirmLabel: string;
}) {
  const { t } = useTranslation('settings');
  return (
    <div role="dialog" aria-modal="true" aria-label={title} className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-[hsl(var(--bg-card))] border border-[hsl(var(--border-color))] rounded-xl p-5 max-w-sm w-full mx-4 shadow-lg">
        <h3 className="text-sm font-medium text-[hsl(var(--text-primary))] mb-2">{title}</h3>
        <p className="text-xs text-[hsl(var(--text-secondary))] mb-4">{message}</p>
        <div className="flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="px-3 py-1.5 rounded-lg text-xs text-[hsl(var(--text-secondary))] hover:bg-[hsl(var(--bg-hover))] transition-colors"
          >
            {t('common.cancel')}
          </button>
          <button
            onClick={onConfirm}
            className="px-3 py-1.5 rounded-lg text-xs text-white bg-red-500 hover:bg-red-600 transition-colors"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

function KeyCreatedModal({
  apiKey,
  onClose,
}: {
  apiKey: string;
  onClose: () => void;
}) {
  const { t, i18n } = useTranslation('settings');
  const [copied, setCopied] = useState(false);
  const [copiedPrompt, setCopiedPrompt] = useState(false);

  const handleCopy = async () => {
    if (await copyToClipboard(apiKey)) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const isZh = i18n.language.startsWith('zh');
  const promptTemplate = isZh
    ? t('apiKeys.agentPromptZh')
    : t('apiKeys.agentPromptEn');

  const agentPrompt = promptTemplate
    .replace(/\{\{skillUrl\}\}/g, SKILL_MD_URL)
    .replace(/\{\{apiKey\}\}/g, apiKey);

  const handleCopyPrompt = async () => {
    if (await copyToClipboard(agentPrompt)) {
      setCopiedPrompt(true);
      setTimeout(() => setCopiedPrompt(false), 2000);
    }
  };

  return (
    <div role="dialog" aria-modal="true" aria-label={t('apiKeys.createdTitle')} className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-[hsl(var(--bg-card))] border border-[hsl(var(--border-color))] rounded-xl p-5 max-w-lg w-full mx-4 shadow-lg">
        <h3 className="text-sm font-medium text-[hsl(var(--text-primary))] mb-2">
          {t('apiKeys.createdTitle')}
        </h3>
        <div className="mb-3 p-2 rounded-lg bg-yellow-500/10 border border-yellow-500/30 text-xs text-yellow-600 dark:text-yellow-400">
          {t('apiKeys.copyWarning')}
        </div>
        <div className="flex items-center gap-2 p-2 rounded-lg bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-color))] mb-4">
          <code className="flex-1 text-xs text-[hsl(var(--text-primary))] break-all font-mono">
            {apiKey}
          </code>
          <button onClick={handleCopy} className="shrink-0 p-1.5 rounded-lg hover:bg-[hsl(var(--bg-hover))] transition-colors text-[hsl(var(--text-secondary))]">
            {copied ? <Check size={14} className="text-green-500" /> : <Copy size={14} />}
          </button>
        </div>

        <div className="mb-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-[hsl(var(--text-primary))]">
              {t('apiKeys.copyPrompt')}
            </span>
            <button onClick={handleCopyPrompt} className="flex items-center gap-1 text-xs text-[hsl(var(--accent-primary))] hover:opacity-80 transition-opacity">
              {copiedPrompt ? <Check size={12} className="text-green-500" /> : <Copy size={12} />}
              {copiedPrompt ? t('apiKeys.copiedPrompt') : t('apiKeys.copyPrompt')}
            </button>
          </div>
          <div className="p-3 rounded-lg bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-color))]">
            <p className="text-xs text-[hsl(var(--text-secondary))] whitespace-pre-wrap font-mono leading-relaxed">
              {agentPrompt}
            </p>
          </div>
        </div>

        <div className="flex justify-end">
          <button
            onClick={onClose}
            className="px-3 py-1.5 rounded-lg text-xs text-[hsl(var(--text-primary))] hover:bg-[hsl(var(--bg-hover))] transition-colors"
          >
            {t('apiKeys.done')}
          </button>
        </div>
      </div>
    </div>
  );
}

function CreateKeyForm({
  onSubmit,
  onCancel,
  isSubmitting,
}: {
  onSubmit: (data: CreateAgentApiKeyRequest) => void;
  onCancel: () => void;
  isSubmitting: boolean;
}) {
  const { t } = useTranslation('settings');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [scopes, setScopes] = useState<string[]>(['read']);
  const [expiresInDays, setExpiresInDays] = useState(0);

  const expirationOptions = [
    { value: 0, label: t('apiKeys.form.never', 'Never expires') },
    { value: 30, label: '30 ' + t('apiKeys.form.days', 'days') },
    { value: 90, label: '90 ' + t('apiKeys.form.days', 'days') },
    { value: 365, label: '365 ' + t('apiKeys.form.days', 'days') },
  ];

  const toggleScope = (scope: string) => {
    setScopes((prev) =>
      prev.includes(scope) ? prev.filter((s) => s !== scope) : [...prev, scope]
    );
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    onSubmit({
      name: name.trim(),
      description: description.trim() || undefined,
      scopes: scopes.length > 0 ? scopes : undefined,
      expires_in_days: expiresInDays || undefined,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-xs font-medium text-[hsl(var(--text-secondary))] mb-1.5">
          {t('apiKeys.form.name')} <span className="text-red-500">*</span>
        </label>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={t('apiKeys.form.namePlaceholder')}
          className="w-full px-3 py-2 rounded-lg border border-[hsl(var(--border-color))] bg-[hsl(var(--bg-secondary))] text-sm text-[hsl(var(--text-primary))] placeholder:text-[hsl(var(--text-secondary))] focus:outline-none focus:ring-1 focus:ring-[hsl(var(--accent-primary))]"
          autoFocus
        />
      </div>

      <div>
        <label className="block text-xs font-medium text-[hsl(var(--text-secondary))] mb-1.5">
          {t('apiKeys.form.description')}
        </label>
        <input
          type="text"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder={t('apiKeys.form.descriptionPlaceholder')}
          className="w-full px-3 py-2 rounded-lg border border-[hsl(var(--border-color))] bg-[hsl(var(--bg-secondary))] text-sm text-[hsl(var(--text-primary))] placeholder:text-[hsl(var(--text-secondary))] focus:outline-none focus:ring-1 focus:ring-[hsl(var(--accent-primary))]"
        />
      </div>

      <div>
        <label className="block text-xs font-medium text-[hsl(var(--text-secondary))] mb-1.5">
          {t('apiKeys.form.permissions')}
        </label>
        <div className="flex gap-3">
          {SCOPES.map((scope) => (
            <label
              key={scope.value}
              className="flex items-center gap-1.5 text-sm text-[hsl(var(--text-primary))] cursor-pointer"
            >
              <input
                type="checkbox"
                checked={scopes.includes(scope.value)}
                onChange={() => toggleScope(scope.value)}
                className="rounded border-[hsl(var(--border-color))] accent-[hsl(var(--accent-primary))]"
              />
              {t(scope.labelKey)}
            </label>
          ))}
        </div>
      </div>

      <div>
        <label className="block text-xs font-medium text-[hsl(var(--text-secondary))] mb-1.5">
          {t('apiKeys.form.expiresAt')}
        </label>
        <select
          value={expiresInDays}
          onChange={(e) => setExpiresInDays(Number(e.target.value))}
          className="w-full px-3 py-2 rounded-lg border border-[hsl(var(--border-color))] bg-[hsl(var(--bg-secondary))] text-sm text-[hsl(var(--text-primary))] focus:outline-none focus:ring-1 focus:ring-[hsl(var(--accent-primary))]"
        >
          {expirationOptions.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      <div className="flex justify-end gap-2 pt-1">
        <button
          type="button"
          onClick={onCancel}
          className="px-3 py-1.5 rounded-lg text-xs text-[hsl(var(--text-secondary))] hover:bg-[hsl(var(--bg-hover))] transition-colors"
        >
          {t('common.cancel')}
        </button>
        <button
          type="submit"
          disabled={!name.trim() || isSubmitting}
          className="px-3 py-1.5 rounded-lg text-xs text-white bg-[hsl(var(--accent-primary))] hover:opacity-90 transition-colors disabled:opacity-50"
        >
          {isSubmitting ? t('common.loading') : t('apiKeys.create')}
        </button>
      </div>
    </form>
  );
}

function TestConnectionButton({ apiKey }: { apiKey: AgentApiKey }) {
  const { t } = useTranslation('settings');
  const [status, setStatus] = useState<'idle' | 'testing' | 'success' | 'error'>('idle');
  const [errorMsg, setErrorMsg] = useState('');

  const handleTest = async () => {
    setStatus('testing');
    setErrorMsg('');
    try {
      const result = await agentApiKeysApi.get(apiKey.id);
      if (result.is_active) {
        setStatus('success');
      } else {
        setStatus('error');
        setErrorMsg(t('apiKeys.status.disabled'));
      }
    } catch (err) {
      setStatus('error');
      setErrorMsg(err instanceof Error ? err.message : String(err));
    }
  };

  if (status === 'success') {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-green-500">
        <Check size={12} />
        {t('apiKeys.testSuccess')}
      </span>
    );
  }

  if (status === 'error') {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-red-500">
        <X size={12} />
        {t('apiKeys.testFailed', { error: errorMsg })}
      </span>
    );
  }

  return (
    <button
      onClick={handleTest}
      disabled={status === 'testing'}
      className="p-1.5 rounded-lg text-[hsl(var(--text-secondary))] hover:bg-[hsl(var(--bg-hover))] transition-colors"
      title={t('apiKeys.testConnection')}
    >
      {status === 'testing' ? (
        <RefreshCw size={14} className="animate-spin" />
      ) : (
        <Zap size={14} />
      )}
    </button>
  );
}

function KeyRow({
  apiKey,
  onRegenerate,
  onDelete,
  onToggleActive,
}: {
  apiKey: AgentApiKey;
  onRegenerate: (key: AgentApiKey) => void;
  onDelete: (key: AgentApiKey) => void;
  onToggleActive: (key: AgentApiKey) => void;
}) {
  const { t } = useTranslation('settings');
  const [copiedPrefix, setCopiedPrefix] = useState(false);

  const handleCopyPrefix = async () => {
    if (await copyToClipboard(apiKey.key_prefix)) {
      setCopiedPrefix(true);
      setTimeout(() => setCopiedPrefix(false), 2000);
    }
  };

  const scopeLabelMap: Record<string, string> = {
    read: t('apiKeys.permissions.read'),
    write: t('apiKeys.permissions.write'),
  };

  return (
    <div className="flex items-center gap-3 p-3 rounded-xl border border-[hsl(var(--border-color))] bg-[hsl(var(--bg-secondary))]">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-sm font-medium text-[hsl(var(--text-primary))] truncate">
            {apiKey.name}
          </span>
          <StatusBadge
            isActive={apiKey.is_active}
            label={apiKey.is_active ? t('apiKeys.status.active') : t('apiKeys.status.disabled')}
          />
        </div>
        <div className="flex items-center gap-2 text-xs text-[hsl(var(--text-secondary))] mb-1.5">
          <code className="font-mono">{apiKey.key_prefix}...</code>
          <button
            onClick={handleCopyPrefix}
            className="p-0.5 rounded hover:bg-[hsl(var(--bg-hover))] transition-colors"
          >
            {copiedPrefix ? (
              <Check size={11} className="text-green-500" />
            ) : (
              <Copy size={11} />
            )}
          </button>
        </div>
        <div className="flex items-center gap-1.5 flex-wrap">
          {apiKey.scopes.map((scope) => (
            <ScopeBadge key={scope} scope={scope} label={scopeLabelMap[scope] || scope} />
          ))}
          <span className="text-xs text-[hsl(var(--text-secondary))] ml-1">
            {t('apiKeys.lastUsed')}: {formatDate(apiKey.last_used_at)}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-1 shrink-0">
        <TestConnectionButton apiKey={apiKey} />
        <button
          onClick={() => onToggleActive(apiKey)}
          title={apiKey.is_active ? t('apiKeys.disable') : t('apiKeys.enable')}
          className="p-1.5 rounded-lg text-[hsl(var(--text-secondary))] hover:bg-[hsl(var(--bg-hover))] transition-colors"
        >
          {apiKey.is_active ? <ShieldOff size={14} /> : <Shield size={14} />}
        </button>
        <button
          onClick={() => onRegenerate(apiKey)}
          title={t('apiKeys.regenerate')}
          className="p-1.5 rounded-lg text-[hsl(var(--text-secondary))] hover:bg-[hsl(var(--bg-hover))] transition-colors"
        >
          <RefreshCw size={14} />
        </button>
        <button
          onClick={() => onDelete(apiKey)}
          title={t('apiKeys.delete')}
          className="p-1.5 rounded-lg text-[hsl(var(--text-secondary))] hover:bg-[hsl(var(--bg-hover))] hover:text-red-500 transition-colors"
        >
          <Trash2 size={14} />
        </button>
      </div>
    </div>
  );
}

export const AgentApiKeysPanel: React.FC = () => {
  const { t } = useTranslation('settings');
  const queryClient = useQueryClient();
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [createdKey, setCreatedKey] = useState<string | null>(null);
  const [confirmAction, setConfirmAction] = useState<{
    title: string;
    message: string;
    confirmLabel: string;
    onConfirm: () => void;
  } | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['agent-api-keys'],
    queryFn: () => agentApiKeysApi.list(),
  });

  const createMutation = useMutation({
    mutationFn: (req: CreateAgentApiKeyRequest) => agentApiKeysApi.create(req),
    onSuccess: (response) => {
      setShowCreateForm(false);
      setCreatedKey(response.key);
      queryClient.invalidateQueries({ queryKey: ['agent-api-keys'] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => agentApiKeysApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agent-api-keys'] });
    },
  });

  const regenerateMutation = useMutation({
    mutationFn: (id: string) => agentApiKeysApi.regenerate(id),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ['agent-api-keys'] });
      setCreatedKey(response.key);
    },
  });

  const toggleActiveMutation = useMutation({
    mutationFn: ({ id, isActive }: { id: string; isActive: boolean }) =>
      agentApiKeysApi.update(id, { is_active: !isActive }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agent-api-keys'] });
    },
  });

  const handleRegenerate = (apiKey: AgentApiKey) => {
    setConfirmAction({
      title: t('apiKeys.regenerateTitle'),
      message: t('apiKeys.regenerateConfirm'),
      confirmLabel: t('apiKeys.regenerate'),
      onConfirm: () => {
        setConfirmAction(null);
        regenerateMutation.mutate(apiKey.id);
      },
    });
  };

  const handleDelete = (apiKey: AgentApiKey) => {
    setConfirmAction({
      title: t('apiKeys.deleteTitle'),
      message: t('apiKeys.deleteConfirm'),
      confirmLabel: t('apiKeys.delete'),
      onConfirm: () => {
        setConfirmAction(null);
        deleteMutation.mutate(apiKey.id);
      },
    });
  };

  const handleToggleActive = (apiKey: AgentApiKey) => {
    toggleActiveMutation.mutate({ id: apiKey.id, isActive: apiKey.is_active });
  };

  const keys = data?.keys ?? [];

  if (isLoading) {
    return (
      <div className="space-y-3 animate-pulse">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="h-20 rounded-xl bg-[hsl(var(--bg-tertiary))] border border-[hsl(var(--border-color))]"
          />
        ))}
      </div>
    );
  }

  if (keys.length === 0 && !showCreateForm) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-center">
        <div className="w-12 h-12 rounded-full bg-[hsl(var(--bg-tertiary))] flex items-center justify-center mb-3">
          <Key size={20} className="text-[hsl(var(--text-secondary))]" />
        </div>
        <h3 className="text-sm font-medium text-[hsl(var(--text-primary))] mb-1">
          {t('apiKeys.noKeys')}
        </h3>
        <p className="text-xs text-[hsl(var(--text-secondary))] mb-4 max-w-xs">
          {t('apiKeys.emptyState')}
        </p>
        <button
          onClick={() => setShowCreateForm(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-white bg-[hsl(var(--accent-primary))] hover:opacity-90 transition-colors"
        >
          <Plus size={14} />
          {t('apiKeys.create')}
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-[hsl(var(--text-primary))]">{t('apiKeys.title')}</h3>
        {!showCreateForm && (
          <button
            onClick={() => setShowCreateForm(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-white bg-[hsl(var(--accent-primary))] hover:opacity-90 transition-colors"
          >
            <Plus size={14} />
            {t('apiKeys.create')}
          </button>
        )}
      </div>

      {showCreateForm && (
        <div className="p-4 rounded-xl border border-[hsl(var(--border-color))] bg-[hsl(var(--bg-secondary))]">
          <CreateKeyForm
            onSubmit={(data) => createMutation.mutate(data)}
            onCancel={() => setShowCreateForm(false)}
            isSubmitting={createMutation.isPending}
          />
        </div>
      )}

      <div className="space-y-2">
        {keys.map((apiKey) => (
          <KeyRow
            key={apiKey.id}
            apiKey={apiKey}
            onRegenerate={handleRegenerate}
            onDelete={handleDelete}
            onToggleActive={handleToggleActive}
          />
        ))}
      </div>

      <div className="p-3 rounded-lg bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-color))]">
        <p className="text-xs text-[hsl(var(--text-secondary))]">
          {t('apiKeys.hintBar')}
        </p>
      </div>

      {confirmAction && (
        <ConfirmDialog
          title={confirmAction.title}
          message={confirmAction.message}
          confirmLabel={confirmAction.confirmLabel}
          onConfirm={confirmAction.onConfirm}
          onCancel={() => setConfirmAction(null)}
        />
      )}

      {createdKey && (
        <KeyCreatedModal apiKey={createdKey} onClose={() => setCreatedKey(null)} />
      )}
    </div>
  );
};

export default AgentApiKeysPanel;
