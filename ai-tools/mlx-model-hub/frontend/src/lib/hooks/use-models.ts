"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  deleteModel,
  getModel,
  getModels,
} from "@/lib/api"

export const modelKeys = {
  all: ["models"] as const,
  lists: () => [...modelKeys.all, "list"] as const,
  list: (filters: { page?: number; status?: string }) =>
    [...modelKeys.lists(), filters] as const,
  details: () => [...modelKeys.all, "detail"] as const,
  detail: (id: string) => [...modelKeys.details(), id] as const,
}

export function useModels(page = 1, pageSize = 20, status?: string) {
  return useQuery({
    queryKey: modelKeys.list({ page, status }),
    queryFn: () => getModels(page, pageSize, status),
  })
}

export function useModel(id: string) {
  return useQuery({
    queryKey: modelKeys.detail(id),
    queryFn: () => getModel(id),
    enabled: !!id,
  })
}

export function useDeleteModel() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => deleteModel(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: modelKeys.lists() })
    },
  })
}
