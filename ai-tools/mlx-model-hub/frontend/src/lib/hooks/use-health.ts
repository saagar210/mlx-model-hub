"use client"

import { useQuery } from "@tanstack/react-query"
import { getHealth, getMetrics } from "@/lib/api"

export const healthKeys = {
  all: ["health"] as const,
  status: () => [...healthKeys.all, "status"] as const,
  metrics: () => [...healthKeys.all, "metrics"] as const,
}

export function useHealth() {
  return useQuery({
    queryKey: healthKeys.status(),
    queryFn: getHealth,
    refetchInterval: 30000, // Poll every 30 seconds
  })
}

export function useMetrics() {
  return useQuery({
    queryKey: healthKeys.metrics(),
    queryFn: getMetrics,
    refetchInterval: 5000, // Poll every 5 seconds for live metrics
  })
}
