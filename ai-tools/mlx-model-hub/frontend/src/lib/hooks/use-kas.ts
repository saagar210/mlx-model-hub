"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  getKASHealth,
  getKASStats,
  searchKAS,
  askKAS,
  KASSearchResponse,
  KASAskResponse,
} from "@/lib/api"

export const kasKeys = {
  all: ["kas"] as const,
  health: () => [...kasKeys.all, "health"] as const,
  stats: () => [...kasKeys.all, "stats"] as const,
  search: (query: string) => [...kasKeys.all, "search", query] as const,
  ask: (query: string) => [...kasKeys.all, "ask", query] as const,
}

/**
 * Hook to check KAS health status
 */
export function useKASHealth() {
  return useQuery({
    queryKey: kasKeys.health(),
    queryFn: getKASHealth,
    refetchInterval: 30000, // Refresh every 30 seconds
    staleTime: 10000, // Consider data stale after 10 seconds
  })
}

/**
 * Hook to get KAS statistics
 */
export function useKASStats() {
  return useQuery({
    queryKey: kasKeys.stats(),
    queryFn: getKASStats,
    refetchInterval: 60000, // Refresh every minute
    staleTime: 30000,
  })
}

/**
 * Hook to search KAS knowledge base
 * Returns cached results for repeated queries
 */
export function useKASSearch(query: string, limit = 10) {
  return useQuery({
    queryKey: kasKeys.search(query),
    queryFn: () => searchKAS(query, limit),
    enabled: query.length >= 2, // Only search with at least 2 characters
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
  })
}

/**
 * Hook for on-demand KAS search (mutation-style)
 * Use this for search triggered by user action
 */
export function useKASSearchMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ query, limit = 10 }: { query: string; limit?: number }) =>
      searchKAS(query, limit),
    onSuccess: (data, variables) => {
      // Cache the result for future queries
      queryClient.setQueryData(kasKeys.search(variables.query), data)
    },
  })
}

/**
 * Hook for Q&A with citations (mutation-style)
 * Use this for asking questions to KAS
 */
export function useKASAsk() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ query, limit = 10 }: { query: string; limit?: number }) =>
      askKAS(query, limit),
    onSuccess: (data, variables) => {
      // Cache the result
      queryClient.setQueryData(kasKeys.ask(variables.query), data)
    },
  })
}

/**
 * Prefetch search results (for anticipated queries)
 */
export function usePrefetchKASSearch() {
  const queryClient = useQueryClient()

  return (query: string, limit = 10) => {
    if (query.length >= 2) {
      queryClient.prefetchQuery({
        queryKey: kasKeys.search(query),
        queryFn: () => searchKAS(query, limit),
        staleTime: 5 * 60 * 1000,
      })
    }
  }
}
