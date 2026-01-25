"use client";

import * as React from "react";
import Link from "next/link";
import { Brain, ArrowLeft, Send, Loader2, ExternalLink, AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAskQuestion } from "@/hooks/use-query";
import { cn, formatConfidence, getConfidenceLevel, formatDuration } from "@/lib/utils";
import type { QueryResponse, QuerySource } from "@/types/api";

export default function AskPage() {
  const [question, setQuestion] = React.useState("");
  const [response, setResponse] = React.useState<QueryResponse | null>(null);

  const askMutation = useAskQuestion();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;

    askMutation.mutate(
      { question: question.trim() },
      {
        onSuccess: (data) => {
          setResponse(data);
        },
      }
    );
  };

  const confidenceLevel = response ? getConfidenceLevel(response.confidence) : null;

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container flex h-14 items-center">
          <Link href="/" className="flex items-center gap-2 text-muted-foreground hover:text-primary transition-colors">
            <ArrowLeft className="h-4 w-4" />
            Back
          </Link>
          <div className="flex items-center gap-2 ml-4">
            <Brain className="h-6 w-6 text-primary" />
            <span className="font-semibold text-lg">Ask a Question</span>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 container py-8">
        <div className="max-w-3xl mx-auto">
          {/* Question input */}
          <form onSubmit={handleSubmit} className="mb-8">
            <div className="flex gap-2">
              <Input
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Ask anything about your knowledge base..."
                className="flex-1 h-12 text-base"
                disabled={askMutation.isPending}
              />
              <Button
                type="submit"
                size="lg"
                disabled={!question.trim() || askMutation.isPending}
              >
                {askMutation.isPending ? (
                  <Loader2 className="h-5 w-5 animate-spin" />
                ) : (
                  <Send className="h-5 w-5" />
                )}
              </Button>
            </div>
          </form>

          {/* Error display */}
          {askMutation.error && (
            <Card className="border-destructive mb-6">
              <CardContent className="p-4 text-destructive">
                Error: {askMutation.error.message}
              </CardContent>
            </Card>
          )}

          {/* Loading state */}
          {askMutation.isPending && (
            <Card className="mb-6">
              <CardContent className="p-6">
                <div className="flex items-center gap-3">
                  <Loader2 className="h-5 w-5 animate-spin text-primary" />
                  <p className="text-muted-foreground">
                    Searching knowledge base and generating answer...
                  </p>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Response */}
          {response && !askMutation.isPending && (
            <div className="space-y-6">
              {/* Answer card */}
              <Card>
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-lg">Answer</CardTitle>
                    <div className="flex items-center gap-2 text-sm">
                      {/* Confidence indicator */}
                      <span
                        className={cn(
                          "font-medium",
                          confidenceLevel === "high" && "confidence-high",
                          confidenceLevel === "medium" && "confidence-medium",
                          confidenceLevel === "low" && "confidence-low"
                        )}
                      >
                        {formatConfidence(response.confidence)} confidence
                      </span>
                      <span className="text-muted-foreground">
                        {formatDuration(response.query_time_ms)}
                      </span>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  {/* Low confidence warning */}
                  {confidenceLevel === "low" && (
                    <div className="flex items-center gap-2 p-3 mb-4 bg-yellow-50 dark:bg-yellow-950 border border-yellow-200 dark:border-yellow-800 rounded-md text-sm">
                      <AlertTriangle className="h-4 w-4 text-yellow-600" />
                      <span className="text-yellow-700 dark:text-yellow-300">
                        Low confidence answer. The knowledge base may not have enough relevant information.
                      </span>
                    </div>
                  )}

                  {/* Answer text */}
                  <div className="prose prose-sm dark:prose-invert max-w-none">
                    {response.answer.split("\n").map((paragraph, i) => (
                      <p key={i}>{paragraph}</p>
                    ))}
                  </div>

                  {/* Token usage */}
                  {response.tokens_used && (
                    <div className="mt-4 pt-4 border-t text-xs text-muted-foreground">
                      Tokens: {response.tokens_used.input} in, {response.tokens_used.output} out
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Sources */}
              {response.sources.length > 0 && (
                <div>
                  <h3 className="text-sm font-medium mb-3 text-muted-foreground">
                    Sources ({response.sources.length})
                  </h3>
                  <div className="space-y-2">
                    {response.sources.map((source, index) => (
                      <SourceCard key={source.chunk_id} source={source} index={index + 1} />
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Empty state */}
          {!response && !askMutation.isPending && (
            <div className="text-center py-12 text-muted-foreground">
              <Brain className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p className="text-lg">Ask a question to get started</p>
              <p className="text-sm mt-2">
                Your question will be answered using the knowledge base with source citations.
              </p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

interface SourceCardProps {
  source: QuerySource;
  index: number;
}

function SourceCard({ source, index }: SourceCardProps) {
  return (
    <Card className="hover:shadow-sm transition-shadow">
      <CardContent className="p-3">
        <div className="flex items-start gap-2">
          <span className="flex-shrink-0 w-5 h-5 rounded-full bg-secondary flex items-center justify-center text-xs font-medium">
            {index}
          </span>
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between gap-2">
              <h4 className="font-medium text-sm truncate">
                {source.document_title}
              </h4>
              <span className="text-xs text-muted-foreground">
                {Math.round(source.relevance_score * 100)}%
              </span>
            </div>
            <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
              {source.content_preview}
            </p>
            {source.source_url && (
              <a
                href={source.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-primary hover:underline flex items-center gap-1 mt-1"
              >
                View source
                <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
