import { Activity, BarChart3, Cog, Database, FileText, TestTube2 } from 'lucide-react';
import clsx from 'clsx';
import { useAppStore, Tab } from '../stores/appStore';

const navItems: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: 'status', label: 'Status', icon: <Activity className="w-5 h-5" /> },
  { id: 'dashboard', label: 'Dashboard', icon: <BarChart3 className="w-5 h-5" /> },
  { id: 'config', label: 'Config', icon: <Cog className="w-5 h-5" /> },
  { id: 'models', label: 'Models', icon: <Database className="w-5 h-5" /> },
  { id: 'logs', label: 'Logs', icon: <FileText className="w-5 h-5" /> },
  { id: 'tests', label: 'Tests', icon: <TestTube2 className="w-5 h-5" /> },
];

export function Sidebar() {
  const { activeTab, setActiveTab } = useAppStore();

  return (
    <aside className="w-56 bg-gray-800 border-r border-gray-700 flex flex-col">
      <div className="p-4 border-b border-gray-700">
        <h1 className="text-lg font-bold text-white flex items-center gap-2">
          <span className="text-blue-400">AI</span> Command Center
        </h1>
        <p className="text-xs text-gray-400 mt-1">Local LLM Gateway</p>
      </div>

      <nav className="flex-1 p-3 space-y-1">
        {navItems.map((item) => (
          <button
            key={item.id}
            onClick={() => setActiveTab(item.id)}
            className={clsx(
              'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
              activeTab === item.id
                ? 'bg-blue-600 text-white'
                : 'text-gray-300 hover:bg-gray-700 hover:text-white'
            )}
          >
            {item.icon}
            {item.label}
          </button>
        ))}
      </nav>

      <div className="p-4 border-t border-gray-700">
        <div className="text-xs text-gray-500">
          <p>v1.0.0</p>
          <p className="mt-1">localhost:4000</p>
        </div>
      </div>
    </aside>
  );
}
