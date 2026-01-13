import {
  App,
  Editor,
  MarkdownView,
  Modal,
  Notice,
  Plugin,
  PluginSettingTab,
  Setting,
  TFile,
  debounce,
} from "obsidian";

// ============================================================
// Types
// ============================================================

interface KnowledgeEngineSettings {
  apiUrl: string;
  apiKey: string;
  namespace: string;
  autoSync: boolean;
  syncInterval: number;
  includeFolders: string[];
  excludeFolders: string[];
  syncOnSave: boolean;
  showSearchInRibbon: boolean;
}

const DEFAULT_SETTINGS: KnowledgeEngineSettings = {
  apiUrl: "http://localhost:8000",
  apiKey: "",
  namespace: "obsidian",
  autoSync: true,
  syncInterval: 30,
  includeFolders: [],
  excludeFolders: [".obsidian", ".trash"],
  syncOnSave: true,
  showSearchInRibbon: true,
};

interface SearchResult {
  id: string;
  content: string;
  score: number;
  document_id: string;
  document_title?: string;
  metadata: Record<string, unknown>;
}

interface SearchResponse {
  query: string;
  results: SearchResult[];
  total_found: number;
  search_time_ms: number;
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
  constructor(private settings: KnowledgeEngineSettings) {}

  private async fetch<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.settings.apiUrl}${endpoint}`;
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };

    if (this.settings.apiKey) {
      headers["X-API-Key"] = this.settings.apiKey;
    }

    const response = await fetch(url, {
      ...options,
      headers: { ...headers, ...options.headers },
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }

    return response.json();
  }

  async search(query: string, limit = 10): Promise<SearchResponse> {
    return this.fetch<SearchResponse>("/v1/search", {
      method: "POST",
      body: JSON.stringify({
        query,
        namespace: this.settings.namespace,
        limit,
        search_type: "hybrid",
        include_content: true,
      }),
    });
  }

  async ingestNote(
    title: string,
    content: string,
    filePath: string
  ): Promise<IngestResponse> {
    return this.fetch<IngestResponse>("/v1/ingest/text", {
      method: "POST",
      body: JSON.stringify({
        title,
        content,
        namespace: this.settings.namespace,
        metadata: {
          source: "obsidian",
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
// Search Modal
// ============================================================

class SearchModal extends Modal {
  private results: SearchResult[] = [];
  private inputEl!: HTMLInputElement;
  private resultsEl!: HTMLElement;
  private api: KnowledgeEngineAPI;
  private onSelect: (result: SearchResult) => void;

  constructor(
    app: App,
    api: KnowledgeEngineAPI,
    onSelect: (result: SearchResult) => void
  ) {
    super(app);
    this.api = api;
    this.onSelect = onSelect;
  }

  onOpen(): void {
    const { contentEl } = this;
    contentEl.empty();
    contentEl.addClass("knowledge-engine-search-modal");

    // Search input
    const inputContainer = contentEl.createDiv("ke-search-input-container");
    this.inputEl = inputContainer.createEl("input", {
      type: "text",
      placeholder: "Search your knowledge base...",
      cls: "ke-search-input",
    });

    // Results container
    this.resultsEl = contentEl.createDiv("ke-search-results");
    this.resultsEl.createEl("p", {
      text: "Start typing to search",
      cls: "ke-search-hint",
    });

    // Event listeners
    const debouncedSearch = debounce(
      async (query: string) => {
        if (query.length < 2) {
          this.renderEmptyState();
          return;
        }

        try {
          this.renderLoading();
          const response = await this.api.search(query);
          this.results = response.results;
          this.renderResults(response);
        } catch (error) {
          this.renderError(error instanceof Error ? error.message : "Search failed");
        }
      },
      300,
      true
    );

    this.inputEl.addEventListener("input", (e) => {
      const query = (e.target as HTMLInputElement).value;
      debouncedSearch(query);
    });

    this.inputEl.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && this.results.length > 0) {
        this.selectResult(this.results[0]!);
      }
    });

    this.inputEl.focus();
  }

  private renderEmptyState(): void {
    this.resultsEl.empty();
    this.resultsEl.createEl("p", {
      text: "Start typing to search",
      cls: "ke-search-hint",
    });
  }

  private renderLoading(): void {
    this.resultsEl.empty();
    this.resultsEl.createEl("p", {
      text: "Searching...",
      cls: "ke-search-loading",
    });
  }

  private renderError(message: string): void {
    this.resultsEl.empty();
    this.resultsEl.createEl("p", {
      text: `Error: ${message}`,
      cls: "ke-search-error",
    });
  }

  private renderResults(response: SearchResponse): void {
    this.resultsEl.empty();

    if (response.results.length === 0) {
      this.resultsEl.createEl("p", {
        text: "No results found",
        cls: "ke-search-no-results",
      });
      return;
    }

    // Results header
    const header = this.resultsEl.createDiv("ke-results-header");
    header.createEl("span", {
      text: `${response.total_found} results (${response.search_time_ms.toFixed(0)}ms)`,
    });

    // Results list
    for (const result of response.results) {
      const item = this.resultsEl.createDiv("ke-result-item");
      item.addEventListener("click", () => this.selectResult(result));

      item.createEl("div", {
        text: result.document_title || "Untitled",
        cls: "ke-result-title",
      });

      item.createEl("div", {
        text: result.content.substring(0, 150) + "...",
        cls: "ke-result-content",
      });

      item.createEl("div", {
        text: `${Math.round(result.score * 100)}% match`,
        cls: "ke-result-score",
      });
    }
  }

  private selectResult(result: SearchResult): void {
    this.onSelect(result);
    this.close();
  }

  onClose(): void {
    this.contentEl.empty();
  }
}

// ============================================================
// Settings Tab
// ============================================================

class KnowledgeEngineSettingTab extends PluginSettingTab {
  plugin: KnowledgeEnginePlugin;

  constructor(app: App, plugin: KnowledgeEnginePlugin) {
    super(app, plugin);
    this.plugin = plugin;
  }

  display(): void {
    const { containerEl } = this;
    containerEl.empty();

    containerEl.createEl("h2", { text: "Knowledge Engine Settings" });

    // Connection settings
    containerEl.createEl("h3", { text: "Connection" });

    new Setting(containerEl)
      .setName("API URL")
      .setDesc("URL of your Knowledge Engine API server")
      .addText((text) =>
        text
          .setPlaceholder("http://localhost:8000")
          .setValue(this.plugin.settings.apiUrl)
          .onChange(async (value) => {
            this.plugin.settings.apiUrl = value;
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName("API Key")
      .setDesc("Optional API key for authentication")
      .addText((text) =>
        text
          .setPlaceholder("Enter API key")
          .setValue(this.plugin.settings.apiKey)
          .onChange(async (value) => {
            this.plugin.settings.apiKey = value;
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName("Namespace")
      .setDesc("Namespace for your Obsidian notes")
      .addText((text) =>
        text
          .setPlaceholder("obsidian")
          .setValue(this.plugin.settings.namespace)
          .onChange(async (value) => {
            this.plugin.settings.namespace = value;
            await this.plugin.saveSettings();
          })
      );

    // Sync settings
    containerEl.createEl("h3", { text: "Sync" });

    new Setting(containerEl)
      .setName("Auto sync")
      .setDesc("Automatically sync notes to Knowledge Engine")
      .addToggle((toggle) =>
        toggle
          .setValue(this.plugin.settings.autoSync)
          .onChange(async (value) => {
            this.plugin.settings.autoSync = value;
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName("Sync on save")
      .setDesc("Sync note when saving")
      .addToggle((toggle) =>
        toggle
          .setValue(this.plugin.settings.syncOnSave)
          .onChange(async (value) => {
            this.plugin.settings.syncOnSave = value;
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName("Sync interval")
      .setDesc("Minutes between automatic syncs")
      .addSlider((slider) =>
        slider
          .setLimits(5, 120, 5)
          .setValue(this.plugin.settings.syncInterval)
          .setDynamicTooltip()
          .onChange(async (value) => {
            this.plugin.settings.syncInterval = value;
            await this.plugin.saveSettings();
          })
      );

    // Test connection button
    new Setting(containerEl)
      .setName("Test connection")
      .setDesc("Test the connection to Knowledge Engine")
      .addButton((button) =>
        button.setButtonText("Test").onClick(async () => {
          button.setButtonText("Testing...");
          const healthy = await this.plugin.api.checkHealth();
          button.setButtonText(healthy ? "Connected!" : "Failed");
          setTimeout(() => button.setButtonText("Test"), 2000);
        })
      );
  }
}

// ============================================================
// Main Plugin
// ============================================================

export default class KnowledgeEnginePlugin extends Plugin {
  settings!: KnowledgeEngineSettings;
  api!: KnowledgeEngineAPI;
  private syncInterval: number | null = null;

  async onload(): Promise<void> {
    await this.loadSettings();
    this.api = new KnowledgeEngineAPI(this.settings);

    // Add ribbon icon for search
    if (this.settings.showSearchInRibbon) {
      this.addRibbonIcon("search", "Knowledge Engine Search", () => {
        this.openSearchModal();
      });
    }

    // Add commands
    this.addCommand({
      id: "ke-search",
      name: "Search Knowledge Engine",
      callback: () => this.openSearchModal(),
      hotkeys: [{ modifiers: ["Mod", "Shift"], key: "k" }],
    });

    this.addCommand({
      id: "ke-sync-current",
      name: "Sync current note",
      editorCallback: async (editor: Editor, view: MarkdownView) => {
        const file = view.file;
        if (file) {
          await this.syncFile(file);
        }
      },
    });

    this.addCommand({
      id: "ke-sync-all",
      name: "Sync all notes",
      callback: async () => {
        await this.syncAllNotes();
      },
    });

    // Register event for sync on save
    this.registerEvent(
      this.app.vault.on("modify", async (file) => {
        if (
          this.settings.syncOnSave &&
          file instanceof TFile &&
          file.extension === "md"
        ) {
          await this.syncFile(file);
        }
      })
    );

    // Start auto sync if enabled
    if (this.settings.autoSync) {
      this.startAutoSync();
    }

    // Add settings tab
    this.addSettingTab(new KnowledgeEngineSettingTab(this.app, this));

    console.log("Knowledge Engine plugin loaded");
  }

  onunload(): void {
    this.stopAutoSync();
    console.log("Knowledge Engine plugin unloaded");
  }

  async loadSettings(): Promise<void> {
    this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
  }

  async saveSettings(): Promise<void> {
    await this.saveData(this.settings);
    this.api = new KnowledgeEngineAPI(this.settings);

    if (this.settings.autoSync) {
      this.startAutoSync();
    } else {
      this.stopAutoSync();
    }
  }

  private openSearchModal(): void {
    new SearchModal(this.app, this.api, (result) => {
      const activeView = this.app.workspace.getActiveViewOfType(MarkdownView);
      if (activeView) {
        const editor = activeView.editor;
        const link = `[[${result.document_title || result.id}]]`;
        editor.replaceSelection(link);
      }
      new Notice(`Selected: ${result.document_title || result.id}`);
    }).open();
  }

  private async syncFile(file: TFile): Promise<void> {
    if (!this.shouldSyncFile(file)) {
      return;
    }

    try {
      const content = await this.app.vault.read(file);
      await this.api.ingestNote(file.basename, content, file.path);
      new Notice(`Synced: ${file.basename}`);
    } catch (error) {
      console.error("Sync failed:", error);
      new Notice(`Sync failed: ${file.basename}`);
    }
  }

  private shouldSyncFile(file: TFile): boolean {
    for (const folder of this.settings.excludeFolders) {
      if (file.path.startsWith(folder)) {
        return false;
      }
    }

    if (this.settings.includeFolders.length > 0) {
      return this.settings.includeFolders.some((folder) =>
        file.path.startsWith(folder)
      );
    }

    return true;
  }

  private async syncAllNotes(): Promise<void> {
    const files = this.app.vault.getMarkdownFiles();
    const toSync = files.filter((f) => this.shouldSyncFile(f));

    new Notice(`Syncing ${toSync.length} notes...`);

    let synced = 0;
    let failed = 0;

    for (const file of toSync) {
      try {
        const content = await this.app.vault.read(file);
        await this.api.ingestNote(file.basename, content, file.path);
        synced++;
      } catch {
        failed++;
      }
    }

    new Notice(`Sync complete: ${synced} synced, ${failed} failed`);
  }

  private startAutoSync(): void {
    this.stopAutoSync();
    const intervalMs = this.settings.syncInterval * 60 * 1000;
    this.syncInterval = window.setInterval(
      () => this.syncAllNotes(),
      intervalMs
    );
  }

  private stopAutoSync(): void {
    if (this.syncInterval) {
      window.clearInterval(this.syncInterval);
      this.syncInterval = null;
    }
  }
}
