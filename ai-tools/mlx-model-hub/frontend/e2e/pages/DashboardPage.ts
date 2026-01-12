import { Page, Locator, expect } from "@playwright/test"
import { BasePage } from "./BasePage"

export class DashboardPage extends BasePage {
  readonly totalModelsCard: Locator
  readonly trainingJobsCard: Locator
  readonly modelsLoadedCard: Locator
  readonly cacheSizeCard: Locator
  readonly quickActions: Locator
  readonly systemStatus: Locator

  constructor(page: Page) {
    super(page)
    this.totalModelsCard = page.locator('[href="/models"]').filter({ hasText: "Total Models" })
    this.trainingJobsCard = page.locator('[href="/training"]').filter({ hasText: "Training Jobs" })
    this.modelsLoadedCard = page.locator('[href="/inference"]').filter({ hasText: "Models Loaded" })
    this.cacheSizeCard = page.locator('[href="/metrics"]').filter({ hasText: "Cache Size" })
    this.quickActions = page.locator("text=Quick Actions").locator("..")
    this.systemStatus = page.locator("text=System Status").locator("..")
  }

  async goto() {
    await super.goto("/")
  }

  async expectDashboardVisible() {
    await this.expectHeading("Dashboard")
    await expect(this.page.getByText("Overview of your MLX Model Hub")).toBeVisible()
  }

  async expectStatsCardsVisible() {
    await expect(this.totalModelsCard).toBeVisible()
    await expect(this.trainingJobsCard).toBeVisible()
    await expect(this.modelsLoadedCard).toBeVisible()
    await expect(this.cacheSizeCard).toBeVisible()
  }

  async expectQuickActionsVisible() {
    await expect(this.page.getByText("Download a Model")).toBeVisible()
    await expect(this.page.getByText("Start Training")).toBeVisible()
    await expect(this.page.getByText("Run Inference")).toBeVisible()
  }

  async clickQuickAction(action: "Download a Model" | "Start Training" | "Run Inference") {
    await this.page.getByText(action).click()
    await this.waitForLoad()
  }

  async getStatValue(cardName: "Total Models" | "Training Jobs" | "Models Loaded" | "Cache Size"): Promise<string> {
    const card = this.page.locator(`text=${cardName}`).locator("..").locator("..")
    const value = card.locator(".text-2xl")
    return await value.textContent() || ""
  }
}
