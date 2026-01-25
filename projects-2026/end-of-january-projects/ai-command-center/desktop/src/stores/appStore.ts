import { create } from 'zustand';

export type Tab = 'status' | 'dashboard' | 'config' | 'models' | 'logs' | 'tests';

interface AppState {
  activeTab: Tab;
  setActiveTab: (tab: Tab) => void;
  isFirstRun: boolean;
  setFirstRun: (value: boolean) => void;
}

export const useAppStore = create<AppState>((set) => ({
  activeTab: 'status',
  setActiveTab: (tab) => set({ activeTab: tab }),
  isFirstRun: false,
  setFirstRun: (value) => set({ isFirstRun: value }),
}));
