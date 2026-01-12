'use client';

import { useState } from 'react';
import { Header } from '@/components/shared/Header';
import { TabNavigation, type TabId } from '@/components/shared/TabNavigation';
import { ChatTab } from '@/components/chat/ChatTab';
import { VisionTab } from '@/components/vision/VisionTab';
import { TTSTab } from '@/components/speech/TTSTab';
import { STTTab } from '@/components/speech/STTTab';
import { motion, AnimatePresence } from 'framer-motion';

export default function Home() {
  const [activeTab, setActiveTab] = useState<TabId>('chat');

  const renderTab = () => {
    switch (activeTab) {
      case 'chat':
        return <ChatTab />;
      case 'vision':
        return <VisionTab />;
      case 'tts':
        return <TTSTab />;
      case 'stt':
        return <STTTab />;
      default:
        return <ChatTab />;
    }
  };

  return (
    <div className="min-h-screen flex flex-col">
      <Header />

      <main className="flex-1 container mx-auto px-4 py-6">
        <div className="mb-6">
          <TabNavigation activeTab={activeTab} onTabChange={setActiveTab} />
        </div>

        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.15 }}
            className="h-[calc(100vh-180px)]"
          >
            {renderTab()}
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  );
}
