"use client";

import * as React from "react";
import { ExternalLink, FileText, Clock, ChevronDown, ChevronUp } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  cn,
  formatConfidence,
  getConfidenceLevel,
  truncate,
  extractDomain,
  formatDuration,
} from "@/lib/utils";
import type { SearchResult, SearchResponse } from "@/types/api";

interface SearchResultsProps {
  response: SearchResponse | null;
  isLoading?: boolean;
  error?: Error | null;
}

export function SearchResults({
  response,
  isLoading,
  error,
}: SearchResultsProps) {
  if (isLoading) {
    return <SearchResultsSkeleton />;
  }

  if (error) {
    return (
      <Card className="border-destructive">
        <CardContent className="p-6">
          <p className="text-destructive">
            Error: {error.message}
          </p>
        </CardContent>
      </Card>
    );
  }

  if (!response) {
    return null;
  }

  if (response.results.length === 0) {
    return (
      <Card>
        <CardContent className="p-6 text-center">
          <p className="text-muted-foreground">
            No results found for &ldquo;{response.query}&rdquo;
          </p>
          <p className="text-sm text-muted-foreground mt-2">
            Try different keywords or broaden your search.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Results header */}
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>
          {response.total_found} result{response.total_found !== 1 ? "s" : ""} found
        </span>
        <span className="flex items-center gap-1">
          <Clock className="h-3 w-3" />
          {formatDuration(response.search_time_ms)}
          {response.reranked && (
            <span className="ml-2 px-1.5 py-0.5 bg-secondary rounded text-xs">
              Reranked
            </span>
          )}
        </span>
      </div>

      {/* Results list */}
      <div className="space-y-3">
        {response.results.map((result, index) => (
          <SearchResultCard key={result.id} result={result} rank={index + 1} />
        ))}
      </div>
    </div>
  );
}

interface SearchResultCardProps {
  result: SearchResult;
  rank: number;
}

function SearchResultCard({ result, rank }: SearchResultCardProps) {
  const [isExpanded, setIsExpanded] = React.useState(false);
  const confidenceLevel = getConfidenceLevel(result.score);

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardContent className="p-4">
        <div className="flex items-start gap-3">
          {/* Rank badge */}
          <div className="flex-shrink-0 w-6 h-6 rounded-full bg-secondary flex items-center justify-center text-xs font-medium">
            {rank}
          </div>

          <div className="flex-1 min-w-0">
            {/* Title and source */}
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 min-w-0">
                <h3 className="font-medium text-base truncate">
                  {result.document_title || "Untitled Document"}
                </h3>
                {result.source_url && (
                  <a
                    href={result.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-muted-foreground hover:text-primary flex items-center gap-1 mt-0.5"
                  >
                    <FileText className="h-3 w-3" />
                    {extractDomain(result.source_url)}
                    <ExternalLink className="h-3 w-3" />
                  </a>
                )}
              </div>

              {/* Confidence score */}
              <div
                className={cn(
                  "flex-shrink-0 text-sm font-medium",
                  confidenceLevel === "high" && "confidence-high",
                  confidenceLevel === "medium" && "confidence-medium",
                  confidenceLevel === "low" && "confidence-low"
                )}
              >
                {formatConfidence(result.score)}
              </div>
            </div>

            {/* Content preview */}
            <p className="mt-2 text-sm text-muted-foreground">
              {isExpanded
                ? result.content
                : truncate(result.content, 200)}
            </p>

            {/* Highlights */}
            {result.highlights && result.highlights.length > 0 && (
              <div className="mt-2 text-sm">
                {result.highlights.map((highlight, i) => (
                  <span
                    key={i}
                    className="search-highlight"
                    dangerouslySetInnerHTML={{ __html: highlight }}
                  />
                ))}
              </div>
            )}

            {/* Expand/collapse button */}
            {result.content.length > 200 && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setIsExpanded(!isExpanded)}
                className="mt-2 h-8 text-xs"
              >
                {isExpanded ? (
                  <>
                    <ChevronUp className="h-3 w-3 mr-1" />
                    Show less
                  </>
                ) : (
                  <>
                    <ChevronDown className="h-3 w-3 mr-1" />
                    Show more
                  </>
                )}
              </Button>
            )}

            {/* Metadata tags */}
            <div className="mt-2 flex flex-wrap gap-1">
              {result.metadata.section && (
                <span className="px-2 py-0.5 bg-secondary text-xs rounded">
                  {result.metadata.section}
                </span>
              )}
              {result.metadata.page && (
                <span className="px-2 py-0.5 bg-secondary text-xs rounded">
                  Page {result.metadata.page}
                </span>
              )}
              {result.metadata.timestamp_start !== undefined && (
                <span className="px-2 py-0.5 bg-secondary text-xs rounded">
                  {formatTimestamp(result.metadata.timestamp_start)}
                </span>
              )}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function formatTimestamp(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

function SearchResultsSkeleton() {
  return (
    <div className="space-y-3">
      {[1, 2, 3].map((i) => (
        <Card key={i}>
          <CardContent className="p-4">
            <div className="flex items-start gap-3">
              <div className="w-6 h-6 rounded-full bg-muted animate-pulse" />
              <div className="flex-1 space-y-2">
                <div className="h-5 bg-muted rounded animate-pulse w-3/4" />
                <div className="h-4 bg-muted rounded animate-pulse w-1/2" />
                <div className="h-4 bg-muted rounded animate-pulse w-full" />
                <div className="h-4 bg-muted rounded animate-pulse w-2/3" />
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
