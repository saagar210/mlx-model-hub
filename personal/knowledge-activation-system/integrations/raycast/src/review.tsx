import { Action, ActionPanel, Detail, getPreferenceValues, openExtensionPreferences } from "@raycast/api";
import { useFetch } from "@raycast/utils";

interface Preferences {
  apiUrl: string;
}

interface ReviewCountResponse {
  due: number;
  text: string;
}

export default function ReviewDue() {
  const { apiUrl } = getPreferenceValues<Preferences>();

  const { isLoading, data, error } = useFetch<ReviewCountResponse>(
    `${apiUrl}/shortcuts/review-count`
  );

  const markdown = data
    ? `
# Review Queue

## ${data.due} items due for review

${data.due > 0 ? "Open KAS web app to start reviewing." : "All caught up!"}

---

*Check back later for more review items.*
`
    : error
    ? `# Error\n\nFailed to load review count: ${error.message}`
    : "Loading...";

  return (
    <Detail
      isLoading={isLoading}
      markdown={markdown}
      actions={
        <ActionPanel>
          <Action.OpenInBrowser
            title="Open Review Page"
            url={`${apiUrl.replace(":8000", ":3000")}/review`}
          />
          <Action
            title="Open Extension Preferences"
            onAction={openExtensionPreferences}
          />
        </ActionPanel>
      }
    />
  );
}
