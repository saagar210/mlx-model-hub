'use client';

import { useState, useEffect } from 'react';
import { getHealth } from '@/lib/api';
import { Cpu, Zap, AlertCircle } from 'lucide-react';
import type { HealthResponse } from '@/types/api';

export function Header() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const data = await getHealth();
        setHealth(data);
        setError(false);
      } catch {
        setError(true);
      }
    };

    fetchHealth();
    const interval = setInterval(fetchHealth, 10000);
    return () => clearInterval(interval);
  }, []);

  const loadedModels = health
    ? Object.values(health.models).filter((m) => m.loaded).length
    : 0;

  return (
    <header className="border-b border-border bg-card/50 backdrop-blur-sm">
      <div className="container mx-auto px-4 h-16 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-lg bg-gradient-to-br from-primary to-accent flex items-center justify-center">
            <Zap className="h-5 w-5 text-white" />
          </div>
          <div>
            <h1 className="font-bold text-lg">Unified MLX AI</h1>
            <p className="text-xs text-muted-foreground">
              Local AI powered by Apple Silicon
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {error ? (
            <div className="flex items-center gap-2 text-destructive text-sm">
              <AlertCircle className="h-4 w-4" />
              API Offline
            </div>
          ) : (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Cpu className="h-4 w-4" />
              <span>
                {loadedModels} model{loadedModels !== 1 ? 's' : ''} loaded
              </span>
              <div
                className={`h-2 w-2 rounded-full ${
                  loadedModels > 0 ? 'bg-green-500' : 'bg-yellow-500'
                }`}
              />
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
