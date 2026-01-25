import { create } from 'zustand';

export type Tab = 'status' | 'dashboard' | 'config' | 'models' | 'logs';

interface AppState {
  activeTab: Tab;
  setActiveTab: (tab: Tab) => void;
}

export const useAppStore = create<AppState>((set) => ({
  activeTab: 'status',
  setActiveTab: (tab) => set({ activeTab: tab }),
}));
