import {
  Action,
  ActionPanel,
  Form,
  getPreferenceValues,
  showToast,
  Toast,
  popToRoot,
} from "@raycast/api";
import { useState } from "react";

interface Preferences {
  apiUrl: string;
}

interface CaptureResponse {
  success: boolean;
  message: string;
  content_id?: string;
}

export default function QuickCapture() {
  const [isLoading, setIsLoading] = useState(false);
  const { apiUrl } = getPreferenceValues<Preferences>();

  async function handleSubmit(values: { text: string; title?: string; tags?: string }) {
    if (!values.text.trim()) {
      showToast({
        style: Toast.Style.Failure,
        title: "Text required",
        message: "Please enter some text to capture",
      });
      return;
    }

    setIsLoading(true);

    try {
      const params = new URLSearchParams({
        text: values.text,
        ...(values.title && { title: values.title }),
        ...(values.tags && { tags: values.tags }),
      });

      const response = await fetch(`${apiUrl}/shortcuts/capture?${params}`, {
        method: "POST",
      });

      const data: CaptureResponse = await response.json();

      if (data.success) {
        showToast({
          style: Toast.Style.Success,
          title: "Captured!",
          message: data.message,
        });
        popToRoot();
      } else {
        throw new Error(data.message || "Capture failed");
      }
    } catch (error) {
      showToast({
        style: Toast.Style.Failure,
        title: "Capture failed",
        message: error instanceof Error ? error.message : "Unknown error",
      });
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <Form
      isLoading={isLoading}
      actions={
        <ActionPanel>
          <Action.SubmitForm title="Capture" onSubmit={handleSubmit} />
        </ActionPanel>
      }
    >
      <Form.TextArea
        id="text"
        title="Content"
        placeholder="Enter text to capture..."
        autoFocus
      />
      <Form.TextField
        id="title"
        title="Title"
        placeholder="Optional title (auto-generated if empty)"
      />
      <Form.TextField
        id="tags"
        title="Tags"
        placeholder="Comma-separated tags (optional)"
      />
    </Form>
  );
}
