import { ReactNode } from 'react';
import { ExternalLink, Play, Square } from 'lucide-react';
import clsx from 'clsx';
import type { HealthStatus } from '../lib/types';

interface ServiceCardProps {
  name: string;
  icon: ReactNode;
  status: HealthStatus;
  port: number;
  external?: boolean;
  url?: string;
  onStart?: () => void;
  onStop?: () => void;
}

export function ServiceCard({
  name,
  icon,
  status,
  port,
  external,
  url,
  onStart,
  onStop,
}: ServiceCardProps) {
  return (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className={clsx(
            'p-2 rounded-lg',
            status.healthy ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'
          )}>
            {icon}
          </div>
          <div>
            <h3 className="font-semibold text-white">{name}</h3>
            <p className="text-sm text-gray-400">Port {port}</p>
          </div>
        </div>
        <div className={clsx(
          'w-3 h-3 rounded-full',
          status.healthy ? 'bg-green-500' : 'bg-red-500'
        )} />
      </div>

      <div className="text-sm text-gray-400 mb-3">
        <p>{status.message}</p>
        {status.latency_ms && (
          <p className="text-xs mt-1">{status.latency_ms}ms</p>
        )}
      </div>

      <div className="flex gap-2">
        {!external && (
          <>
            <button
              onClick={onStart}
              disabled={status.healthy}
              className={clsx(
                'flex-1 flex items-center justify-center gap-1 px-3 py-1.5 rounded text-sm font-medium',
                status.healthy
                  ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
                  : 'bg-green-600 hover:bg-green-700 text-white'
              )}
            >
              <Play className="w-4 h-4" />
              Start
            </button>
            <button
              onClick={onStop}
              disabled={!status.healthy}
              className={clsx(
                'flex-1 flex items-center justify-center gap-1 px-3 py-1.5 rounded text-sm font-medium',
                !status.healthy
                  ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
                  : 'bg-red-600 hover:bg-red-700 text-white'
              )}
            >
              <Square className="w-4 h-4" />
              Stop
            </button>
          </>
        )}
        {url && (
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex-1 flex items-center justify-center gap-1 px-3 py-1.5 rounded text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white"
          >
            <ExternalLink className="w-4 h-4" />
            Open
          </a>
        )}
        {external && !url && (
          <div className="flex-1 flex items-center justify-center px-3 py-1.5 rounded text-sm text-gray-500 bg-gray-700/50">
            External Service
          </div>
        )}
      </div>
    </div>
  );
}
