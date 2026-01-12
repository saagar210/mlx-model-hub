import { Page, Locator, expect } from "@playwright/test"
import { BasePage } from "./BasePage"

export class DiscoverPage extends BasePage {
  readonly searchInput: Locator
  readonly sortSelect: Locator
  readonly popularModels: Locator
  readonly recentModels: Locator
  readonly searchResults: Locator
  readonly downloadDialog: Locator

  constructor(page: Page) {
    super(page)
    this.searchInput = page.getByPlaceholder("Search MLX models...")
    this.sortSelect = page.getByRole("combobox")
    this.popularModels = page.locator("text=Popular Models").locator("..").locator("..")
    this.recentModels = page.locator("text=Recently Updated").locator("..").locator("..")
    this.searchResults = page.locator("text=Search Results").locator("..").locator("..")
    this.downloadDialog = page.getByRole("dialog")
  }

  async goto() {
    await super.goto("/discover")
  }

  async expectDiscoverPageVisible() {
    await this.expectHeading("Discover Models")
    await expect(this.page.getByText("Browse and download MLX models")).toBeVisible()
  }

  async search(query: string) {
    await this.searchInput.fill(query)
    // Wait for debounced search
    await this.page.waitForTimeout(500)
    await this.waitForLoad()
  }

  async clearSearch() {
    await this.searchInput.clear()
  }

  async sortBy(option: "Downloads" | "Likes" | "Recently Updated") {
    await this.sortSelect.click()
    await this.page.getByRole("option", { name: option }).click()
  }

  async expectPopularModelsVisible() {
    await expect(this.popularModels).toBeVisible()
  }

  async expectRecentModelsVisible() {
    await expect(this.recentModels).toBeVisible()
  }

  async expectSearchResults() {
    await expect(this.searchResults).toBeVisible()
  }

  async expectNoResults(query: string) {
    await expect(this.page.getByText(`No models found for "${query}"`)).toBeVisible()
  }

  async clickDownloadOnModel(modelName: string) {
    const modelCard = this.page.locator('[class*="Card"]').filter({ hasText: modelName })
    await modelCard.getByRole("button", { name: /Download/i }).click()
    await expect(this.downloadDialog).toBeVisible()
  }

  async expectDownloadDialogVisible() {
    await expect(this.downloadDialog).toBeVisible()
    await expect(this.page.getByText("Download Model")).toBeVisible()
  }

  async closeDownloadDialog() {
    await this.page.getByRole("button", { name: "Cancel" }).click()
    await expect(this.downloadDialog).not.toBeVisible()
  }

  async confirmDownload() {
    await this.page.getByRole("button", { name: "Download" }).click()
  }

  async expectCompatibilityCheck() {
    // Should show compatibility status
    const compatStatus = this.page.locator("text=compatible").or(
      this.page.locator("text=tight")
    ).or(
      this.page.locator("text=incompatible")
    )
    await expect(compatStatus.first()).toBeVisible()
  }

  async expectModelCard(modelName: string) {
    await expect(this.page.locator('[class*="Card"]').filter({ hasText: modelName })).toBeVisible()
  }

  async getModelCardStats(modelName: string) {
    const card = this.page.locator('[class*="Card"]').filter({ hasText: modelName })
    return {
      downloads: await card.locator("svg.lucide-download").locator("..").textContent(),
      likes: await card.locator("svg.lucide-heart").locator("..").textContent(),
      size: await card.locator("svg.lucide-hard-drive").locator("..").textContent(),
    }
  }
}
