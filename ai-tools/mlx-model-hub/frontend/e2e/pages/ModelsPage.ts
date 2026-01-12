import { Page, Locator, expect } from "@playwright/test"
import { BasePage } from "./BasePage"

export class ModelsPage extends BasePage {
  readonly createModelButton: Locator
  readonly refreshButton: Locator
  readonly modelsTable: Locator
  readonly createModelDialog: Locator
  readonly emptyState: Locator

  constructor(page: Page) {
    super(page)
    this.createModelButton = page.getByRole("button", { name: /Create Model/i })
    this.refreshButton = page.getByRole("button").filter({ has: page.locator("svg.lucide-refresh-cw") })
    this.modelsTable = page.locator("table")
    this.createModelDialog = page.getByRole("dialog")
    this.emptyState = page.getByText("No models yet")
  }

  async goto() {
    await super.goto("/models")
  }

  async expectModelsPageVisible() {
    await this.expectHeading("Models")
    await expect(this.page.getByText("Manage your MLX models")).toBeVisible()
  }

  async openCreateModelDialog() {
    await this.createModelButton.click()
    await expect(this.createModelDialog).toBeVisible()
  }

  async closeDialog() {
    await this.page.getByRole("button", { name: "Cancel" }).click()
    await expect(this.createModelDialog).not.toBeVisible()
  }

  async fillCreateModelForm(data: {
    name: string
    taskType?: string
    baseModel: string
    description?: string
  }) {
    await this.page.getByLabel("Name").fill(data.name)
    if (data.taskType) {
      await this.page.getByLabel("Task Type").click()
      await this.page.getByRole("option", { name: data.taskType }).click()
    }
    await this.page.getByLabel("Base Model").fill(data.baseModel)
    if (data.description) {
      await this.page.getByLabel("Description").fill(data.description)
    }
  }

  async submitCreateModel() {
    await this.page.getByRole("button", { name: "Create" }).click()
  }

  async expectModelInTable(modelName: string) {
    await expect(this.modelsTable.getByText(modelName)).toBeVisible()
  }

  async expectEmptyState() {
    await expect(this.emptyState).toBeVisible()
  }

  async deleteModel(modelName: string) {
    const row = this.modelsTable.locator("tr").filter({ hasText: modelName })
    await row.getByRole("button", { name: /delete/i }).click()
    await this.page.getByRole("button", { name: "Delete" }).click()
  }

  async viewModelDetails(modelName: string) {
    await this.modelsTable.getByText(modelName).click()
  }

  async refresh() {
    await this.refreshButton.click()
    await this.waitForLoad()
  }
}
