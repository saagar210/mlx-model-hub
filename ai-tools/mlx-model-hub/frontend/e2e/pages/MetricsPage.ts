import { Page, Locator, expect } from "@playwright/test"
import { BasePage } from "./BasePage"

export class MetricsPage extends BasePage {
  readonly refreshButton: Locator
  readonly grafanaButton: Locator
  readonly apiStatusCard: Locator
  readonly modelsLoadedCard: Locator
  readonly activeInferencesCard: Locator
  readonly trainingJobsCard: Locator
  readonly uptimeCard: Locator
  readonly storageCard: Locator
  readonly quickLinks: Locator
  readonly prometheusMetrics: Locator

  constructor(page: Page) {
    super(page)
    this.refreshButton = page.getByRole("button").filter({ has: page.locator("svg.lucide-refresh-cw") })
    this.grafanaButton = page.getByRole("link", { name: /Open Grafana/i })
    this.apiStatusCard = page.locator("text=API Status").locator("..").locator("..")
    this.modelsLoadedCard = page.locator("text=Models Loaded").locator("..").locator("..")
    this.activeInferencesCard = page.locator("text=Active Inferences").locator("..").locator("..")
    this.trainingJobsCard = page.locator("text=Training Jobs").locator("..").locator("..")
    this.uptimeCard = page.locator("text=Uptime").locator("..").locator("..")
    this.storageCard = page.locator("text=Storage").locator("..").locator("..")
    this.quickLinks = page.locator("text=Quick Links").locator("..").locator("..")
    this.prometheusMetrics = page.locator("text=Prometheus Metrics").locator("..").locator("..")
  }

  async goto() {
    await super.goto("/metrics")
  }

  async expectMetricsPageVisible() {
    await this.expectHeading("Metrics")
    await expect(this.page.getByText("Monitor system health and performance")).toBeVisible()
  }

  async expectApiOnlineStatus() {
    await expect(this.apiStatusCard.getByText("Online")).toBeVisible()
  }

  async expectApiOfflineStatus() {
    await expect(this.apiStatusCard.getByText("Offline")).toBeVisible()
  }

  async expectAllMetricCardsVisible() {
    await expect(this.modelsLoadedCard).toBeVisible()
    await expect(this.activeInferencesCard).toBeVisible()
    await expect(this.trainingJobsCard).toBeVisible()
    await expect(this.uptimeCard).toBeVisible()
  }

  async expectStorageCardVisible() {
    await expect(this.storageCard).toBeVisible()
    await expect(this.page.getByText("Cache Size")).toBeVisible()
  }

  async expectQuickLinksVisible() {
    await expect(this.quickLinks).toBeVisible()
    await expect(this.page.getByText("Prometheus")).toBeVisible()
    await expect(this.page.getByText("Grafana Dashboard")).toBeVisible()
    await expect(this.page.getByText("MLflow Tracking")).toBeVisible()
    await expect(this.page.getByText("API Documentation")).toBeVisible()
  }

  async expectPrometheusMetricsVisible() {
    await expect(this.prometheusMetrics).toBeVisible()
    await expect(this.page.getByText("http_requests_total")).toBeVisible()
    await expect(this.page.getByText("inference_ttft_seconds")).toBeVisible()
  }

  async expectChartsVisible() {
    // Check that charts are rendered
    await expect(this.page.getByText("Time to First Token")).toBeVisible()
    await expect(this.page.getByText("Inference Throughput")).toBeVisible()
    await expect(this.page.getByText("Requests per Hour")).toBeVisible()
  }

  async refresh() {
    await this.refreshButton.click()
    await this.waitForLoad()
  }

  async clickGrafana() {
    // Opens in new tab, just verify link exists
    await expect(this.grafanaButton).toHaveAttribute("href", /grafana/)
  }

  async clickQuickLink(link: "Prometheus" | "Grafana Dashboard" | "MLflow Tracking" | "API Documentation") {
    await this.quickLinks.getByText(link).click()
  }
}
