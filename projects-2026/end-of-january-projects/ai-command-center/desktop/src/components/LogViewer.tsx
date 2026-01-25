import { useEffect, useState, useRef } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { RefreshCw, Loader2 } from 'lucide-react';
import clsx from 'clsx';

type LogService = 'router' | 'litellm';

export function LogViewer() {
  const [selectedLog, setSelectedLog] = useState<LogService>('router');
  const [logs, setLogs] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const logsEndRef = useRef<HTMLDivElement>(null);

  const loadLogs = async () => {
    setLoading(true);
    try {
      const result = await invoke<string[]>('read_log_tail', {
        service: selectedLog,
        lines: 200,
      });
      setLogs(result);
    } catch (err) {
      setLogs([`Error loading logs: ${err}`]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLogs();
    // Poll for new logs every 5 seconds (reduced from 2s for performance)
    const interval = setInterval(loadLogs, 5000);
    return () => clearInterval(interval);
  }, [selectedLog]);

  useEffect(() => {
    if (autoScroll) {
      logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);

  const getLineClass = (line: string) => {
    if (line.includes('ERROR') || line.includes('error')) return 'text-red-400';
    if (line.includes('WARNING') || line.includes('warn')) return 'text-yellow-400';
    if (line.includes('INFO')) return 'text-gray-300';
    if (line.includes('DEBUG')) return 'text-gray-500';
    return 'text-gray-400';
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Service Logs</h1>
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 text-sm text-gray-400">
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
              className="w-4 h-4 rounded"
            />
            Auto-scroll
          </label>
        </div>
      </div>

      {/* Log Source Selector */}
      <div className="flex gap-2">
        <button
          onClick={() => setSelectedLog('router')}
          className={clsx(
            'px-4 py-2 rounded-lg font-medium',
            selectedLog === 'router'
              ? 'bg-blue-600 text-white'
              : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
          )}
        >
          Smart Router
        </button>
        <button
          onClick={() => setSelectedLog('litellm')}
          className={clsx(
            'px-4 py-2 rounded-lg font-medium',
            selectedLog === 'litellm'
              ? 'bg-blue-600 text-white'
              : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
          )}
        >
          LiteLLM
        </button>
        <button
          onClick={loadLogs}
          disabled={loading}
          className="ml-auto p-2 text-gray-400 hover:text-white hover:bg-gray-700 rounded-lg disabled:opacity-50"
        >
          <RefreshCw className={clsx("w-4 h-4", loading && "animate-spin")} />
        </button>
      </div>

      {/* Log Viewer */}
      <div className="bg-gray-900 rounded-lg p-4 h-[600px] overflow-auto font-mono text-sm">
        {loading && logs.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <Loader2 className="w-6 h-6 text-gray-400 animate-spin" />
          </div>
        ) : logs.length === 0 ? (
          <p className="text-gray-500">No logs available</p>
        ) : (
          <>
            {logs.map((line, index) => (
              <div
                key={index}
                className={clsx('py-0.5 whitespace-pre-wrap break-all', getLineClass(line))}
              >
                {line}
              </div>
            ))}
            <div ref={logsEndRef} />
          </>
        )}
      </div>

      {/* Log Legend */}
      <div className="flex gap-6 text-sm">
        <span className="text-red-400">ERROR</span>
        <span className="text-yellow-400">WARNING</span>
        <span className="text-gray-300">INFO</span>
        <span className="text-gray-500">DEBUG</span>
      </div>
    </div>
  );
}
