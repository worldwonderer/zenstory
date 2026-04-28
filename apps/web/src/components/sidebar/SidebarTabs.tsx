import React from "react";
import { useTranslation } from "react-i18next";
import { FolderOpen, Zap, BookOpen } from "lucide-react";
import { useSidebarStore } from "../../stores/sidebarStore";

const tabs = [
  { id: 'files' as const, icon: FolderOpen },
  { id: 'skills' as const, icon: Zap },
  { id: 'materials' as const, icon: BookOpen },
];

export const SidebarTabs: React.FC = () => {
  const { t } = useTranslation(['editor']);
  const { activeTab, setActiveTab } = useSidebarStore();

  const effectiveActiveTab = activeTab === 'dashboard' ? 'files' : activeTab;

  React.useEffect(() => {
    if (activeTab === 'dashboard') {
      setActiveTab('files');
    }
  }, [activeTab, setActiveTab]);

  const handleTabClick = (tabId: 'files' | 'skills' | 'materials') => {
    setActiveTab(tabId);
  };

  return (
    <div className="flex border-b border-[hsl(var(--border-primary))]">
      {tabs.map((tab) => {
        const isActive = effectiveActiveTab === tab.id;
        const Icon = tab.icon;
        return (
          <button
            key={tab.id}
            onClick={() => handleTabClick(tab.id)}
            className={`flex-1 flex flex-col items-center justify-center py-2 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--accent-primary)/0.6)] focus-visible:ring-offset-2 focus-visible:ring-offset-[hsl(var(--bg-secondary))] ${
              isActive
                ? "text-[hsl(var(--accent-primary))] border-b-2 border-[hsl(var(--accent-primary))]"
                : "text-[hsl(var(--text-secondary))]"
            }`}
          >
            <Icon size={18} />
            <span className="text-xs mt-0.5">
              {t(`editor:sidebar.${tab.id}`)}
            </span>
          </button>
        );
      })}
    </div>
  );
};
