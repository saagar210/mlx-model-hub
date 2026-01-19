"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { toast } from "sonner";
import {
  Puzzle,
  Loader2,
  AlertTriangle,
  RefreshCw,
  Settings2,
  ExternalLink,
  CheckCircle,
  XCircle,
  Book,
  Bookmark,
  FileText,
  Cloud,
} from "lucide-react";

// Plugin types
interface Plugin {
  id: string;
  name: string;
  description: string;
  version: string;
  author: string;
  enabled: boolean;
  icon: string;
  category: "import" | "export" | "automation" | "integration";
  configurable: boolean;
  status: "active" | "inactive" | "error";
  lastSync?: string;
  error?: string;
}

// Mock plugins data - replace with API call when backend is ready
const MOCK_PLUGINS: Plugin[] = [
  {
    id: "notion",
    name: "Notion",
    description: "Import pages and databases from Notion workspaces",
    version: "1.0.0",
    author: "KAS Team",
    enabled: false,
    icon: "notion",
    category: "import",
    configurable: true,
    status: "inactive",
  },
  {
    id: "readwise",
    name: "Readwise",
    description: "Sync highlights and annotations from Readwise",
    version: "1.0.0",
    author: "KAS Team",
    enabled: false,
    icon: "readwise",
    category: "import",
    configurable: true,
    status: "inactive",
  },
  {
    id: "pocket",
    name: "Pocket",
    description: "Import saved articles from Pocket",
    version: "1.0.0",
    author: "KAS Team",
    enabled: false,
    icon: "pocket",
    category: "import",
    configurable: true,
    status: "inactive",
  },
  {
    id: "obsidian-sync",
    name: "Obsidian Sync",
    description: "Two-way sync with Obsidian vault (tags, links, metadata)",
    version: "1.0.0",
    author: "KAS Team",
    enabled: true,
    icon: "obsidian",
    category: "integration",
    configurable: true,
    status: "active",
    lastSync: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
  },
];

const getCategoryIcon = (category: Plugin["category"]) => {
  switch (category) {
    case "import":
      return <FileText className="h-4 w-4" />;
    case "export":
      return <ExternalLink className="h-4 w-4" />;
    case "automation":
      return <RefreshCw className="h-4 w-4" />;
    case "integration":
      return <Cloud className="h-4 w-4" />;
  }
};

const getPluginIcon = (icon: string) => {
  // Return appropriate icon based on plugin type
  switch (icon) {
    case "notion":
      return <Book className="h-8 w-8" />;
    case "readwise":
      return <Bookmark className="h-8 w-8" />;
    case "pocket":
      return <Bookmark className="h-8 w-8" />;
    case "obsidian":
      return <FileText className="h-8 w-8" />;
    default:
      return <Puzzle className="h-8 w-8" />;
  }
};

