import * as vscode from "vscode";

// ============================================================
// Types
// ============================================================

interface SearchResult {
  id: string;
  content: string;
  score: number;
  document_id: string;
  document_title?: string;
  source_url?: string;
}

interface SearchResponse {
  query: string;
  results: SearchResult[];
  total_found: number;
  search_time_ms: number;
}

interface QueryResponse {
  query: string;
  answer: string;
  confidence: number;
  sources: Array<{
    document_id: string;
    document_title: string;
    relevance_score: number;
  }>;
  query_time_ms: number;
}

interface IngestResponse {
  document_id: string;
  title: string;
  chunk_count: number;
  status: string;
}

// ============================================================
// API Client
// ============================================================

class KnowledgeEngineAPI {
  private getConfig() {
    const config = vscode.workspace.getConfiguration("knowledgeEngine");
    return {
      apiUrl: config.get<string>("apiUrl") || "http://localhost:8000",
      apiKey: config.get<string>("apiKey") || "",
      namespace: config.get<string>("namespace") || "vscode",
      maxResults: config.get<number>("maxResults") || 10,
    };
  }

  private async fetch<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const config = this.getConfig();
    const url = `${config.apiUrl}${endpoint}`;

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };

    if (config.apiKey) {
      headers["X-API-Key"] = config.apiKey;
    }

    const response = await fetch(url, {
      ...options,
      headers: { ...headers, ...options.headers },
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }

    return response.json() as Promise<T>;
  }

  async search(query: string): Promise<SearchResponse> {
    const config = this.getConfig();
    return this.fetch<SearchResponse>("/v1/search", {
      method: "POST",
      body: JSON.stringify({
        query,
        namespace: config.namespace,
        limit: config.maxResults,
        search_type: "hybrid",
        include_content: true,
      }),
    });
  }

  async ask(question: string): Promise<QueryResponse> {
    const config = this.getConfig();
    return this.fetch<QueryResponse>("/v1/query", {
      method: "POST",
      body: JSON.stringify({
        query: question,
        namespace: config.namespace,
        max_context_chunks: 5,
        include_sources: true,
      }),
    });
  }

  async ingest(title: string, content: string, filePath?: string): Promise<IngestResponse> {
    const config = this.getConfig();
    return this.fetch<IngestResponse>("/v1/ingest/text", {
      method: "POST",
      body: JSON.stringify({
        title,
        content,
        namespace: config.namespace,
        metadata: {
          source: "vscode",
          file_path: filePath,
        },
      }),
    });
  }

  async checkHealth(): Promise<boolean> {
    try {
      const response = await this.fetch<{ status: string }>("/health");
      return response.status === "healthy";
    } catch {
      return false;
    }
  }
}

// ============================================================
// Quick Pick Items
// ============================================================

class SearchResultItem implements vscode.QuickPickItem {
  label: string;
  description?: string;
  detail?: string;

  constructor(public result: SearchResult) {
    this.label = result.document_title || "Untitled";
    this.description = `${Math.round(result.score * 100)}% match`;
    this.detail = result.content.substring(0, 100) + "...";
  }
}

// ============================================================
// Extension Activation
// ============================================================

