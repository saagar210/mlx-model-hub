'use client';

import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';
import { MessageSquare, Eye, Volume2, Mic } from 'lucide-react';

export type TabId = 'chat' | 'vision' | 'tts' | 'stt';

interface Tab {
  id: TabId;
  label: string;
  icon: React.ReactNode;
}

const tabs: Tab[] = [
  { id: 'chat', label: 'Chat', icon: <MessageSquare className="h-4 w-4" /> },
  { id: 'vision', label: 'Vision', icon: <Eye className="h-4 w-4" /> },
  { id: 'tts', label: 'Text to Speech', icon: <Volume2 className="h-4 w-4" /> },
  { id: 'stt', label: 'Speech to Text', icon: <Mic className="h-4 w-4" /> },
];

interface TabNavigationProps {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
}

export function TabNavigation({ activeTab, onTabChange }: TabNavigationProps) {
  return (
    <div className="flex gap-1 p-1 bg-secondary/50 rounded-lg">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onTabChange(tab.id)}
          className={cn(
            'relative flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors',
            activeTab === tab.id
              ? 'text-foreground'
              : 'text-muted-foreground hover:text-foreground'
          )}
        >
          {activeTab === tab.id && (
            <motion.div
              layoutId="activeTab"
              className="absolute inset-0 bg-background rounded-md shadow-sm"
              transition={{ type: 'spring', duration: 0.3 }}
            />
          )}
          <span className="relative z-10 flex items-center gap-2">
            {tab.icon}
            {tab.label}
          </span>
        </button>
      ))}
    </div>
  );
}
