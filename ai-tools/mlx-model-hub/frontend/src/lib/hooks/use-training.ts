"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  cancelTrainingJob,
  createTrainingJob,
  getTrainingJob,
  getTrainingJobs,
  TrainingConfig,
} from "@/lib/api"

export const trainingKeys = {
  all: ["training"] as const,
  lists: () => [...trainingKeys.all, "list"] as const,
  list: (filters: { page?: number; status?: string }) =>
    [...trainingKeys.lists(), filters] as const,
  details: () => [...trainingKeys.all, "detail"] as const,
  detail: (id: string) => [...trainingKeys.details(), id] as const,
}

export function useTrainingJobs(page = 1, pageSize = 20, status?: string) {
  return useQuery({
    queryKey: trainingKeys.list({ page, status }),
    queryFn: () => getTrainingJobs(page, pageSize, status),
  })
}

export function useTrainingJob(id: string) {
  return useQuery({
    queryKey: trainingKeys.detail(id),
    queryFn: () => getTrainingJob(id),
    enabled: !!id,
    refetchInterval: (query) => {
      // Poll every 2s for running jobs
      const data = query.state.data
      if (data?.status === "running" || data?.status === "pending") {
        return 2000
      }
      return false
    },
  })
}

export function useCreateTrainingJob() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (config: TrainingConfig) => createTrainingJob(config),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: trainingKeys.lists() })
    },
  })
}

export function useCancelTrainingJob() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => cancelTrainingJob(id),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: trainingKeys.lists() })
      queryClient.setQueryData(trainingKeys.detail(data.id), data)
    },
  })
}
