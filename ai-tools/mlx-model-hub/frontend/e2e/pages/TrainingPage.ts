import { Page, Locator, expect } from "@playwright/test"
import { BasePage } from "./BasePage"

export class TrainingPage extends BasePage {
  readonly newJobButton: Locator
  readonly refreshButton: Locator
  readonly jobsTable: Locator
  readonly createJobDialog: Locator
  readonly emptyState: Locator
  readonly totalJobsCard: Locator
  readonly runningCard: Locator
  readonly completedCard: Locator

  constructor(page: Page) {
    super(page)
    this.newJobButton = page.getByRole("button", { name: /New Training Job/i })
    this.refreshButton = page.getByRole("button").filter({ has: page.locator("svg.lucide-refresh-cw") })
    this.jobsTable = page.locator("table")
    this.createJobDialog = page.getByRole("dialog")
    this.emptyState = page.getByText("No training jobs yet")
    this.totalJobsCard = page.locator("text=Total Jobs").locator("..")
    this.runningCard = page.locator("text=Running").locator("..")
    this.completedCard = page.locator("text=Completed").locator("..")
  }

  async goto() {
    await super.goto("/training")
  }

  async expectTrainingPageVisible() {
    await this.expectHeading("Training")
    await expect(this.page.getByText("Fine-tune models with LoRA")).toBeVisible()
  }

  async expectStatsCardsVisible() {
    await expect(this.totalJobsCard).toBeVisible()
    await expect(this.runningCard).toBeVisible()
    await expect(this.completedCard).toBeVisible()
  }

  async openCreateJobDialog() {
    await this.newJobButton.click()
    await expect(this.createJobDialog).toBeVisible()
  }

  async closeDialog() {
    await this.page.getByRole("button", { name: "Cancel" }).click()
    await expect(this.createJobDialog).not.toBeVisible()
  }

  async fillCreateJobForm(data: {
    baseModel: string
    datasetPath: string
    outputDir: string
    epochs?: number
    batchSize?: number
    learningRate?: number
    loraRank?: number
    loraAlpha?: number
  }) {
    // Select base model
    await this.page.getByLabel("Base Model").click()
    await this.page.getByRole("option", { name: new RegExp(data.baseModel) }).click()

    await this.page.getByLabel("Dataset Path").fill(data.datasetPath)
    await this.page.getByLabel("Output Directory").fill(data.outputDir)

    if (data.epochs) {
      await this.page.getByLabel("Epochs").fill(data.epochs.toString())
    }
    if (data.batchSize) {
      await this.page.getByLabel("Batch Size").fill(data.batchSize.toString())
    }
    if (data.learningRate) {
      await this.page.getByLabel("Learning Rate").fill(data.learningRate.toString())
    }
    if (data.loraRank) {
      await this.page.getByLabel("LoRA Rank").fill(data.loraRank.toString())
    }
    if (data.loraAlpha) {
      await this.page.getByLabel("LoRA Alpha").fill(data.loraAlpha.toString())
    }
  }

  async submitCreateJob() {
    await this.page.getByRole("button", { name: "Start Training" }).click()
  }

  async expectJobInTable(jobId: string) {
    await expect(this.jobsTable.getByText(jobId.slice(0, 8))).toBeVisible()
  }

  async expectEmptyState() {
    await expect(this.emptyState).toBeVisible()
  }

  async cancelJob(jobId: string) {
    const row = this.jobsTable.locator("tr").filter({ hasText: jobId.slice(0, 8) })
    await row.getByRole("button", { name: /Cancel/i }).click()
  }

  async expectJobStatus(jobId: string, status: "pending" | "running" | "completed" | "failed" | "cancelled") {
    const row = this.jobsTable.locator("tr").filter({ hasText: jobId.slice(0, 8) })
    await expect(row.getByText(status)).toBeVisible()
  }

  async refresh() {
    await this.refreshButton.click()
    await this.waitForLoad()
  }
}
