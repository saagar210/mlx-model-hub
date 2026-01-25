"use client";

import { useMutation } from "@tanstack/react-query";
import { query, askQuestion, streamQuery } from "@/lib/api";
import type { QueryRequest, QueryResponse } from "@/types/api";

/**
 * Hook for RAG query with mutation pattern.
 */
export function useRAGQuery() {
  return useMutation<QueryResponse, Error, QueryRequest>({
    mutationFn: (request: QueryRequest) => query(request),
    mutationKey: ["query", "rag"],
  });
}

/**
 * Hook for simple question asking.
 */
export function useAskQuestion() {
  return useMutation<QueryResponse, Error, { question: string; namespace?: string }>({
    mutationFn: ({ question, namespace }) => askQuestion(question, namespace),
    mutationKey: ["query", "ask"],
  });
}

/**
 * Hook for streaming RAG responses.
 * Returns a mutation that handles the async generator.
 */
export function useStreamingQuery(
  onChunk: (chunk: string) => void,
  onComplete?: () => void
) {
  return useMutation<void, Error, QueryRequest>({
    mutationFn: async (request: QueryRequest) => {
      const stream = streamQuery({ ...request, stream: true });

      for await (const chunk of stream) {
        onChunk(chunk);
      }

      onComplete?.();
    },
    mutationKey: ["query", "stream"],
  });
}
