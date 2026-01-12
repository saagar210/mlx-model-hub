"use client";

import { useState, useEffect, useCallback } from "react";
import { AlertCircle, RefreshCw, Wifi, WifiOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { checkConnection } from "@/lib/api";
import { cn } from "@/lib/utils";

interface ConnectionStatusProps {
  className?: string;
  showRetry?: boolean;
}

export function ConnectionStatus({ className, showRetry = true }: ConnectionStatusProps) {
  const [isConnected, setIsConnected] = useState<boolean | null>(null);
  const [isChecking, setIsChecking] = useState(false);

  const checkStatus = useCallback(async () => {
    setIsChecking(true);
    try {
      const connected = await checkConnection();
      setIsConnected(connected);
    } catch {
      setIsConnected(false);
    } finally {
      setIsChecking(false);
    }
  }, []);

  useEffect(() => {
    checkStatus();
    // Check connection every 30 seconds
    const interval = setInterval(checkStatus, 30000);
    return () => clearInterval(interval);
  }, [checkStatus]);

  if (isConnected === null) {
    return (
      <div className={cn("flex items-center gap-2 text-sm text-muted-foreground", className)}>
        <RefreshCw className="h-4 w-4 animate-spin" />
        <span>Checking connection...</span>
      </div>
    );
  }

  if (isConnected) {
    return (
      <div className={cn("flex items-center gap-2 text-sm text-green-600 dark:text-green-400", className)}>
        <Wifi className="h-4 w-4" />
        <span>Connected</span>
      </div>
    );
  }

  return (
    <div className={cn("flex items-center gap-2", className)}>
      <div className="flex items-center gap-2 text-sm text-red-600 dark:text-red-400">
        <WifiOff className="h-4 w-4" />
        <span>Disconnected</span>
      </div>
      {showRetry && (
        <Button
          variant="ghost"
          size="sm"
          onClick={checkStatus}
          disabled={isChecking}
          className="h-7 px-2"
        >
          <RefreshCw className={cn("h-3 w-3", isChecking && "animate-spin")} />
        </Button>
      )}
    </div>
  );
}

/**
 * Banner that shows when the API is disconnected
 */
export function ConnectionBanner() {
  const [isConnected, setIsConnected] = useState<boolean | null>(null);
  const [isChecking, setIsChecking] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  const checkStatus = useCallback(async () => {
    setIsChecking(true);
    try {
      const connected = await checkConnection();
      setIsConnected(connected);
      if (connected) {
        setDismissed(false); // Reset dismiss when reconnected
      }
    } catch {
      setIsConnected(false);
    } finally {
      setIsChecking(false);
    }
  }, []);

  useEffect(() => {
    checkStatus();
    const interval = setInterval(checkStatus, 30000);
    return () => clearInterval(interval);
  }, [checkStatus]);

  // Don't show if connected, still checking, or dismissed
  if (isConnected === null || isConnected || dismissed) {
    return null;
  }

  return (
    <div className="bg-red-500/10 border-b border-red-500/20 px-4 py-2">
      <div className="flex items-center justify-between max-w-7xl mx-auto">
        <div className="flex items-center gap-3">
          <AlertCircle className="h-4 w-4 text-red-500" />
          <span className="text-sm text-red-600 dark:text-red-400">
            Unable to connect to the API server. Make sure the backend is running at{" "}
            <code className="bg-red-500/10 px-1 py-0.5 rounded text-xs">
              {process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}
            </code>
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={checkStatus}
            disabled={isChecking}
            className="text-red-600 hover:text-red-700 hover:bg-red-500/10"
          >
            <RefreshCw className={cn("h-4 w-4 mr-1", isChecking && "animate-spin")} />
            Retry
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setDismissed(true)}
            className="text-red-600 hover:text-red-700 hover:bg-red-500/10"
          >
            Dismiss
          </Button>
        </div>
      </div>
    </div>
  );
}
