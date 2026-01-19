"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { toast } from "sonner";
import {
  Webhook as WebhookIcon,
  Plus,
  Trash2,
  PlayCircle,
  Loader2,
  CheckCircle,
  XCircle,
  AlertTriangle,
  RefreshCw,
  Link as LinkIcon,
  Clock,
} from "lucide-react";
import {
  getWebhooks,
  createWebhook,
  deleteWebhook,
  testWebhook,
  type Webhook,
} from "@/lib/api";

const AVAILABLE_EVENTS = [
  { value: "content.created", label: "Content Created" },
  { value: "content.updated", label: "Content Updated" },
  { value: "content.deleted", label: "Content Deleted" },
  { value: "search.performed", label: "Search Performed" },
  { value: "review.completed", label: "Review Completed" },
  { value: "ingest.completed", label: "Ingest Completed" },
];

export default function WebhooksPage() {
  const [webhooks, setWebhooks] = useState<Webhook[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  // Create form state
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newUrl, setNewUrl] = useState("");
  const [newEvents, setNewEvents] = useState<string[]>([]);
  const [newSecret, setNewSecret] = useState("");
  const [creating, setCreating] = useState(false);

  // Testing state
  const [testingId, setTestingId] = useState<string | null>(null);

  const loadWebhooks = async () => {
    try {
      const data = await getWebhooks();
      setWebhooks(data);
      setError(false);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadWebhooks();
  }, []);

  const handleCreate = async () => {
    if (!newUrl.trim()) {
      toast.error("Please enter a webhook URL");
      return;
    }
    if (newEvents.length === 0) {
      toast.error("Please select at least one event");
      return;
    }

    setCreating(true);
    try {
      const webhook = await createWebhook({
        url: newUrl,
        events: newEvents,
        secret: newSecret || undefined,
      });
      setWebhooks([...webhooks, webhook]);
      setShowCreateForm(false);
      setNewUrl("");
      setNewEvents([]);
      setNewSecret("");
      toast.success("Webhook created successfully");
    } catch {
      toast.error("Failed to create webhook");
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteWebhook(id);
      setWebhooks(webhooks.filter((w) => w.id !== id));
      toast.success("Webhook deleted");
    } catch {
      toast.error("Failed to delete webhook");
    }
  };

  const handleTest = async (id: string) => {
    setTestingId(id);
    try {
      const result = await testWebhook(id);
      if (result.success) {
        toast.success("Webhook test successful");
      } else {
        toast.error(`Webhook test failed: ${result.message}`);
      }
    } catch {
      toast.error("Failed to test webhook");
    } finally {
      setTestingId(null);
    }
  };

  const toggleEvent = (event: string) => {
    if (newEvents.includes(event)) {
      setNewEvents(newEvents.filter((e) => e !== event));
    } else {
      setNewEvents([...newEvents, event]);
    }
  };

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center min-h-[50vh]">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4 text-muted-foreground" />
          <p className="text-muted-foreground">Loading webhooks...</p>
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
            <WebhookIcon className="h-6 w-6" />
            Webhooks
          </h1>
          <p className="text-muted-foreground">
            Configure webhooks to receive notifications about events
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={loadWebhooks} className="gap-2">
            <RefreshCw className="h-4 w-4" />
            Refresh
          </Button>
          <Button onClick={() => setShowCreateForm(true)} className="gap-2">
            <Plus className="h-4 w-4" />
            Add Webhook
          </Button>
        </div>
      </div>

      {/* Error State */}
      {error && (
        <Card>
          <CardContent className="p-8 text-center">
            <AlertTriangle className="h-12 w-12 mx-auto mb-4 text-yellow-500" />
            <p className="font-medium">Webhooks Not Available</p>
            <p className="text-sm text-muted-foreground mt-2">
              The webhooks API endpoint is not available yet.
              This feature may not be fully implemented on the backend.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Create Form */}
      {showCreateForm && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Create Webhook</CardTitle>
            <CardDescription>
              Configure a new webhook endpoint to receive event notifications
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="text-sm font-medium mb-2 block">Webhook URL</label>
              <div className="relative">
                <LinkIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="https://your-server.com/webhook"
                  value={newUrl}
                  onChange={(e) => setNewUrl(e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>

            <div>
              <label className="text-sm font-medium mb-2 block">Events</label>
              <div className="flex flex-wrap gap-2">
                {AVAILABLE_EVENTS.map((event) => (
                  <Button
                    key={event.value}
                    type="button"
                    variant={newEvents.includes(event.value) ? "default" : "outline"}
                    size="sm"
                    onClick={() => toggleEvent(event.value)}
                  >
                    {event.label}
                  </Button>
                ))}
              </div>
            </div>

            <div>
              <label className="text-sm font-medium mb-2 block">
                Secret (optional)
              </label>
              <Input
                type="password"
                placeholder="For HMAC signature verification"
                value={newSecret}
                onChange={(e) => setNewSecret(e.target.value)}
              />
              <p className="text-xs text-muted-foreground mt-1">
                Used to sign webhook payloads for verification
              </p>
            </div>

            <Separator />

            <div className="flex gap-2 justify-end">
              <Button
                variant="outline"
                onClick={() => {
                  setShowCreateForm(false);
                  setNewUrl("");
                  setNewEvents([]);
                  setNewSecret("");
                }}
              >
                Cancel
              </Button>
              <Button onClick={handleCreate} disabled={creating} className="gap-2">
                {creating && <Loader2 className="h-4 w-4 animate-spin" />}
                Create Webhook
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Webhooks List */}
      {!error && (
        <div className="space-y-4">
          {webhooks.length === 0 ? (
            <Card>
              <CardContent className="p-8 text-center">
                <WebhookIcon className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
                <p className="font-medium">No webhooks configured</p>
                <p className="text-sm text-muted-foreground mt-2">
                  Create a webhook to receive notifications about events in your knowledge base
                </p>
                <Button onClick={() => setShowCreateForm(true)} className="mt-4 gap-2">
                  <Plus className="h-4 w-4" />
                  Add Your First Webhook
                </Button>
              </CardContent>
            </Card>
          ) : (
            webhooks.map((webhook) => (
              <Card key={webhook.id}>
                <CardContent className="p-4">
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-2">
                        <p className="font-mono text-sm truncate">{webhook.url}</p>
                        <Badge variant={webhook.active ? "default" : "secondary"}>
                          {webhook.active ? "Active" : "Inactive"}
                        </Badge>
                        {webhook.failure_count > 0 && (
                          <Badge variant="destructive">
                            {webhook.failure_count} failures
                          </Badge>
                        )}
                      </div>
                      <div className="flex flex-wrap gap-1 mb-2">
                        {webhook.events.map((event) => (
                          <Badge key={event} variant="outline" className="text-xs">
                            {event}
                          </Badge>
                        ))}
                      </div>
                      <div className="flex items-center gap-4 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          Created {new Date(webhook.created_at).toLocaleDateString()}
                        </span>
                        {webhook.last_triggered && (
                          <span>
                            Last triggered {new Date(webhook.last_triggered).toLocaleDateString()}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="flex gap-2 ml-4">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleTest(webhook.id)}
                        disabled={testingId === webhook.id}
                        className="gap-1"
                      >
                        {testingId === webhook.id ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <PlayCircle className="h-4 w-4" />
                        )}
                        Test
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleDelete(webhook.id)}
                        className="text-red-500 hover:text-red-600"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))
          )}
        </div>
      )}

      {/* Info Card */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">About Webhooks</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="p-4 rounded-lg border">
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle className="h-5 w-5 text-green-500" />
                <span className="font-medium">Payload Signing</span>
              </div>
              <p className="text-sm text-muted-foreground">
                Webhooks are signed with HMAC-SHA256 using your secret for verification
              </p>
            </div>
            <div className="p-4 rounded-lg border">
              <div className="flex items-center gap-2 mb-2">
                <RefreshCw className="h-5 w-5 text-blue-500" />
                <span className="font-medium">Automatic Retry</span>
              </div>
              <p className="text-sm text-muted-foreground">
                Failed deliveries are automatically retried with exponential backoff
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
