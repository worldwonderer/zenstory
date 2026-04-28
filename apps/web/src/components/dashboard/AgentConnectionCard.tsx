import React from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import { useNavigate, useLocation } from 'react-router-dom';
import { Key, Plus, RefreshCw, Settings, Zap } from 'lucide-react';
import { agentApiKeysApi } from '../../lib/api';

export function AgentConnectionCard() {
  const { t } = useTranslation('dashboard');
  const navigate = useNavigate();
  const location = useLocation();
  const { data, isError, refetch } = useQuery({
    queryKey: ['agent-api-keys'],
    queryFn: () => agentApiKeysApi.list(),
  });

  const keys = data?.keys ?? [];
  const activeKeys = keys.filter((k) => k.is_active);
  const hasKeys = activeKeys.length > 0;

  const openAgentSettings = () => {
    navigate(location.pathname, { state: { openSettingsTab: 'agent' } });
  };

  // Error state
  if (isError) {
    return (
      <div className="flex items-center gap-3 p-3 rounded-xl border border-[hsl(var(--border-color))] bg-[hsl(var(--bg-secondary))]">
        <div className="flex-shrink-0 w-9 h-9 rounded-lg bg-[hsl(var(--error)/0.1)] flex items-center justify-center">
          <Key size={16} className="text-[hsl(var(--error))]" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-[hsl(var(--text-primary))]">
            {t('agentConnection.errorTitle', { defaultValue: 'Failed to load' })}
          </div>
        </div>
        <button
          onClick={() => refetch()}
          className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs text-[hsl(var(--text-secondary))] hover:bg-[hsl(var(--bg-hover))] transition-colors"
        >
          <RefreshCw size={12} />
          {t('agentConnection.retry', { defaultValue: 'Retry' })}
        </button>
      </div>
    );
  }

  // Connected / active state
  if (hasKeys) {
    return (
      <div
        className="group relative flex items-center gap-3 p-3 rounded-xl border border-[hsl(var(--border-color))] bg-[hsl(var(--bg-secondary))] transition-all duration-200 hover:border-[hsl(var(--success)/0.3)] hover:shadow-[0_0_16px_hsl(var(--success)/0.06)]"
        role="status"
        aria-label={t('agentConnection.activeTitle', { defaultValue: 'AI agent connected' })}
      >
        {/* Green accent strip */}
        <div className="absolute left-0 top-2 bottom-2 w-0.5 rounded-full bg-[hsl(var(--success))]" />

        <div className="flex-shrink-0 w-9 h-9 rounded-lg bg-[hsl(var(--success)/0.1)] flex items-center justify-center ml-1.5">
          <Zap size={16} className="text-[hsl(var(--success))]" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-[hsl(var(--text-primary))]">
            {t('agentConnection.activeTitle', { defaultValue: 'AI agent connected' })}
          </div>
          <div className="text-xs text-[hsl(var(--text-secondary))]">
            {t('agentConnection.keyCount', {
              count: activeKeys.length,
              defaultValue: '{{count}} active key(s)',
            })}
          </div>
        </div>
        <button
          onClick={openAgentSettings}
          className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs text-[hsl(var(--text-secondary))] hover:bg-[hsl(var(--bg-hover))] hover:text-[hsl(var(--text-primary))] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--accent-primary)/0.5)] focus-visible:ring-offset-1"
          aria-label={t('agentConnection.manageKeysAria', { defaultValue: 'Manage API keys' })}
        >
          <Settings size={12} />
          {t('agentConnection.manageKeys', { defaultValue: 'Manage' })}
        </button>
      </div>
    );
  }

  // Empty / invitation state
  return (
    <button
      onClick={openAgentSettings}
      className="group/card w-full relative flex items-center gap-3 p-3 rounded-xl border border-dashed border-[hsl(var(--border-color))] bg-[hsl(var(--bg-secondary))] text-left transition-all duration-200 hover:border-[hsl(var(--accent-primary)/0.35)] hover:bg-[hsl(var(--bg-secondary)/0.8)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--accent-primary)/0.5)] focus-visible:ring-offset-1"
      aria-label={t('agentConnection.createKeyAria', { defaultValue: 'Create an Agent API key' })}
    >
      {/* Animated corner accents on hover */}
      <div className="absolute top-0 left-0 w-4 h-4 border-t-2 border-l-2 border-transparent rounded-tl-xl group-hover/card:border-[hsl(var(--accent-primary)/0.3)] transition-colors duration-300" />
      <div className="absolute bottom-0 right-0 w-4 h-4 border-b-2 border-r-2 border-transparent rounded-br-xl group-hover/card:border-[hsl(var(--accent-primary)/0.3)] transition-colors duration-300" />

      <div className="flex-shrink-0 w-9 h-9 rounded-lg bg-[hsl(var(--bg-tertiary))] flex items-center justify-center group-hover/card:bg-[hsl(var(--accent-primary)/0.1)] transition-colors duration-200">
        <Key size={16} className="text-[hsl(var(--text-secondary))] group-hover/card:text-[hsl(var(--accent-primary))] transition-colors duration-200" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-[hsl(var(--text-primary))]">
          {t('agentConnection.title', { defaultValue: 'Connect your AI agent' })}
        </div>
        <div className="text-xs text-[hsl(var(--text-secondary))] line-clamp-1">
          {t('agentConnection.description', { defaultValue: 'Let Claude Code or OpenClaw directly operate your novel projects' })}
        </div>
      </div>
      <span className="flex-shrink-0 flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium text-white bg-[hsl(var(--accent-primary))] group-hover/card:shadow-[0_0_14px_hsl(var(--accent-primary)/0.3)] transition-shadow duration-200">
        <Plus size={12} />
        {t('agentConnection.createKey', { defaultValue: 'Create Key' })}
      </span>
    </button>
  );
}

export default AgentConnectionCard;