export default function PluginsPage() {
  const [plugins, setPlugins] = useState<Plugin[]>([]);
  const [loading, setLoading] = useState(true);
  const [apiAvailable, setApiAvailable] = useState(false);
  const [togglingId, setTogglingId] = useState<string | null>(null);

  const loadPlugins = async () => {
    setLoading(true);
    try {
      // Try to fetch from API first
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/plugins`
      );
      if (response.ok) {
        const data = await response.json();
        setPlugins(data);
        setApiAvailable(true);
      } else {
        // Fall back to mock data
        setPlugins(MOCK_PLUGINS);
        setApiAvailable(false);
      }
    } catch {
      // Fall back to mock data
      setPlugins(MOCK_PLUGINS);
      setApiAvailable(false);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPlugins();
  }, []);

  const handleToggle = async (plugin: Plugin) => {
    setTogglingId(plugin.id);

    // Simulate API call
    await new Promise((resolve) => setTimeout(resolve, 500));

    setPlugins(
      plugins.map((p) =>
        p.id === plugin.id
          ? {
              ...p,
              enabled: !p.enabled,
              status: !p.enabled ? "active" : "inactive",
            }
          : p
      )
    );

    toast.success(
      plugin.enabled
        ? `${plugin.name} disabled`
        : `${plugin.name} enabled`
    );

    setTogglingId(null);
  };

  const handleConfigure = (plugin: Plugin) => {
    toast.info(`Configuration for ${plugin.name} coming soon`);
  };

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center min-h-[50vh]">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4 text-muted-foreground" />
          <p className="text-muted-foreground">Loading plugins...</p>
        </div>
      </div>
    );
  }

  const enabledPlugins = plugins.filter((p) => p.enabled);
  const availablePlugins = plugins.filter((p) => !p.enabled);

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Puzzle className="h-6 w-6" />
            Plugins
          </h1>
          <p className="text-muted-foreground">
            Extend KAS with integrations and automations
          </p>
        </div>
        <Button variant="outline" onClick={loadPlugins} className="gap-2">
          <RefreshCw className="h-4 w-4" />
          Refresh
        </Button>
      </div>

      {/* API Status Banner */}
      {!apiAvailable && (
        <Card className="border-yellow-500/50 bg-yellow-500/5">
          <CardContent className="p-4 flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 text-yellow-500 mt-0.5" />
            <div>
              <p className="font-medium text-yellow-500">Preview Mode</p>
              <p className="text-sm text-muted-foreground">
                The plugins API is not available. Showing preview data.
                Plugin changes won&apos;t persist until the backend is implemented.
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Enabled Plugins */}
      {enabledPlugins.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold">Active Plugins</h2>
          <div className="grid gap-4 md:grid-cols-2">
            {enabledPlugins.map((plugin) => (
              <Card key={plugin.id}>
                <CardContent className="p-4">
                  <div className="flex items-start gap-4">
                    <div className="p-2 rounded-lg bg-primary/10 text-primary">
                      {getPluginIcon(plugin.icon)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between mb-1">
                        <h3 className="font-semibold">{plugin.name}</h3>
                        <div className="flex items-center gap-2">
                          {plugin.status === "active" ? (
                            <Badge variant="default" className="gap-1">
                              <CheckCircle className="h-3 w-3" />
                              Active
                            </Badge>
                          ) : plugin.status === "error" ? (
                            <Badge variant="destructive" className="gap-1">
                              <XCircle className="h-3 w-3" />
                              Error
                            </Badge>
                          ) : null}
                          <Switch
                            checked={plugin.enabled}
                            onCheckedChange={() => handleToggle(plugin)}
                            disabled={togglingId === plugin.id}
                          />
                        </div>
                      </div>
                      <p className="text-sm text-muted-foreground mb-2">
                        {plugin.description}
                      </p>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                          {getCategoryIcon(plugin.category)}
                          <span className="capitalize">{plugin.category}</span>
                          <span>•</span>
                          <span>v{plugin.version}</span>
                        </div>
                        {plugin.configurable && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleConfigure(plugin)}
                            className="gap-1 h-7"
                          >
                            <Settings2 className="h-3.5 w-3.5" />
                            Configure
                          </Button>
                        )}
                      </div>
                      {plugin.lastSync && (
                        <p className="text-xs text-muted-foreground mt-2">
                          Last synced: {new Date(plugin.lastSync).toLocaleString()}
                        </p>
                      )}
                      {plugin.error && (
                        <p className="text-xs text-red-500 mt-2">
                          Error: {plugin.error}
                        </p>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Available Plugins */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold">Available Plugins</h2>
        {availablePlugins.length === 0 ? (
          <Card>
            <CardContent className="p-8 text-center">
              <CheckCircle className="h-12 w-12 mx-auto mb-4 text-green-500 opacity-50" />
              <p className="font-medium">All plugins enabled!</p>
              <p className="text-sm text-muted-foreground mt-2">
                You&apos;ve enabled all available plugins
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {availablePlugins.map((plugin) => (
              <Card key={plugin.id} className="opacity-75 hover:opacity-100 transition-opacity">
                <CardContent className="p-4">
                  <div className="flex items-start gap-4">
                    <div className="p-2 rounded-lg bg-muted text-muted-foreground">
                      {getPluginIcon(plugin.icon)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between mb-1">
                        <h3 className="font-semibold">{plugin.name}</h3>
                        <Switch
                          checked={plugin.enabled}
                          onCheckedChange={() => handleToggle(plugin)}
                          disabled={togglingId === plugin.id}
                        />
                      </div>
                      <p className="text-sm text-muted-foreground mb-2">
                        {plugin.description}
                      </p>
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        {getCategoryIcon(plugin.category)}
                        <span className="capitalize">{plugin.category}</span>
                        <span>•</span>
                        <span>v{plugin.version}</span>
                        <span>•</span>
                        <span>by {plugin.author}</span>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      <Separator />

      {/* Info Card */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">About Plugins</CardTitle>
          <CardDescription>
            Plugins extend KAS functionality with third-party integrations
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="p-4 rounded-lg border">
              <div className="flex items-center gap-2 mb-2">
                <FileText className="h-5 w-5 text-blue-500" />
                <span className="font-medium">Import Plugins</span>
              </div>
              <p className="text-sm text-muted-foreground">
                Bring content from external services like Notion, Readwise, and Pocket
              </p>
            </div>
            <div className="p-4 rounded-lg border">
              <div className="flex items-center gap-2 mb-2">
                <Cloud className="h-5 w-5 text-purple-500" />
                <span className="font-medium">Integration Plugins</span>
              </div>
              <p className="text-sm text-muted-foreground">
                Two-way sync with tools like Obsidian for seamless workflows
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
