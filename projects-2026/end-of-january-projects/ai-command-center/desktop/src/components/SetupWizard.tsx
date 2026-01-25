import { useEffect, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { CheckCircle, XCircle, Loader2, ExternalLink, Rocket } from 'lucide-react';
import clsx from 'clsx';

interface DependencyCheck {
  name: string;
  description: string;
  status: 'pending' | 'checking' | 'ok' | 'missing';
  required: boolean;
  fixUrl?: string;
}

interface SetupWizardProps {
  onComplete: () => void;
}

export function SetupWizard({ onComplete }: SetupWizardProps) {
  const [checks, setChecks] = useState<DependencyCheck[]>([
    {
      name: 'Ollama',
      description: 'Local LLM runtime',
      status: 'pending',
      required: true,
      fixUrl: 'https://ollama.com/download',
    },
    {
      name: 'Redis',
      description: 'Caching layer',
      status: 'pending',
      required: true,
      fixUrl: 'https://redis.io/docs/getting-started/installation/install-redis-on-mac-os/',
    },
    {
      name: 'Langfuse',
      description: 'Observability (Docker)',
      status: 'pending',
      required: false,
      fixUrl: 'https://langfuse.com/docs/deployment/self-host',
    },
    {
      name: 'Config Files',
      description: 'AI Command Center config',
      status: 'pending',
      required: true,
    },
  ]);
  const [isChecking, setIsChecking] = useState(false);

  const updateCheck = (name: string, status: DependencyCheck['status']) => {
    setChecks((prev) =>
      prev.map((c) => (c.name === name ? { ...c, status } : c))
    );
  };

  const runChecks = async () => {
    setIsChecking(true);

    // Reset all to pending
    setChecks((prev) => prev.map((c) => ({ ...c, status: 'pending' })));

    // Check Ollama
    updateCheck('Ollama', 'checking');
    try {
      const result = await invoke<{ healthy: boolean }>('check_ollama_health');
      updateCheck('Ollama', result.healthy ? 'ok' : 'missing');
    } catch {
      updateCheck('Ollama', 'missing');
    }

    // Check Redis
    updateCheck('Redis', 'checking');
    try {
      const result = await invoke<{ healthy: boolean }>('check_redis_health');
      updateCheck('Redis', result.healthy ? 'ok' : 'missing');
    } catch {
      updateCheck('Redis', 'missing');
    }

    // Check Langfuse (optional)
    updateCheck('Langfuse', 'checking');
    try {
      const result = await invoke<{ healthy: boolean }>('check_langfuse_health');
      updateCheck('Langfuse', result.healthy ? 'ok' : 'missing');
    } catch {
      updateCheck('Langfuse', 'missing');
    }

    // Check config files
    updateCheck('Config Files', 'checking');
    try {
      await invoke('read_config');
      await invoke('read_policy');
      updateCheck('Config Files', 'ok');
    } catch {
      updateCheck('Config Files', 'missing');
    }

    setIsChecking(false);
  };

  useEffect(() => {
    runChecks();
  }, []);

  const requiredPassing = checks
    .filter((c) => c.required)
    .every((c) => c.status === 'ok');

  const allChecksComplete = checks.every(
    (c) => c.status === 'ok' || c.status === 'missing'
  );

  return (
    <div className="min-h-screen bg-gray-900 flex items-center justify-center p-8">
      <div className="max-w-lg w-full bg-gray-800 rounded-xl p-8 shadow-2xl">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-600 rounded-2xl mb-4">
            <Rocket className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-white">AI Command Center</h1>
          <p className="text-gray-400 mt-2">
            Let's verify your system is ready
          </p>
        </div>

        <div className="space-y-3 mb-8">
          {checks.map((check) => (
            <div
              key={check.name}
              className="flex items-center justify-between p-4 bg-gray-700 rounded-lg"
            >
              <div className="flex items-center gap-4">
                {check.status === 'checking' && (
                  <Loader2 className="w-5 h-5 text-blue-400 animate-spin" />
                )}
                {check.status === 'ok' && (
                  <CheckCircle className="w-5 h-5 text-green-400" />
                )}
                {check.status === 'missing' && (
                  <XCircle
                    className={clsx(
                      'w-5 h-5',
                      check.required ? 'text-red-400' : 'text-yellow-400'
                    )}
                  />
                )}
                {check.status === 'pending' && (
                  <div className="w-5 h-5 rounded-full border-2 border-gray-500" />
                )}
                <div>
                  <p className="font-medium text-white">
                    {check.name}
                    {!check.required && (
                      <span className="ml-2 text-xs text-gray-400">(optional)</span>
                    )}
                  </p>
                  <p className="text-sm text-gray-400">{check.description}</p>
                </div>
              </div>
              {check.status === 'missing' && check.fixUrl && (
                <a
                  href={check.fixUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="p-2 text-blue-400 hover:bg-blue-900/30 rounded-lg"
                  title="Installation guide"
                >
                  <ExternalLink className="w-4 h-4" />
                </a>
              )}
            </div>
          ))}
        </div>

        <div className="space-y-4">
          {allChecksComplete && !requiredPassing && (
            <div className="bg-yellow-900/30 border border-yellow-700 text-yellow-400 p-4 rounded-lg text-sm">
              <p className="font-medium mb-1">Missing required dependencies</p>
              <p>
                Please install Ollama and Redis, then click "Re-check" to continue.
              </p>
            </div>
          )}

          <div className="flex gap-3">
            <button
              onClick={runChecks}
              disabled={isChecking}
              className="flex-1 px-4 py-3 bg-gray-700 hover:bg-gray-600 rounded-lg font-medium text-white disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {isChecking && <Loader2 className="w-4 h-4 animate-spin" />}
              Re-check
            </button>
            <button
              onClick={onComplete}
              disabled={!requiredPassing || isChecking}
              className={clsx(
                'flex-1 px-4 py-3 rounded-lg font-medium flex items-center justify-center gap-2',
                requiredPassing && !isChecking
                  ? 'bg-green-600 hover:bg-green-700 text-white'
                  : 'bg-gray-700 text-gray-500 cursor-not-allowed'
              )}
            >
              <Rocket className="w-4 h-4" />
              Get Started
            </button>
          </div>

          <button
            onClick={onComplete}
            className="w-full text-sm text-gray-500 hover:text-gray-400"
          >
            Skip setup and continue anyway
          </button>
        </div>
      </div>
    </div>
  );
}