export function activate(context: vscode.ExtensionContext): void {
  const api = new KnowledgeEngineAPI();

  // Search command
  const searchCommand = vscode.commands.registerCommand(
    "knowledgeEngine.search",
    async () => {
      const query = await vscode.window.showInputBox({
        prompt: "Search your knowledge base",
        placeHolder: "Enter search query...",
      });

      if (!query) {
        return;
      }

      await vscode.window.withProgress(
        {
          location: vscode.ProgressLocation.Notification,
          title: "Searching...",
          cancellable: false,
        },
        async () => {
          try {
            const response = await api.search(query);

            if (response.results.length === 0) {
              vscode.window.showInformationMessage("No results found");
              return;
            }

            const items = response.results.map((r) => new SearchResultItem(r));
            const selected = await vscode.window.showQuickPick(items, {
              placeHolder: `${response.total_found} results (${response.search_time_ms.toFixed(0)}ms)`,
              matchOnDescription: true,
              matchOnDetail: true,
            });

            if (selected) {
              // Show full content in a new document
              const doc = await vscode.workspace.openTextDocument({
                content: formatSearchResult(selected.result),
                language: "markdown",
              });
              await vscode.window.showTextDocument(doc, { preview: true });
            }
          } catch (error) {
            vscode.window.showErrorMessage(
              `Search failed: ${error instanceof Error ? error.message : "Unknown error"}`
            );
          }
        }
      );
    }
  );

  // Ask command
  const askCommand = vscode.commands.registerCommand(
    "knowledgeEngine.ask",
    async () => {
      const question = await vscode.window.showInputBox({
        prompt: "Ask a question",
        placeHolder: "What would you like to know?",
      });

      if (!question) {
        return;
      }

      await vscode.window.withProgress(
        {
          location: vscode.ProgressLocation.Notification,
          title: "Thinking...",
          cancellable: false,
        },
        async () => {
          try {
            const response = await api.ask(question);

            // Show answer in a new document
            const doc = await vscode.workspace.openTextDocument({
              content: formatQueryResponse(question, response),
              language: "markdown",
            });
            await vscode.window.showTextDocument(doc, { preview: true });
          } catch (error) {
            vscode.window.showErrorMessage(
              `Query failed: ${error instanceof Error ? error.message : "Unknown error"}`
            );
          }
        }
      );
    }
  );

  // Ingest selection command
  const ingestSelectionCommand = vscode.commands.registerCommand(
    "knowledgeEngine.ingestSelection",
    async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) {
        vscode.window.showWarningMessage("No active editor");
        return;
      }

      const selection = editor.selection;
      const text = editor.document.getText(selection);

      if (!text) {
        vscode.window.showWarningMessage("No text selected");
        return;
      }

      const title = await vscode.window.showInputBox({
        prompt: "Enter a title for this content",
        placeHolder: "e.g., Code snippet from MyFile.ts",
        value: `Selection from ${editor.document.fileName.split("/").pop()}`,
      });

      if (!title) {
        return;
      }

      try {
        const response = await api.ingest(
          title,
          text,
          editor.document.fileName
        );
        vscode.window.showInformationMessage(
          `Saved: ${response.title} (${response.chunk_count} chunks)`
        );
      } catch (error) {
        vscode.window.showErrorMessage(
          `Failed to save: ${error instanceof Error ? error.message : "Unknown error"}`
        );
      }
    }
  );

  // Ingest file command
  const ingestFileCommand = vscode.commands.registerCommand(
    "knowledgeEngine.ingestFile",
    async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) {
        vscode.window.showWarningMessage("No active editor");
        return;
      }

      const fileName = editor.document.fileName.split("/").pop() || "Untitled";
      const content = editor.document.getText();

      try {
        const response = await api.ingest(
          fileName,
          content,
          editor.document.fileName
        );
        vscode.window.showInformationMessage(
          `Saved: ${response.title} (${response.chunk_count} chunks)`
        );
      } catch (error) {
        vscode.window.showErrorMessage(
          `Failed to save: ${error instanceof Error ? error.message : "Unknown error"}`
        );
      }
    }
  );

  // Register all commands
  context.subscriptions.push(
    searchCommand,
    askCommand,
    ingestSelectionCommand,
    ingestFileCommand
  );

  // Status bar item
  const statusBar = vscode.window.createStatusBarItem(
    vscode.StatusBarAlignment.Right,
    100
  );
  statusBar.text = "$(database) KE";
  statusBar.tooltip = "Knowledge Engine";
  statusBar.command = "knowledgeEngine.search";
  statusBar.show();
  context.subscriptions.push(statusBar);

  // Check connection on startup
  api.checkHealth().then((healthy) => {
    if (healthy) {
      statusBar.text = "$(database) KE";
      statusBar.tooltip = "Knowledge Engine: Connected";
    } else {
      statusBar.text = "$(database) KE $(warning)";
      statusBar.tooltip = "Knowledge Engine: Not connected";
    }
  });

  console.log("Knowledge Engine extension activated");
}

export function deactivate(): void {
  console.log("Knowledge Engine extension deactivated");
}

// ============================================================
// Formatting Helpers
// ============================================================

function formatSearchResult(result: SearchResult): string {
  const lines = [
    `# ${result.document_title || "Untitled"}`,
    "",
    `**Match:** ${Math.round(result.score * 100)}%`,
    "",
    "---",
    "",
    result.content,
    "",
    "---",
    "",
    `*Document ID: ${result.document_id}*`,
  ];

  if (result.source_url) {
    lines.push(`*Source: ${result.source_url}*`);
  }

  return lines.join("\n");
}

function formatQueryResponse(question: string, response: QueryResponse): string {
  const lines = [
    `# Question`,
    "",
    question,
    "",
    "# Answer",
    "",
    response.answer,
    "",
    `**Confidence:** ${Math.round(response.confidence * 100)}%`,
    `**Time:** ${response.query_time_ms.toFixed(0)}ms`,
    "",
  ];

  if (response.sources.length > 0) {
    lines.push("## Sources", "");
    for (const source of response.sources) {
      lines.push(
        `- ${source.document_title} (${Math.round(source.relevance_score * 100)}%)`
      );
    }
  }

  return lines.join("\n");
}
