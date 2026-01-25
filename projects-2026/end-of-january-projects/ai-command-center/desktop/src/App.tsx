import { useEffect, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { Activity, Database, Server, Layers, BarChart3 } from 'lucide-react';
import { Sidebar } from './components/Sidebar';
import { ServiceCard } from './components/ServiceCard';
import { Dashboard } from './components/Dashboard';
import { ConfigEditor } from './components/ConfigEditor';
import { OllamaModels } from './components/OllamaModels';
import { LogViewer } from './components/LogViewer';
import { TestRunner } from './components/TestRunner';
import { SetupWizard } from './components/SetupWizard';
import { useAppStore } from './stores/appStore';
import type { AllHealth } from './lib/types';

const SETUP_COMPLETE_KEY = 'ai-command-center-setup-complete';

function App() {
  const [health, setHealth] = useState<AllHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [showSetup, setShowSetup] = useState(() => {
    return localStorage.getItem(SETUP_COMPLETE_KEY) !== 'true';
  });
  const { activeTab } = useAppStore();

  const handleSetupComplete = () => {
    localStorage.setItem(SETUP_COMPLETE_KEY, 'true');
    setShowSetup(false);
  };

  const fetchHealth = async () => {
    try {
      const result = await invoke<AllHealth>('get_all_health');
      setHealth(result);
    } catch (error) {
      console.error('Failed to fetch health:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 5000);
    return () => clearInterval(interval);
  }, []);

  const healthyCount = health
    ? [health.router, health.litellm, health.ollama, health.redis, health.langfuse]
        .filter((s) => s.healthy).length
    : 0;

  // Show setup wizard on first run
  if (showSetup) {
    return <SetupWizard onComplete={handleSetupComplete} />;
  }

  return (
    <div className="flex h-screen bg-gray-900 text-gray-100">
      <Sidebar />

      <main className="flex-1 p-6 overflow-auto">
        {activeTab === 'status' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h1 className="text-2xl font-bold text-white">Service Status</h1>
            </div>

            {loading ? (
              <div className="text-gray-400">Loading health status...</div>
            ) : health ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <ServiceCard
                  name="Smart Router"
                  icon={<Layers className="w-6 h-6" />}
                  status={health.router}
                  port={4000}
                  managed
                />
                <ServiceCard
                  name="LiteLLM Proxy"
                  icon={<Server className="w-6 h-6" />}
                  status={health.litellm}
                  port={4001}
                  managed
                />
                <ServiceCard
                  name="Ollama"
                  icon={<Activity className="w-6 h-6" />}
                  status={health.ollama}
                  port={11434}
                  external
                />
                <ServiceCard
                  name="Redis"
                  icon={<Database className="w-6 h-6" />}
                  status={health.redis}
                  port={6379}
                  external
                />
                <ServiceCard
                  name="Langfuse"
                  icon={<BarChart3 className="w-6 h-6" />}
                  status={health.langfuse}
                  port={3001}
                  external
                  url="http://localhost:3001"
                />
              </div>
            ) : (
              <div className="text-gray-400">Failed to load health status</div>
            )}

            <div className="mt-8 p-4 bg-gray-800 rounded-lg">
              <h2 className="text-lg font-semibold mb-2 text-white">Quick Summary</h2>
              <p className="text-gray-400">
                {healthyCount}/5 services healthy
              </p>
              {health && !health.router.healthy && !health.litellm.healthy && (
                <p className="text-yellow-400 mt-2 text-sm">
                  Services are managed by LaunchAgents. Run: launchctl start com.aicommandcenter.router
                </p>
              )}
            </div>

            {/* Quick Links */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-gray-800 rounded-lg p-4">
                <h3 className="font-semibold mb-2">API Endpoints</h3>
                <div className="space-y-1 text-sm text-gray-400">
                  <p><code className="text-blue-400">localhost:4000</code> - Smart Router (use this)</p>
                  <p><code className="text-gray-500">localhost:4001</code> - LiteLLM Proxy (internal)</p>
                </div>
              </div>
              <div className="bg-gray-800 rounded-lg p-4">
                <h3 className="font-semibold mb-2">Quick Test</h3>
                <code className="text-xs text-gray-400 block bg-gray-900 p-2 rounded overflow-x-auto">
                  curl localhost:4000/v1/chat/completions -H "Authorization: Bearer sk-command-center-local" -H "Content-Type: application/json" -d '{"{"}\"model\":\"qwen-local\",\"messages\":[{"{"}\"role\":\"user\",\"content\":\"Hi\"{"}"}]{"}"}'
                </code>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'dashboard' && <Dashboard />}
        {activeTab === 'config' && <ConfigEditor />}
        {activeTab === 'models' && <OllamaModels />}
        {activeTab === 'logs' && <LogViewer />}
        {activeTab === 'tests' && <TestRunner />}
      </main>
    </div>
  );
}

export default App;
