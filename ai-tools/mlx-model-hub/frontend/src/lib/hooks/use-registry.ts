"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  getRegistryStatus,
  getModelStatus,
  unregisterModel,
  preloadModel,
  scanExportsDirectory,
  getAdminHealth,
} from "@/lib/api"

export const registryKeys = {
  all: ["registry"] as const,
  status: (registeredBy?: string) => [...registryKeys.all, "status", registeredBy] as const,
  modelStatus: (name: string) => [...registryKeys.all, "model", name] as const,
  health: () => [...registryKeys.all, "health"] as const,
}

export function useRegistryStatus(registeredBy?: string) {
  return useQuery({
    queryKey: registryKeys.status(registeredBy),
    queryFn: () => getRegistryStatus(registeredBy),
    refetchInterval: 10000, // Refresh every 10 seconds
  })
}

export function useModelStatus(name?: string) {
  return useQuery({
    queryKey: registryKeys.modelStatus(name!),
    queryFn: () => getModelStatus(name!),
    enabled: !!name,
    refetchInterval: 5000, // Faster refresh for individual model status
  })
}

export function useAdminHealth() {
  return useQuery({
    queryKey: registryKeys.health(),
    queryFn: () => getAdminHealth(),
    refetchInterval: 30000, // Refresh every 30 seconds
  })
}

export function useUnregisterModel() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (name: string) => unregisterModel(name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: registryKeys.status() })
      queryClient.invalidateQueries({ queryKey: registryKeys.health() })
    },
  })
}

export function usePreloadModel() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (name: string) => preloadModel(name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: registryKeys.status() })
    },
  })
}

export function useScanExports() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => scanExportsDirectory(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: registryKeys.status() })
      queryClient.invalidateQueries({ queryKey: registryKeys.health() })
    },
  })
}
