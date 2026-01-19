"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { toast } from "sonner";
import {
  Settings as SettingsIcon,
  Database,
  Brain,
  Search,
  RefreshCw,
  CheckCircle,
  XCircle,
  Loader2,
  Server,
  HardDrive,
  Cpu,
  Clock,
} from "lucide-react";
import { getHealth, getStats, type HealthResponse, type StatsResponse } from "@/lib/api";
import { cn } from "@/lib/utils";

export default function SettingsPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = async () => {
    try {
      const [healthData, statsData] = await Promise.all([
        getHealth(),
        getStats(),
      ]);
      setHealth(healthData);
      setStats(statsData);
    } catch (error) {
      console.error("Failed to load settings data:", error);
      toast.error("Failed to load system information");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleRefresh = async () => {
    setRefreshing(true);
    await loadData();
    toast.success("System information refreshed");
  };

  if (loading) {
    return (
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <div className="h-8 w-48 bg-muted rounded animate-pulse" />
            <div className="h-4 w-64 bg-muted rounded animate-pulse mt-2" />
          </div>
        </div>
        <div className="grid gap-6">
          {[...Array(3)].map((_, i) => (
            <Card key={i}>
              <CardContent className="p-6">
                <div className="h-4 w-32 bg-muted rounded animate-pulse" />
                <div className="h-24 w-full bg-muted rounded animate-pulse mt-4" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <SettingsIcon className="h-6 w-6" />
            Settings
          </h1>
          <p className="text-muted-foreground">
            System configuration and status
          </p>
        </div>
        <Button
          variant="outline"
          onClick={handleRefresh}
          disabled={refreshing}
          className="gap-2"
        >
          {refreshing ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="h-4 w-4" />
          )}
          Refresh
        </Button>
      </div>

      {/* System Status */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Server className="h-5 w-5" />
            System Status
          </CardTitle>
          <CardDescription>
            Current health of all system components
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-2">
            {health?.services?.map((service) => (
              <div
                key={service.name}
                className="flex items-center justify-between p-4 rounded-lg border bg-card"
              >
                <div className="flex items-center gap-3">
                  {service.status === "healthy" ? (
                    <CheckCircle className="h-5 w-5 text-green-500" />
                  ) : (
                    <XCircle className="h-5 w-5 text-red-500" />
                  )}
                  <div>
                    <p className="font-medium">{service.name}</p>
                    <p className="text-sm text-muted-foreground">
                      {service.status === "healthy" ? "Operational" : "Degraded"}
                    </p>
                  </div>
                </div>
                <Badge
                  variant={service.status === "healthy" ? "default" : "destructive"}
                >
                  {service.status}
                </Badge>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Database Statistics */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Database className="h-5 w-5" />
            Database Statistics
          </CardTitle>
          <CardDescription>
            Content and storage metrics
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-4">
            <div className="p-4 rounded-lg bg-muted/50 text-center">
              <p className="text-3xl font-bold">{stats?.total_content || 0}</p>
              <p className="text-sm text-muted-foreground">Total Content</p>
            </div>
            <div className="p-4 rounded-lg bg-muted/50 text-center">
              <p className="text-3xl font-bold">{stats?.total_chunks || 0}</p>
              <p className="text-sm text-muted-foreground">Indexed Chunks</p>
            </div>
            <div className="p-4 rounded-lg bg-muted/50 text-center">
              <p className="text-3xl font-bold">{stats?.review_active || 0}</p>
              <p className="text-sm text-muted-foreground">In Review Queue</p>
            </div>
            <div className="p-4 rounded-lg bg-muted/50 text-center">
              <p className="text-3xl font-bold text-orange-500">
                {stats?.review_due || 0}
              </p>
              <p className="text-sm text-muted-foreground">Reviews Due</p>
            </div>
          </div>

          <Separator className="my-6" />

          <div>
            <h4 className="font-medium mb-3">Content by Type</h4>
            <div className="grid gap-2 md:grid-cols-3">
              {stats?.content_by_type &&
                Object.entries(stats.content_by_type)
                  .filter(([, count]) => count > 0)
                  .map(([type, count]) => (
                    <div
                      key={type}
                      className="flex items-center justify-between p-3 rounded-lg border"
                    >
                      <span className="capitalize">{type}</span>
                      <Badge variant="secondary">{count}</Badge>
                    </div>
                  ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Service Details */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Cpu className="h-5 w-5" />
            Service Details
          </CardTitle>
          <CardDescription>
            Detailed information about each service
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {health?.services?.map((service) => (
              <div key={service.name} className="border rounded-lg p-4">
                <div className="flex items-center gap-2 mb-3">
                  {service.name === "PostgreSQL" ? (
                    <Database className="h-4 w-4" />
                  ) : service.name === "Ollama" ? (
                    <Brain className="h-4 w-4" />
                  ) : (
                    <Server className="h-4 w-4" />
                  )}
                  <h4 className="font-medium">{service.name}</h4>
                </div>
                {service.details && (
                  <div className="grid gap-2 text-sm">
                    {Object.entries(service.details).map(([key, value]) => (
                      <div
                        key={key}
                        className="flex items-center justify-between py-1 border-b border-border/50 last:border-0"
                      >
                        <span className="text-muted-foreground capitalize">
                          {key.replace(/_/g, " ")}
                        </span>
                        <span className="font-mono">
                          {Array.isArray(value)
                            ? value.length > 0
                              ? value.join(", ")
                              : "None"
                            : String(value)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Configuration Info */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <HardDrive className="h-5 w-5" />
            Configuration
          </CardTitle>
          <CardDescription>
            System configuration (read-only)
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3">
            <div className="flex items-center justify-between p-3 rounded-lg border">
              <div className="flex items-center gap-2">
                <Search className="h-4 w-4 text-muted-foreground" />
                <span>Search Mode</span>
              </div>
              <Badge>Hybrid (BM25 + Vector)</Badge>
            </div>
            <div className="flex items-center justify-between p-3 rounded-lg border">
              <div className="flex items-center gap-2">
                <Brain className="h-4 w-4 text-muted-foreground" />
                <span>Embedding Model</span>
              </div>
              <Badge variant="secondary">nomic-embed-text</Badge>
            </div>
            <div className="flex items-center justify-between p-3 rounded-lg border">
              <div className="flex items-center gap-2">
                <Clock className="h-4 w-4 text-muted-foreground" />
                <span>Spaced Repetition</span>
              </div>
              <Badge variant="secondary">FSRS Algorithm</Badge>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
