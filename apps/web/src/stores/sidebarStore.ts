import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type SidebarTab = 'files' | 'skills' | 'materials' | 'dashboard';

interface SidebarState {
  activeTab: SidebarTab;
  setActiveTab: (tab: SidebarTab) => void;
}

export const useSidebarStore = create<SidebarState>()(
  persist(
    (set) => ({
      activeTab: 'files',
      setActiveTab: (tab) => set({ activeTab: tab }),
    }),
    {
      name: 'zenstory-sidebar-tab',
    }
  )
);
