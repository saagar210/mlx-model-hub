"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
  DropdownMenuCheckboxItem,
} from "@/components/ui/dropdown-menu";
import {
  Search,
  Sparkles,
  Filter,
  ArrowUpDown,
  X,
  Youtube,
  Bookmark,
  FileText,
  FileIcon,
  StickyNote,
  ChevronDown,
} from "lucide-react";
import {
  search,
  ask,
  type SearchResult,
  type AskResponse,
  type SearchMode,
  type ContentType,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import { useDebounce } from "@/hooks/use-debounce";
import { SearchResultsSkeleton } from "@/components/loading-states";

type SortOption = "relevance" | "date";
type ContentTypeFilter = ContentType | "all";

const CONTENT_TYPES: ContentType[] = ["youtube", "bookmark", "note", "pdf", "file"];

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [searchMode, setSearchMode] = useState<SearchMode>("hybrid");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [answer, setAnswer] = useState<AskResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"search" | "ask">("search");

  // Filters
  const [typeFilter, setTypeFilter] = useState<ContentTypeFilter>("all");
  const [sortBy, setSortBy] = useState<SortOption>("relevance");

  // Debounce for instant search
  const debouncedQuery = useDebounce(query, 300);

  // Auto-search when query changes (debounced)
  useEffect(() => {
    if (activeTab === "search" && debouncedQuery.trim().length >= 2) {
      performSearch();
    } else if (debouncedQuery.trim().length === 0) {
      setResults([]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedQuery, searchMode, activeTab]);

  const performSearch = useCallback(async () => {
    if (!debouncedQuery.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const response = await search(debouncedQuery, 30, searchMode);
      setResults(response.results);
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setLoading(false);
    }
  }, [debouncedQuery, searchMode]);

  const handleAsk = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError(null);
    setAnswer(null);

    try {
      const response = await ask(query);
      setAnswer(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setLoading(false);
    }
  };

  const clearSearch = () => {
    setQuery("");
    setResults([]);
    setAnswer(null);
    setError(null);
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case "youtube":
        return <Youtube className="h-4 w-4 text-red-500" />;
      case "bookmark":
        return <Bookmark className="h-4 w-4 text-blue-500" />;
      case "note":
        return <StickyNote className="h-4 w-4 text-green-500" />;
      case "pdf":
        return <FileIcon className="h-4 w-4 text-orange-500" />;
      default:
        return <FileText className="h-4 w-4 text-gray-500" />;
    }
  };

  const getTypeColor = (type: string) => {
    switch (type) {
      case "youtube":
        return "bg-red-500/10 text-red-500 border-red-500/20";
      case "bookmark":
        return "bg-blue-500/10 text-blue-500 border-blue-500/20";
      case "note":
        return "bg-green-500/10 text-green-500 border-green-500/20";
      case "pdf":
        return "bg-orange-500/10 text-orange-500 border-orange-500/20";
      default:
        return "bg-gray-500/10 text-gray-500 border-gray-500/20";
    }
  };

  const getConfidenceColor = (level: string) => {
    switch (level) {
      case "high":
        return "bg-green-500/10 text-green-500 border-green-500/20";
      case "medium":
        return "bg-yellow-500/10 text-yellow-500 border-yellow-500/20";
      case "low":
        return "bg-red-500/10 text-red-500 border-red-500/20";
      default:
        return "bg-gray-500/10 text-gray-500 border-gray-500/20";
    }
  };

  // Apply filters and sorting to results
  const filteredResults = results
    .filter((result) => {
      if (typeFilter === "all") return true;
      return result.content_type === typeFilter;
    })
    .sort((a, b) => {
      if (sortBy === "relevance") {
        return b.score - a.score;
      }
      // For date sorting, we'd need date info in the result
      // For now, maintain relevance order
      return 0;
    });

  const activeFilterCount = (typeFilter !== "all" ? 1 : 0);

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Search</h1>
          <p className="text-muted-foreground">
            Search your knowledge base or ask questions
          </p>
        </div>
      </div>

      {/* Search Area */}
      <Card>
        <CardContent className="p-6">
          <Tabs
            value={activeTab}
            onValueChange={(v) => {
              setActiveTab(v as "search" | "ask");
              setResults([]);
              setAnswer(null);
              setError(null);
            }}
          >
            <div className="flex items-center justify-between mb-4">
              <TabsList>
                <TabsTrigger value="search" className="gap-2">
                  <Search className="h-4 w-4" />
                  Search
                </TabsTrigger>
                <TabsTrigger value="ask" className="gap-2">
                  <Sparkles className="h-4 w-4" />
                  Ask AI
                </TabsTrigger>
              </TabsList>

              {activeTab === "search" && (
                <div className="flex items-center gap-2">
                  <span className="text-sm text-muted-foreground">Mode:</span>
                  {(["hybrid", "bm25", "vector"] as const).map((m) => (
                    <Button
                      key={m}
                      type="button"
                      variant={searchMode === m ? "secondary" : "ghost"}
                      size="sm"
                      onClick={() => setSearchMode(m)}
                      className="text-xs h-7"
                    >
                      {m.toUpperCase()}
                    </Button>
                  ))}
                </div>
              )}
            </div>

            <form onSubmit={activeTab === "ask" ? handleAsk : (e) => e.preventDefault()}>
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <Input
                    type="text"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder={
                      activeTab === "ask"
                        ? "Ask a question about your knowledge base..."
                        : "Search for content... (starts automatically)"
                    }
                    className="h-12 text-base pr-10"
                    autoFocus
                  />
                  {query && (
                    <button
                      type="button"
                      onClick={clearSearch}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  )}
                </div>
                {activeTab === "ask" && (
                  <Button type="submit" disabled={loading} className="h-12 px-6">
                    {loading ? (
                      <span className="animate-pulse">...</span>
                    ) : (
                      <>
                        <Sparkles className="h-4 w-4 mr-2" />
                        Ask
                      </>
                    )}
                  </Button>
                )}
              </div>
            </form>
          </Tabs>
        </CardContent>
      </Card>

      {/* Error State */}
      {error && (
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <p className="text-destructive">{error}</p>
          </CardContent>
        </Card>
      )}

      {/* AI Answer */}
      {answer && (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-3">
              <Sparkles className="h-5 w-5 text-primary" />
              <CardTitle>AI Answer</CardTitle>
              <Badge variant="outline" className={getConfidenceColor(answer.confidence)}>
                {answer.confidence} ({(answer.confidence_score * 100).toFixed(0)}%)
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {answer.warning && (
              <div className="flex items-start gap-2 p-3 rounded-md bg-yellow-500/10 text-yellow-600 dark:text-yellow-400">
                <span className="text-sm">{answer.warning}</span>
              </div>
            )}
            {answer.error ? (
              <p className="text-destructive">{answer.error}</p>
            ) : (
              <div className="prose prose-sm dark:prose-invert max-w-none">
                <p className="whitespace-pre-wrap text-base leading-relaxed">
                  {answer.answer}
                </p>
              </div>
            )}

            {answer.citations.length > 0 && (
              <>
                <Separator />
                <div>
                  <h4 className="text-sm font-medium mb-3">Sources</h4>
                  <div className="grid gap-2">
                    {answer.citations.map((citation) => (
                      <div
                        key={citation.index}
                        className="flex items-start gap-3 p-3 rounded-md bg-muted/50"
                      >
                        <span className="font-mono text-xs bg-background px-2 py-1 rounded border">
                          {citation.index}
                        </span>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <Badge
                              variant="outline"
                              className={cn("text-xs", getTypeColor(citation.content_type))}
                            >
                              {citation.content_type}
                            </Badge>
                            <span className="text-sm font-medium truncate">
                              {citation.title}
                            </span>
                          </div>
                          {citation.chunk_text && (
                            <p className="text-xs text-muted-foreground line-clamp-2">
                              {citation.chunk_text}
                            </p>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      )}

      {/* Search Results */}
      {activeTab === "search" && (
        <>
          {/* Filters Row */}
          {(results.length > 0 || loading) && (
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-2">
                {/* Type Filter */}
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="outline" size="sm" className="gap-2">
                      <Filter className="h-4 w-4" />
                      Type
                      {typeFilter !== "all" && (
                        <Badge variant="secondary" className="ml-1 h-5 px-1.5">
                          1
                        </Badge>
                      )}
                      <ChevronDown className="h-4 w-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="start">
                    <DropdownMenuCheckboxItem
                      checked={typeFilter === "all"}
                      onCheckedChange={() => setTypeFilter("all")}
                    >
                      All Types
                    </DropdownMenuCheckboxItem>
                    <DropdownMenuSeparator />
                    {CONTENT_TYPES.map((type) => (
                      <DropdownMenuCheckboxItem
                        key={type}
                        checked={typeFilter === type}
                        onCheckedChange={() => setTypeFilter(type)}
                      >
                        <span className="flex items-center gap-2">
                          {getTypeIcon(type)}
                          <span className="capitalize">{type}</span>
                        </span>
                      </DropdownMenuCheckboxItem>
                    ))}
                  </DropdownMenuContent>
                </DropdownMenu>

                {/* Sort By */}
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="outline" size="sm" className="gap-2">
                      <ArrowUpDown className="h-4 w-4" />
                      Sort
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="start">
                    <DropdownMenuItem onClick={() => setSortBy("relevance")}>
                      {sortBy === "relevance" && "* "}Relevance
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => setSortBy("date")}>
                      {sortBy === "date" && "* "}Date
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>

                {/* Clear Filters */}
                {activeFilterCount > 0 && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setTypeFilter("all");
                      setSortBy("relevance");
                    }}
                    className="text-muted-foreground"
                  >
                    Clear filters
                  </Button>
                )}
              </div>

              <p className="text-sm text-muted-foreground">
                {loading ? (
                  "Searching..."
                ) : (
                  <>
                    {filteredResults.length} of {results.length} results
                  </>
                )}
              </p>
            </div>
          )}

          {/* Loading State */}
          {loading && <SearchResultsSkeleton count={5} />}

          {/* Results List */}
          {!loading && filteredResults.length > 0 && (
            <div className="grid gap-3">
              {filteredResults.map((result, index) => (
                <Link
                  key={`${result.content_id}-${index}`}
                  href={`/content/${result.content_id}`}
                >
                  <Card className="hover:border-primary/30 hover:bg-muted/30 transition-colors cursor-pointer">
                    <CardContent className="p-4">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-2">
                            <Badge
                              variant="outline"
                              className={getTypeColor(result.content_type)}
                            >
                              {result.content_type}
                            </Badge>
                            <span className="font-medium truncate">
                              {result.title}
                            </span>
                          </div>
                          <p className="text-sm text-muted-foreground line-clamp-3">
                            {result.chunk_text}
                          </p>
                          {result.source_ref && (
                            <p className="text-xs text-muted-foreground mt-2 font-mono">
                              {result.source_ref}
                            </p>
                          )}
                        </div>
                        <div className="text-right shrink-0">
                          <div className="text-xs font-mono text-muted-foreground">
                            Score: {result.score.toFixed(3)}
                          </div>
                          {(result.bm25_rank || result.vector_rank) && (
                            <div className="text-xs text-muted-foreground mt-1">
                              {result.bm25_rank && <span>BM25: #{result.bm25_rank}</span>}
                              {result.bm25_rank && result.vector_rank && <span> | </span>}
                              {result.vector_rank && <span>Vec: #{result.vector_rank}</span>}
                            </div>
                          )}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              ))}
            </div>
          )}

          {/* No Results for Filter */}
          {!loading && results.length > 0 && filteredResults.length === 0 && (
            <Card>
              <CardContent className="py-12">
                <div className="text-center text-muted-foreground">
                  <Filter className="h-12 w-12 mx-auto mb-4 opacity-20" />
                  <p className="text-lg mb-1">No results match your filters</p>
                  <p className="text-sm mb-4">Try adjusting your filter settings</p>
                  <Button variant="outline" onClick={() => setTypeFilter("all")}>
                    Clear Filters
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Empty State */}
          {!loading && !error && results.length === 0 && query.length >= 2 && (
            <Card>
              <CardContent className="py-12">
                <div className="text-center text-muted-foreground">
                  <Search className="h-12 w-12 mx-auto mb-4 opacity-20" />
                  <p className="text-lg mb-1">No results found</p>
                  <p className="text-sm">Try a different search term or use Ask AI</p>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Initial State */}
          {!loading && !error && results.length === 0 && query.length < 2 && (
            <Card>
              <CardContent className="py-12">
                <div className="text-center text-muted-foreground">
                  <Search className="h-12 w-12 mx-auto mb-4 opacity-20" />
                  <p className="text-lg mb-1">Search your knowledge base</p>
                  <p className="text-sm">
                    Type at least 2 characters to start searching
                  </p>
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}

      {/* Ask Tab Initial State */}
      {activeTab === "ask" && !loading && !error && !answer && (
        <Card>
          <CardContent className="py-12">
            <div className="text-center text-muted-foreground">
              <Sparkles className="h-12 w-12 mx-auto mb-4 opacity-20" />
              <p className="text-lg mb-1">Ask a question</p>
              <p className="text-sm">
                Get AI-powered answers from your knowledge base
              </p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
