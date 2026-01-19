"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
  Network,
  Search,
  Loader2,
  Database,
  GitBranch,
  Tag,
  FileText,
  ExternalLink,
} from "lucide-react";
import {
  getEntityStats,
  getConnectedEntities,
  searchContentByEntity,
  type EntityStats,
  type ConnectedEntity,
  type ContentByEntity,
} from "@/lib/api";
import Link from "next/link";

// Entity type color mapping
const TYPE_COLORS: Record<string, string> = {
  technology: "bg-blue-100 text-blue-800",
  concept: "bg-purple-100 text-purple-800",
  tool: "bg-green-100 text-green-800",
  framework: "bg-orange-100 text-orange-800",
  organization: "bg-yellow-100 text-yellow-800",
  person: "bg-pink-100 text-pink-800",
  protocol: "bg-cyan-100 text-cyan-800",
};

export default function GraphPage() {
  const [stats, setStats] = useState<EntityStats[]>([]);
  const [connected, setConnected] = useState<ConnectedEntity[]>([]);
  const [searchResults, setSearchResults] = useState<ContentByEntity[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    const loadData = async () => {
      try {
        const [statsData, connectedData] = await Promise.all([
          getEntityStats(),
          getConnectedEntities(30),
        ]);
        setStats(statsData);
        setConnected(connectedData);
      } catch (error) {
        console.error("Failed to load graph data:", error);
        toast.error("Failed to load knowledge graph data");
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;

    setSearching(true);
    try {
      const results = await searchContentByEntity(searchQuery, 20);
      setSearchResults(results);
      if (results.length === 0) {
        toast.info(`No content found containing "${searchQuery}"`);
      }
    } catch (error) {
      console.error("Search failed:", error);
      toast.error("Failed to search entities");
    } finally {
      setSearching(false);
    }
  };

  const totalEntities = stats.reduce((acc, s) => acc + s.count, 0);
  const uniqueEntities = stats.reduce((acc, s) => acc + s.unique_names, 0);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center gap-2 mb-6">
        <Network className="h-8 w-8" />
        <div>
          <h1 className="text-3xl font-bold">Knowledge Graph</h1>
          <p className="text-muted-foreground">
            Explore entities and their relationships across your knowledge base
          </p>
        </div>
      </div>

      {/* Stats Overview */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Entities</CardTitle>
            <Database className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalEntities}</div>
            <p className="text-xs text-muted-foreground">
              {uniqueEntities} unique names
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Entity Types</CardTitle>
            <Tag className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.length}</div>
            <p className="text-xs text-muted-foreground">
              categories extracted
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Most Connected</CardTitle>
            <GitBranch className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {connected[0]?.name || "N/A"}
            </div>
            <p className="text-xs text-muted-foreground">
              {connected[0]?.connection_count || 0} connections
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Top Type</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold capitalize">
              {stats[0]?.entity_type || "N/A"}
            </div>
            <p className="text-xs text-muted-foreground">
              {stats[0]?.count || 0} entities
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Entity Search */}
      <Card>
        <CardHeader>
          <CardTitle>Search by Entity</CardTitle>
          <CardDescription>
            Find content containing specific entities
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <Input
              placeholder="Search for an entity (e.g., Python, RAG, FastAPI)..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              className="flex-1"
            />
            <Button onClick={handleSearch} disabled={searching}>
              {searching ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Search className="h-4 w-4" />
              )}
              <span className="ml-2">Search</span>
            </Button>
          </div>

          {searchResults.length > 0 && (
            <div className="mt-4 space-y-3">
              <h3 className="font-medium">
                Found {searchResults.length} content items
              </h3>
              {searchResults.map((result) => (
                <div
                  key={result.content_id}
                  className="border rounded-lg p-4 hover:bg-muted/50 transition-colors"
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <Link
                        href={`/content/${result.content_id}`}
                        className="font-medium hover:underline flex items-center gap-1"
                      >
                        {result.title}
                        <ExternalLink className="h-3 w-3" />
                      </Link>
                      <p className="text-sm text-muted-foreground">
                        {result.content_type} - {result.entity_count} entities
                      </p>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-1 mt-2">
                    {result.entities.slice(0, 10).map((entity) => (
                      <Badge
                        key={entity.id}
                        variant="secondary"
                        className={TYPE_COLORS[entity.entity_type] || ""}
                        onClick={() => {
                          setSearchQuery(entity.name);
                          handleSearch();
                        }}
                        style={{ cursor: "pointer" }}
                      >
                        {entity.name}
                      </Badge>
                    ))}
                    {result.entities.length > 10 && (
                      <Badge variant="outline">
                        +{result.entities.length - 10} more
                      </Badge>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-6 md:grid-cols-2">
        {/* Entity Types Distribution */}
        <Card>
          <CardHeader>
            <CardTitle>Entity Types</CardTitle>
            <CardDescription>
              Distribution of entities by type
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {stats.map((stat) => (
                <div key={stat.entity_type} className="flex items-center gap-3">
                  <Badge
                    className={TYPE_COLORS[stat.entity_type] || "bg-gray-100 text-gray-800"}
                  >
                    {stat.entity_type}
                  </Badge>
                  <div className="flex-1 bg-muted rounded-full h-2 overflow-hidden">
                    <div
                      className="bg-primary h-full transition-all"
                      style={{
                        width: `${(stat.count / totalEntities) * 100}%`,
                      }}
                    />
                  </div>
                  <span className="text-sm text-muted-foreground w-16 text-right">
                    {stat.count} ({stat.unique_names})
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Most Connected Entities */}
        <Card>
          <CardHeader>
            <CardTitle>Most Connected</CardTitle>
            <CardDescription>
              Entities with the most relationships
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {connected.slice(0, 15).map((entity, idx) => (
                <div
                  key={`${entity.name}-${idx}`}
                  className="flex items-center justify-between py-1 hover:bg-muted/50 px-2 rounded cursor-pointer"
                  onClick={() => {
                    setSearchQuery(entity.name);
                    handleSearch();
                  }}
                >
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground w-6">
                      {idx + 1}.
                    </span>
                    <span className="font-medium">{entity.name}</span>
                    <Badge
                      variant="outline"
                      className={TYPE_COLORS[entity.entity_type] || ""}
                    >
                      {entity.entity_type}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-1 text-sm text-muted-foreground">
                    <GitBranch className="h-3 w-3" />
                    {entity.connection_count}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
