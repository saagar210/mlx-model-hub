import { Detail, getPreferenceValues } from "@raycast/api";
import { useFetch } from "@raycast/utils";

interface Preferences {
  apiUrl: string;
}

interface StatsResponse {
  documents: number;
  chunks: number;
  review_due: number;
}

export default function KnowledgeStats() {
  const { apiUrl } = getPreferenceValues<Preferences>();

  const { isLoading, data, error } = useFetch<StatsResponse>(
    `${apiUrl}/shortcuts/stats`
  );

  const markdown = data
    ? `
# Knowledge Base Statistics

| Metric | Count |
|--------|-------|
| Documents | **${data.documents.toLocaleString()}** |
| Chunks | **${data.chunks.toLocaleString()}** |
| Due for Review | **${data.review_due.toLocaleString()}** |

---

*Last updated: ${new Date().toLocaleString()}*
`
    : error
    ? `# Error\n\nFailed to load stats: ${error.message}`
    : "Loading...";

  return <Detail isLoading={isLoading} markdown={markdown} />;
}
