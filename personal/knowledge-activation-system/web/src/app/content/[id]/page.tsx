"use client";

import { useEffect, useState, use } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
  TooltipProvider,
} from "@/components/ui/tooltip";
import {
  ArrowLeft,
  ExternalLink,
  Trash2,
  Brain,
  Calendar,
  Tag,
  Layers,
  ChevronRight,
  Copy,
  Check,
} from "lucide-react";
import {
  getContentById,
  deleteContent,
  enableReview,
  type ContentDetail,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import { ContentDetailSkeleton } from "@/components/loading-states";

export default function ContentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();
  const [content, setContent] = useState<ContentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [activeChunk, setActiveChunk] = useState<number>(0);
  const [copied, setCopied] = useState(false);
  const [addingToReview, setAddingToReview] = useState(false);

  useEffect(() => {
    loadContent();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const loadContent = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getContentById(id);
      setContent(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load content");
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!content) return;
    if (!confirm(`Are you sure you want to delete "${content.title}"?`)) return;

    setDeleting(true);
    try {
      await deleteContent(id);
      router.push("/content");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete content");
      setDeleting(false);
    }
  };

  const handleAddToReview = async () => {
    if (!content) return;
    setAddingToReview(true);
    try {
      await enableReview(id);
      // Show success feedback
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add to review");
    } finally {
      setAddingToReview(false);
    }
  };

  const handleCopyChunk = async (text: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
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

  if (loading) {
    return <ContentDetailSkeleton />;
  }

  if (error || !content) {
    return (
      <div className="p-6">
        <Link href="/content">
          <Button variant="ghost" size="sm" className="gap-2 mb-6">
            <ArrowLeft className="h-4 w-4" />
            Back to Content
          </Button>
        </Link>
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <p className="text-destructive">{error || "Content not found"}</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <TooltipProvider>
      <div className="p-6 space-y-6">
        {/* Breadcrumb */}
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Link href="/content" className="hover:text-foreground transition-colors">
            Content
          </Link>
          <ChevronRight className="h-4 w-4" />
          <span className="text-foreground truncate max-w-md">{content.title}</span>
        </div>

        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <h1 className="text-2xl font-bold mb-2 break-words">{content.title}</h1>
            <div className="flex items-center gap-3 flex-wrap">
              <Badge variant="outline" className={getTypeColor(content.content_type)}>
                {content.content_type}
              </Badge>
              <span className="text-sm text-muted-foreground flex items-center gap-1">
                <Layers className="h-4 w-4" />
                {content.chunks.length} chunk{content.chunks.length !== 1 ? "s" : ""}
              </span>
              <span className="text-sm text-muted-foreground flex items-center gap-1">
                <Calendar className="h-4 w-4" />
                {new Date(content.created_at).toLocaleDateString()}
              </span>
            </div>
          </div>
          <div className="flex gap-2 shrink-0">
            <Button
              variant="outline"
              className="gap-2"
              onClick={handleAddToReview}
              disabled={addingToReview}
            >
              <Brain className="h-4 w-4" />
              {addingToReview ? "Adding..." : "Add to Review"}
            </Button>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="destructive"
                  size="icon"
                  onClick={handleDelete}
                  disabled={deleting}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Delete content</TooltipContent>
            </Tooltip>
          </div>
        </div>

        {/* Two Column Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Content - Chunks */}
          <div className="lg:col-span-2 space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">
                  Content Chunks ({content.chunks.length})
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {content.chunks.map((chunk, index) => (
                    <div
                      key={chunk.id}
                      id={`chunk-${index}`}
                      className={cn(
                        "p-4 rounded-lg border transition-colors relative group",
                        activeChunk === index
                          ? "border-primary bg-primary/5"
                          : "border-border hover:border-muted-foreground/50"
                      )}
                      onClick={() => setActiveChunk(index)}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium text-muted-foreground">
                          Chunk #{chunk.chunk_index + 1}
                        </span>
                        <div className="flex items-center gap-2">
                          {chunk.source_ref && (
                            <code className="text-xs bg-muted px-2 py-1 rounded">
                              {chunk.source_ref}
                            </code>
                          )}
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-7 w-7 p-0 opacity-0 group-hover:opacity-100 transition-opacity"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleCopyChunk(chunk.chunk_text);
                                }}
                              >
                                {copied && activeChunk === index ? (
                                  <Check className="h-3 w-3 text-green-500" />
                                ) : (
                                  <Copy className="h-3 w-3" />
                                )}
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>Copy chunk text</TooltipContent>
                          </Tooltip>
                        </div>
                      </div>
                      <p className="text-sm whitespace-pre-wrap leading-relaxed">
                        {chunk.chunk_text}
                      </p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Sidebar - Metadata */}
          <div className="space-y-4">
            {/* Quick Info */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Details</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {content.url && (
                  <div>
                    <p className="text-sm font-medium mb-1">Source URL</p>
                    <a
                      href={content.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-primary hover:underline flex items-center gap-1 break-all"
                    >
                      <span className="truncate">{content.url}</span>
                      <ExternalLink className="h-3 w-3 shrink-0" />
                    </a>
                  </div>
                )}

                <div>
                  <p className="text-sm font-medium mb-1">File Path</p>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <code className="text-xs bg-muted p-2 rounded block truncate cursor-help">
                        {content.filepath}
                      </code>
                    </TooltipTrigger>
                    <TooltipContent side="bottom" className="max-w-md">
                      <p className="text-xs break-all">{content.filepath}</p>
                    </TooltipContent>
                  </Tooltip>
                </div>

                <Separator />

                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <p className="text-muted-foreground">Created</p>
                    <p className="font-medium">
                      {new Date(content.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Updated</p>
                    <p className="font-medium">
                      {new Date(content.updated_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Tags */}
            {content.tags.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2">
                    <Tag className="h-4 w-4" />
                    Tags ({content.tags.length})
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-wrap gap-2">
                    {content.tags.map((tag) => (
                      <Badge key={tag} variant="secondary">
                        {tag}
                      </Badge>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Metadata */}
            {content.metadata && Object.keys(content.metadata).length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Metadata</CardTitle>
                </CardHeader>
                <CardContent>
                  <ScrollArea className="h-48">
                    <pre className="text-xs bg-muted p-3 rounded overflow-x-auto">
                      {JSON.stringify(content.metadata, null, 2)}
                    </pre>
                  </ScrollArea>
                </CardContent>
              </Card>
            )}

            {/* Chunk Navigation */}
            {content.chunks.length > 1 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Jump to Chunk</CardTitle>
                </CardHeader>
                <CardContent>
                  <ScrollArea className="h-32">
                    <div className="space-y-1">
                      {content.chunks.map((chunk, index) => (
                        <button
                          key={chunk.id}
                          onClick={() => {
                            setActiveChunk(index);
                            document.getElementById(`chunk-${index}`)?.scrollIntoView({
                              behavior: "smooth",
                              block: "center",
                            });
                          }}
                          className={cn(
                            "w-full text-left text-sm px-3 py-2 rounded transition-colors",
                            activeChunk === index
                              ? "bg-primary text-primary-foreground"
                              : "hover:bg-muted"
                          )}
                        >
                          <span className="font-mono">#{chunk.chunk_index + 1}</span>
                          {chunk.source_ref && (
                            <span className="ml-2 text-xs opacity-70">
                              {chunk.source_ref}
                            </span>
                          )}
                        </button>
                      ))}
                    </div>
                  </ScrollArea>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </div>
    </TooltipProvider>
  );
}
