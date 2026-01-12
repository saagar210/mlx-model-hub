"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
  TooltipProvider,
} from "@/components/ui/tooltip";
import {
  Search,
  Filter,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Youtube,
  Bookmark,
  FileText,
  FileIcon,
  StickyNote,
  MoreHorizontal,
  Eye,
  Trash2,
  Brain,
  ArrowUpDown,
  RefreshCw,
  X,
} from "lucide-react";
import {
  getContent,
  getStats,
  deleteContent,
  enableReview,
  type ContentItem,
  type ContentType,
  type StatsResponse,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import { useDebounce } from "@/hooks/use-debounce";
import { ContentTableSkeleton } from "@/components/loading-states";

const contentTypes: ContentType[] = ["youtube", "bookmark", "note", "pdf", "file"];
const PAGE_SIZE = 25;

export default function ContentPage() {
  const [content, setContent] = useState<ContentItem[]>([]);
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [filter, setFilter] = useState<ContentType | "all">("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<"date" | "title">("date");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);

  const debouncedSearch = useDebounce(searchQuery, 300);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [contentData, statsData] = await Promise.all([
        getContent(filter === "all" ? undefined : filter, PAGE_SIZE, page),
        getStats(),
      ]);
      setContent(contentData.items);
      setTotal(contentData.total);
      setStats(statsData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load content");
    } finally {
      setLoading(false);
    }
  }, [filter, page]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Reset page when filter changes
  useEffect(() => {
    setPage(1);
  }, [filter]);

  const handleDelete = async (id: string, title: string) => {
    if (!confirm(`Are you sure you want to delete "${title}"?`)) return;
    try {
      await deleteContent(id);
      setContent((prev) => prev.filter((item) => item.id !== id));
      setTotal((prev) => prev - 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete");
    }
  };

  const handleAddToReview = async (id: string) => {
    try {
      await enableReview(id);
      // Could show a toast notification here
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add to review");
    }
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

  const getTypeBadgeColor = (type: string) => {
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

  // Filter and sort content locally (for search within current page)
  const filteredContent = content
    .filter((item) => {
      if (!debouncedSearch) return true;
      const query = debouncedSearch.toLowerCase();
      return (
        item.title.toLowerCase().includes(query) ||
        item.tags.some((tag) => tag.toLowerCase().includes(query))
      );
    })
    .sort((a, b) => {
      if (sortBy === "date") {
        const dateA = new Date(a.created_at).getTime();
        const dateB = new Date(b.created_at).getTime();
        return sortOrder === "desc" ? dateB - dateA : dateA - dateB;
      } else {
        const compare = a.title.localeCompare(b.title);
        return sortOrder === "desc" ? -compare : compare;
      }
    });

  const toggleSort = (field: "date" | "title") => {
    if (sortBy === field) {
      setSortOrder((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(field);
      setSortOrder("desc");
    }
  };

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <TooltipProvider>
      <div className="p-6 space-y-6">
        {/* Page Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Content Library</h1>
            <p className="text-muted-foreground">
              {stats ? (
                <>
                  {stats.total_content.toLocaleString()} items, {stats.total_chunks.toLocaleString()} chunks indexed
                </>
              ) : (
                "Loading..."
              )}
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={loadData}
            disabled={loading}
          >
            <RefreshCw className={cn("h-4 w-4 mr-2", loading && "animate-spin")} />
            Refresh
          </Button>
        </div>

        {/* Filters and Search */}
        <Card>
          <CardContent className="p-4">
            <div className="flex flex-wrap gap-4 items-center">
              {/* Search */}
              <div className="relative flex-1 min-w-[200px]">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search by title or tag..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-9 pr-9"
                />
                {searchQuery && (
                  <button
                    onClick={() => setSearchQuery("")}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    <X className="h-4 w-4" />
                  </button>
                )}
              </div>

              {/* Type Filter */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" className="gap-2">
                    <Filter className="h-4 w-4" />
                    {filter === "all" ? "All Types" : (
                      <span className="capitalize">{filter}</span>
                    )}
                    <ChevronDown className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onClick={() => setFilter("all")}>
                    All Types
                    {stats && (
                      <span className="ml-auto text-muted-foreground">
                        ({stats.total_content})
                      </span>
                    )}
                  </DropdownMenuItem>
                  {contentTypes.map((type) => (
                    <DropdownMenuItem key={type} onClick={() => setFilter(type)}>
                      <span className="flex items-center gap-2">
                        {getTypeIcon(type)}
                        <span className="capitalize">{type}</span>
                      </span>
                      {stats && (
                        <span className="ml-auto text-muted-foreground">
                          ({stats.content_by_type[type] || 0})
                        </span>
                      )}
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
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

        {/* Content Table */}
        <Card>
          <CardContent className="p-0">
            {loading ? (
              <ContentTableSkeleton rows={10} />
            ) : filteredContent.length === 0 ? (
              <div className="p-8 text-center text-muted-foreground">
                <FileText className="h-12 w-12 mx-auto mb-4 opacity-20" />
                <p className="text-lg mb-1">No content found</p>
                <p className="text-sm">
                  {searchQuery
                    ? "Try a different search term"
                    : "Ingest content using the CLI to get started"}
                </p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-24">Type</TableHead>
                    <TableHead>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="gap-1 -ml-3 h-8"
                        onClick={() => toggleSort("title")}
                      >
                        Title
                        <ArrowUpDown className="h-3 w-3" />
                      </Button>
                    </TableHead>
                    <TableHead className="hidden md:table-cell">Tags</TableHead>
                    <TableHead className="hidden lg:table-cell w-32">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="gap-1 -ml-3 h-8"
                        onClick={() => toggleSort("date")}
                      >
                        Created
                        <ArrowUpDown className="h-3 w-3" />
                      </Button>
                    </TableHead>
                    <TableHead className="w-12"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredContent.map((item) => (
                    <TableRow key={item.id} className="group">
                      <TableCell>
                        <Badge
                          variant="outline"
                          className={cn("text-xs", getTypeBadgeColor(item.content_type))}
                        >
                          {item.content_type}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Link
                          href={`/content/${item.id}`}
                          className="font-medium hover:text-primary transition-colors line-clamp-1"
                        >
                          {item.title}
                        </Link>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <p className="text-xs text-muted-foreground truncate max-w-md cursor-help">
                              {item.filepath}
                            </p>
                          </TooltipTrigger>
                          <TooltipContent side="bottom" className="max-w-md">
                            <p className="text-xs break-all">{item.filepath}</p>
                          </TooltipContent>
                        </Tooltip>
                      </TableCell>
                      <TableCell className="hidden md:table-cell">
                        <div className="flex gap-1 flex-wrap">
                          {item.tags.slice(0, 3).map((tag) => (
                            <Badge key={tag} variant="secondary" className="text-xs">
                              {tag}
                            </Badge>
                          ))}
                          {item.tags.length > 3 && (
                            <Tooltip>
                              <TooltipTrigger>
                                <Badge variant="secondary" className="text-xs cursor-help">
                                  +{item.tags.length - 3}
                                </Badge>
                              </TooltipTrigger>
                              <TooltipContent>
                                {item.tags.slice(3).join(", ")}
                              </TooltipContent>
                            </Tooltip>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="hidden lg:table-cell text-muted-foreground text-sm">
                        {new Date(item.created_at).toLocaleDateString()}
                      </TableCell>
                      <TableCell>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-8 w-8 p-0 opacity-0 group-hover:opacity-100 transition-opacity"
                            >
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem asChild>
                              <Link href={`/content/${item.id}`}>
                                <Eye className="h-4 w-4 mr-2" />
                                View Details
                              </Link>
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => handleAddToReview(item.id)}>
                              <Brain className="h-4 w-4 mr-2" />
                              Add to Review
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              className="text-destructive focus:text-destructive"
                              onClick={() => handleDelete(item.id, item.title)}
                            >
                              <Trash2 className="h-4 w-4 mr-2" />
                              Delete
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        {/* Pagination */}
        {!loading && totalPages > 1 && (
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              Showing {((page - 1) * PAGE_SIZE) + 1} - {Math.min(page * PAGE_SIZE, total)} of {total} items
            </p>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
              >
                <ChevronLeft className="h-4 w-4 mr-1" />
                Previous
              </Button>
              <span className="text-sm text-muted-foreground px-2">
                Page {page} of {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
              >
                Next
                <ChevronRight className="h-4 w-4 ml-1" />
              </Button>
            </div>
          </div>
        )}
      </div>
    </TooltipProvider>
  );
}
