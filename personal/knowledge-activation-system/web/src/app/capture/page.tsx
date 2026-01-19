"use client";

import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "sonner";
import {
  PenLine,
  Link as LinkIcon,
  Plus,
  X,
  Loader2,
  CheckCircle,
  FileText,
  Globe,
} from "lucide-react";
import { captureContent, captureUrl, type CaptureResponse } from "@/lib/api";

export default function CapturePage() {
  // Text capture state
  const [textContent, setTextContent] = useState("");
  const [textTitle, setTextTitle] = useState("");
  const [textTags, setTextTags] = useState<string[]>([]);
  const [textTagInput, setTextTagInput] = useState("");
  const [textSubmitting, setTextSubmitting] = useState(false);

  // URL capture state
  const [urlInput, setUrlInput] = useState("");
  const [urlTags, setUrlTags] = useState<string[]>([]);
  const [urlTagInput, setUrlTagInput] = useState("");
  const [urlSubmitting, setUrlSubmitting] = useState(false);

  // Recent captures
  const [recentCaptures, setRecentCaptures] = useState<CaptureResponse[]>([]);

  const addTag = (tags: string[], setTags: (tags: string[]) => void, input: string, setInput: (s: string) => void) => {
    const tag = input.trim().toLowerCase();
    if (tag && !tags.includes(tag)) {
      setTags([...tags, tag]);
    }
    setInput("");
  };

  const removeTag = (tags: string[], setTags: (tags: string[]) => void, tagToRemove: string) => {
    setTags(tags.filter((t) => t !== tagToRemove));
  };

  const handleTextCapture = async () => {
    if (!textContent.trim()) {
      toast.error("Please enter some content to capture");
      return;
    }

    setTextSubmitting(true);
    try {
      const result = await captureContent({
        content: textContent,
        title: textTitle || undefined,
        tags: textTags.length > 0 ? textTags : undefined,
        content_type: "note",
      });

      setRecentCaptures([result, ...recentCaptures.slice(0, 4)]);
      setTextContent("");
      setTextTitle("");
      setTextTags([]);
      toast.success(`Captured "${result.title}" with ${result.chunks_created} chunks`);
    } catch (error) {
      console.error("Capture failed:", error);
      toast.error("Failed to capture content");
    } finally {
      setTextSubmitting(false);
    }
  };

  const handleUrlCapture = async () => {
    if (!urlInput.trim()) {
      toast.error("Please enter a URL to capture");
      return;
    }

    // Basic URL validation
    try {
      new URL(urlInput);
    } catch {
      toast.error("Please enter a valid URL");
      return;
    }

    setUrlSubmitting(true);
    try {
      const result = await captureUrl({
        url: urlInput,
        tags: urlTags.length > 0 ? urlTags : undefined,
      });

      setRecentCaptures([result, ...recentCaptures.slice(0, 4)]);
      setUrlInput("");
      setUrlTags([]);
      toast.success(`Captured "${result.title}" with ${result.chunks_created} chunks`);
    } catch (error) {
      console.error("URL capture failed:", error);
      toast.error("Failed to capture URL content");
    } finally {
      setUrlSubmitting(false);
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <PenLine className="h-6 w-6" />
          Quick Capture
        </h1>
        <p className="text-muted-foreground">
          Quickly add content to your knowledge base
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Capture Forms */}
        <div className="lg:col-span-2">
          <Tabs defaultValue="text" className="space-y-4">
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="text" className="gap-2">
                <FileText className="h-4 w-4" />
                Text Note
              </TabsTrigger>
              <TabsTrigger value="url" className="gap-2">
                <Globe className="h-4 w-4" />
                URL
              </TabsTrigger>
            </TabsList>

            {/* Text Capture Tab */}
            <TabsContent value="text">
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Capture Text</CardTitle>
                  <CardDescription>
                    Add a quick note, snippet, or any text content
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <Input
                      placeholder="Title (optional)"
                      value={textTitle}
                      onChange={(e) => setTextTitle(e.target.value)}
                    />
                  </div>
                  <div>
                    <Textarea
                      placeholder="Enter your content here..."
                      value={textContent}
                      onChange={(e) => setTextContent(e.target.value)}
                      rows={8}
                      className="resize-none"
                    />
                    <p className="text-xs text-muted-foreground mt-1">
                      {textContent.length} characters
                    </p>
                  </div>
                  <div>
                    <div className="flex gap-2 mb-2">
                      <Input
                        placeholder="Add tags..."
                        value={textTagInput}
                        onChange={(e) => setTextTagInput(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            e.preventDefault();
                            addTag(textTags, setTextTags, textTagInput, setTextTagInput);
                          }
                        }}
                      />
                      <Button
                        type="button"
                        variant="outline"
                        size="icon"
                        onClick={() => addTag(textTags, setTextTags, textTagInput, setTextTagInput)}
                      >
                        <Plus className="h-4 w-4" />
                      </Button>
                    </div>
                    {textTags.length > 0 && (
                      <div className="flex flex-wrap gap-2">
                        {textTags.map((tag) => (
                          <Badge key={tag} variant="secondary" className="gap-1">
                            {tag}
                            <button
                              type="button"
                              onClick={() => removeTag(textTags, setTextTags, tag)}
                              className="ml-1 hover:text-destructive"
                            >
                              <X className="h-3 w-3" />
                            </button>
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>
                  <Button
                    onClick={handleTextCapture}
                    disabled={textSubmitting || !textContent.trim()}
                    className="w-full gap-2"
                  >
                    {textSubmitting ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <PenLine className="h-4 w-4" />
                    )}
                    Capture Note
                  </Button>
                </CardContent>
              </Card>
            </TabsContent>

            {/* URL Capture Tab */}
            <TabsContent value="url">
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Capture URL</CardTitle>
                  <CardDescription>
                    Extract and save content from a web page
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <div className="flex gap-2">
                      <div className="relative flex-1">
                        <LinkIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                        <Input
                          placeholder="https://example.com/article"
                          value={urlInput}
                          onChange={(e) => setUrlInput(e.target.value)}
                          className="pl-10"
                        />
                      </div>
                    </div>
                  </div>
                  <div>
                    <div className="flex gap-2 mb-2">
                      <Input
                        placeholder="Add tags..."
                        value={urlTagInput}
                        onChange={(e) => setUrlTagInput(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            e.preventDefault();
                            addTag(urlTags, setUrlTags, urlTagInput, setUrlTagInput);
                          }
                        }}
                      />
                      <Button
                        type="button"
                        variant="outline"
                        size="icon"
                        onClick={() => addTag(urlTags, setUrlTags, urlTagInput, setUrlTagInput)}
                      >
                        <Plus className="h-4 w-4" />
                      </Button>
                    </div>
                    {urlTags.length > 0 && (
                      <div className="flex flex-wrap gap-2">
                        {urlTags.map((tag) => (
                          <Badge key={tag} variant="secondary" className="gap-1">
                            {tag}
                            <button
                              type="button"
                              onClick={() => removeTag(urlTags, setUrlTags, tag)}
                              className="ml-1 hover:text-destructive"
                            >
                              <X className="h-3 w-3" />
                            </button>
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>
                  <Button
                    onClick={handleUrlCapture}
                    disabled={urlSubmitting || !urlInput.trim()}
                    className="w-full gap-2"
                  >
                    {urlSubmitting ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Globe className="h-4 w-4" />
                    )}
                    Capture URL
                  </Button>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>

        {/* Recent Captures */}
        <div>
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Recent Captures</CardTitle>
              <CardDescription>
                Your latest captured content
              </CardDescription>
            </CardHeader>
            <CardContent>
              {recentCaptures.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <CheckCircle className="h-12 w-12 mx-auto mb-4 opacity-20" />
                  <p className="text-sm">No captures yet this session</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {recentCaptures.map((capture, index) => (
                    <div
                      key={`${capture.content_id}-${index}`}
                      className="p-3 rounded-lg border bg-muted/30"
                    >
                      <p className="font-medium text-sm truncate">{capture.title}</p>
                      <div className="flex items-center gap-2 mt-1">
                        <Badge variant="outline" className="text-xs">
                          {capture.content_type}
                        </Badge>
                        <span className="text-xs text-muted-foreground">
                          {capture.chunks_created} chunks
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
