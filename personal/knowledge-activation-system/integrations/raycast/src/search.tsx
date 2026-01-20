import { Action, ActionPanel, List, getPreferenceValues, showToast, Toast } from "@raycast/api";
import { useFetch } from "@raycast/utils";
import { useState } from "react";

interface Preferences {
  apiUrl: string;
}

interface SearchResult {
  content_id: string;
  title: string;
  content_type: string;
  chunk_text: string;
  score: number;
  namespace?: string;
}

interface SearchResponse {
  results: SearchResult[];
  total_count: number;
  query: string;
}

export default function SearchKnowledge() {
  const [searchText, setSearchText] = useState("");
  const { apiUrl } = getPreferenceValues<Preferences>();

  const { isLoading, data, error } = useFetch<SearchResponse>(
    `${apiUrl}/api/v1/search?q=${encodeURIComponent(searchText)}&limit=10`,
    {
      execute: searchText.length > 2,
      keepPreviousData: true,
      onError: (error) => {
        showToast({
          style: Toast.Style.Failure,
          title: "Search failed",
          message: error.message,
        });
      },
    }
  );

  return (
    <List
      isLoading={isLoading}
      searchBarPlaceholder="Search your knowledge base..."
      onSearchTextChange={setSearchText}
      throttle
    >
      {data?.results?.map((result) => (
        <List.Item
          key={result.content_id}
          title={result.title}
          subtitle={result.namespace || result.content_type}
          accessories={[{ text: `${(result.score * 100).toFixed(0)}%` }]}
          actions={
            <ActionPanel>
              <Action.CopyToClipboard
                title="Copy Text"
                content={result.chunk_text}
              />
              <Action.OpenInBrowser
                title="Open in KAS"
                url={`${apiUrl}/content/${result.content_id}`}
              />
            </ActionPanel>
          }
          detail={
            <List.Item.Detail
              markdown={`## ${result.title}\n\n${result.chunk_text}`}
            />
          }
        />
      ))}
      {searchText.length > 2 && data?.results?.length === 0 && (
        <List.EmptyView
          title="No Results"
          description={`No results found for "${searchText}"`}
        />
      )}
      {searchText.length <= 2 && (
        <List.EmptyView
          title="Search Knowledge"
          description="Type at least 3 characters to search"
        />
      )}
    </List>
  );
}
