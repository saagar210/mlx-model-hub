"use client";

import * as React from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Link2,
  Youtube,
  FileText,
  Loader2,
  CheckCircle2,
  XCircle,
  Upload,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { useMutation } from "@tanstack/react-query";
import { ingestURL, ingestYouTube, ingestText } from "@/lib/api";
import { cn, formatBytes, formatDuration } from "@/lib/utils";
import type { IngestResponse } from "@/types/api";

type IngestType = "url" | "youtube" | "text";

export default function IngestPage() {
  const [activeType, setActiveType] = React.useState<IngestType>("url");
  const [results, setResults] = React.useState<IngestResult[]>([]);

  const addResult = (result: IngestResult) => {
    setResults((prev) => [result, ...prev].slice(0, 10)); // Keep last 10
  };

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container flex h-14 items-center">
          <Link
            href="/"
            className="flex items-center gap-2 text-muted-foreground hover:text-primary transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
            Back
          </Link>
          <div className="flex items-center gap-2 ml-4">
            <Upload className="h-6 w-6 text-primary" />
            <span className="font-semibold text-lg">Ingest Content</span>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 container py-8">
        <div className="max-w-2xl mx-auto">
          {/* Type selector */}
          <div className="flex gap-2 mb-6">
            <TypeButton
              type="url"
              icon={<Link2 className="h-4 w-4" />}
              label="URL"
              active={activeType === "url"}
              onClick={() => setActiveType("url")}
            />
            <TypeButton
              type="youtube"
              icon={<Youtube className="h-4 w-4" />}
              label="YouTube"
              active={activeType === "youtube"}
              onClick={() => setActiveType("youtube")}
            />
            <TypeButton
              type="text"
              icon={<FileText className="h-4 w-4" />}
              label="Text"
              active={activeType === "text"}
              onClick={() => setActiveType("text")}
            />
          </div>

          {/* Ingest forms */}
          {activeType === "url" && <URLIngestForm onResult={addResult} />}
          {activeType === "youtube" && <YouTubeIngestForm onResult={addResult} />}
          {activeType === "text" && <TextIngestForm onResult={addResult} />}

          {/* Results */}
          {results.length > 0 && (
            <div className="mt-8">
              <h3 className="text-sm font-medium mb-3 text-muted-foreground">
                Recent Ingestions
              </h3>
              <div className="space-y-2">
                {results.map((result, i) => (
                  <ResultCard key={i} result={result} />
                ))}
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

interface IngestResult {
  type: IngestType;
  input: string;
  response?: IngestResponse;
  error?: string;
  timestamp: Date;
}

interface TypeButtonProps {
  type: IngestType;
  icon: React.ReactNode;
  label: string;
  active: boolean;
  onClick: () => void;
}

function TypeButton({ icon, label, active, onClick }: TypeButtonProps) {
  return (
    <Button
      variant={active ? "default" : "outline"}
      onClick={onClick}
      className="flex-1"
    >
      {icon}
      <span className="ml-2">{label}</span>
    </Button>
  );
}

interface FormProps {
  onResult: (result: IngestResult) => void;
}

function URLIngestForm({ onResult }: FormProps) {
  const [url, setUrl] = React.useState("");

  const mutation = useMutation({
    mutationFn: (url: string) => ingestURL(url),
    onSuccess: (response) => {
      onResult({
        type: "url",
        input: url,
        response,
        timestamp: new Date(),
      });
      setUrl("");
    },
    onError: (error: Error) => {
      onResult({
        type: "url",
        input: url,
        error: error.message,
        timestamp: new Date(),
      });
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;
    mutation.mutate(url.trim());
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Ingest from URL</CardTitle>
        <CardDescription>
          Extract and index content from any webpage.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="flex gap-2">
          <Input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://example.com/article"
            className="flex-1"
            disabled={mutation.isPending}
          />
          <Button type="submit" disabled={!url.trim() || mutation.isPending}>
            {mutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              "Ingest"
            )}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

function YouTubeIngestForm({ onResult }: FormProps) {
  const [input, setInput] = React.useState("");

  const mutation = useMutation({
    mutationFn: (videoId: string) => ingestYouTube(videoId),
    onSuccess: (response) => {
      onResult({
        type: "youtube",
        input,
        response,
        timestamp: new Date(),
      });
      setInput("");
    },
    onError: (error: Error) => {
      onResult({
        type: "youtube",
        input,
        error: error.message,
        timestamp: new Date(),
      });
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;

    // Extract video ID from URL or use as-is
    const videoId = extractYouTubeId(input.trim());
    if (videoId) {
      mutation.mutate(videoId);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Ingest from YouTube</CardTitle>
        <CardDescription>
          Extract transcripts and metadata from YouTube videos.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="flex gap-2">
          <Input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Video URL or ID (e.g., dQw4w9WgXcQ)"
            className="flex-1"
            disabled={mutation.isPending}
          />
          <Button type="submit" disabled={!input.trim() || mutation.isPending}>
            {mutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              "Ingest"
            )}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

function TextIngestForm({ onResult }: FormProps) {
  const [title, setTitle] = React.useState("");
  const [content, setContent] = React.useState("");

  const mutation = useMutation({
    mutationFn: ({ content, title }: { content: string; title: string }) =>
      ingestText(content, title),
    onSuccess: (response) => {
      onResult({
        type: "text",
        input: title,
        response,
        timestamp: new Date(),
      });
      setTitle("");
      setContent("");
    },
    onError: (error: Error) => {
      onResult({
        type: "text",
        input: title,
        error: error.message,
        timestamp: new Date(),
      });
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !content.trim()) return;
    mutation.mutate({ content: content.trim(), title: title.trim() });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Ingest Text</CardTitle>
        <CardDescription>
          Add custom text content directly to the knowledge base.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Title"
            disabled={mutation.isPending}
          />
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="Content..."
            rows={6}
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
            disabled={mutation.isPending}
          />
          <Button
            type="submit"
            className="w-full"
            disabled={!title.trim() || !content.trim() || mutation.isPending}
          >
            {mutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
            ) : null}
            Ingest Text
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

function ResultCard({ result }: { result: IngestResult }) {
  const isSuccess = !!result.response && result.response.status === "success";
  const isError = !!result.error || result.response?.status === "error";

  return (
    <Card
      className={cn(
        "transition-colors",
        isSuccess && "border-green-200 dark:border-green-800",
        isError && "border-red-200 dark:border-red-800"
      )}
    >
      <CardContent className="p-3">
        <div className="flex items-start gap-2">
          {isSuccess ? (
            <CheckCircle2 className="h-5 w-5 text-green-600 flex-shrink-0" />
          ) : isError ? (
            <XCircle className="h-5 w-5 text-red-600 flex-shrink-0" />
          ) : (
            <Loader2 className="h-5 w-5 animate-spin flex-shrink-0" />
          )}
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between gap-2">
              <span className="font-medium text-sm truncate">
                {result.response?.title || result.input}
              </span>
              <span className="text-xs text-muted-foreground capitalize">
                {result.type}
              </span>
            </div>
            {result.response && (
              <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                <span>{result.response.chunk_count} chunks</span>
                <span>{formatBytes(result.response.content_length)}</span>
                <span>{formatDuration(result.response.ingestion_time_ms)}</span>
              </div>
            )}
            {result.error && (
              <p className="text-xs text-red-600 mt-1">{result.error}</p>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function extractYouTubeId(input: string): string | null {
  // Already a video ID
  if (/^[\w-]{11}$/.test(input)) {
    return input;
  }

  // YouTube URL patterns
  const patterns = [
    /(?:youtube\.com\/watch\?v=|youtu\.be\/)([\w-]{11})/,
    /youtube\.com\/embed\/([\w-]{11})/,
    /youtube\.com\/v\/([\w-]{11})/,
  ];

  for (const pattern of patterns) {
    const match = input.match(pattern);
    if (match?.[1]) {
      return match[1];
    }
  }

  return null;
}
