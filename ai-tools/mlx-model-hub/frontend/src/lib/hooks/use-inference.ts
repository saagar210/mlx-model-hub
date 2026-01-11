"use client"

import { useMutation } from "@tanstack/react-query"
import { InferenceRequest, runInference } from "@/lib/api"

export function useInference() {
  return useMutation({
    mutationFn: (request: InferenceRequest) => runInference(request),
  })
}
