"use client";

import * as React from "react";
import { useMutation } from "@tanstack/react-query";
import { Brain, BookOpen, Zap, Database } from "lucide-react";

import { SearchBar } from "@/components/search/search-bar";
import { SearchResults } from "@/components/search/search-results";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { hybridSearch } from "@/lib/api";
import type { SearchResponse } from "@/types/api";

export default function HomePage() {
  const [searchResponse, setSearchResponse] = React.useState<SearchResponse | null>(null);

  const searchMutation = useMutation({
    mutationFn: (query: string) => hybridSearch(query, 10),
    onSuccess: (data) => {
      setSearchResponse(data);
    },
  });

  const handleSearch = (query: string) => {
    searchMutation.mutate(query);
  };

  const handleClear = () => {
    setSearchResponse(null);
  };

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container flex h-14 items-center">
          <div className="flex items-center gap-2">
            <Brain className="h-6 w-6 text-primary" />
            <span className="font-semibold text-lg">Knowledge Engine</span>
          </div>
          <nav className="ml-auto flex items-center gap-4 text-sm">
            <a href="/ingest" className="text-muted-foreground hover:text-primary transition-colors">
              Ingest
            </a>
            <a href="/memory" className="text-muted-foreground hover:text-primary transition-colors">
              Memory
            </a>
            <a href="/ask" className="text-muted-foreground hover:text-primary transition-colors">
              Ask
            </a>
          </nav>
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 container py-8">
        {/* Hero section with search */}
        <div className="max-w-3xl mx-auto">
          {!searchResponse && !searchMutation.isPending && (
            <div className="text-center mb-8">
              <h1 className="text-4xl font-bold tracking-tight mb-4">
                Search Your Knowledge
              </h1>
              <p className="text-lg text-muted-foreground">
                Semantic search powered by AI. Find what you need instantly.
              </p>
            </div>
          )}

          {/* Search bar */}
          <SearchBar
            onSearch={handleSearch}
            onClear={handleClear}
            isLoading={searchMutation.isPending}
            autoFocus={!searchResponse}
            className="mb-8"
          />

          {/* Search results */}
          <SearchResults
            response={searchResponse}
            isLoading={searchMutation.isPending}
            error={searchMutation.error}
          />

          {/* Feature cards (shown when no search) */}
          {!searchResponse && !searchMutation.isPending && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-12">
              <FeatureCard
                icon={<Zap className="h-5 w-5" />}
                title="Hybrid Search"
                description="Combines semantic vectors with keyword matching for best results."
              />
              <FeatureCard
                icon={<BookOpen className="h-5 w-5" />}
                title="Multi-Source"
                description="Ingest from URLs, YouTube, PDFs, and more."
              />
              <FeatureCard
                icon={<Brain className="h-5 w-5" />}
                title="AI-Powered Q&A"
                description="Ask questions and get answers with source citations."
              />
              <FeatureCard
                icon={<Database className="h-5 w-5" />}
                title="Persistent Memory"
                description="Store and recall facts, preferences, and context."
              />
            </div>
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t py-6">
        <div className="container flex flex-col sm:flex-row items-center justify-between gap-4 text-sm text-muted-foreground">
          <p>Knowledge Engine v0.1.0</p>
          <p>Built with Next.js 15 and FastAPI</p>
        </div>
      </footer>
    </div>
  );
}

interface FeatureCardProps {
  icon: React.ReactNode;
  title: string;
  description: string;
}

function FeatureCard({ icon, title, description }: FeatureCardProps) {
  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <div className="p-2 bg-primary/10 rounded-md text-primary">
            {icon}
          </div>
          <CardTitle className="text-lg">{title}</CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        <CardDescription>{description}</CardDescription>
      </CardContent>
    </Card>
  );
}
