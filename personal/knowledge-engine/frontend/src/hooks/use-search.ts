"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { hybridSearch, vectorSearch, search } from "@/lib/api";
import type { SearchRequest, SearchResponse } from "@/types/api";

/**
 * Hook for performing hybrid search with mutation pattern.
 * Use this when search is triggered by user action.
 */
export function useHybridSearch() {
  return useMutation<SearchResponse, Error, string>({
    mutationFn: (query: string) => hybridSearch(query),
    mutationKey: ["search", "hybrid"],
  });
}

/**
 * Hook for performing vector-only search.
 */
export function useVectorSearch() {
  return useMutation<SearchResponse, Error, string>({
    mutationFn: (query: string) => vectorSearch(query),
    mutationKey: ["search", "vector"],
  });
}

/**
 * Hook for performing search with custom options.
 */
export function useSearch() {
  return useMutation<SearchResponse, Error, SearchRequest>({
    mutationFn: (request: SearchRequest) => search(request),
    mutationKey: ["search", "custom"],
  });
}

/**
 * Hook for search with automatic refetch (query pattern).
 * Use this when you want search results to persist and update automatically.
 */
export function useSearchQuery(
  query: string | null,
  options?: Partial<SearchRequest>
) {
  return useQuery({
    queryKey: ["search", query, options] as const,
    queryFn: () =>
      query
        ? search({
            query,
            search_type: "hybrid",
            limit: 10,
            include_content: true,
            ...options,
          })
        : Promise.resolve(null),
    enabled: !!query,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}
