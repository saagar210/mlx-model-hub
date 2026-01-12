import { test, expect } from "@playwright/test"

test.describe("Metrics Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/metrics")
  })

  test("should display metrics page header", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "Metrics" })).toBeVisible()
    await expect(
      page.getByText("Monitor system health and performance")
    ).toBeVisible()
  })

  test("should display API status card", async ({ page }) => {
    await expect(page.getByText("API Status")).toBeVisible()
  })

  test("should display metric cards", async ({ page }) => {
    await expect(page.getByText("Models Loaded")).toBeVisible()
    await expect(page.getByText("Active Inferences")).toBeVisible()
    await expect(page.getByText("Training Jobs")).toBeVisible()
    await expect(page.getByText("Uptime")).toBeVisible()
  })

  test("should display storage card", async ({ page }) => {
    await expect(page.getByText("Storage")).toBeVisible()
    await expect(page.getByText("Cache Size")).toBeVisible()
  })

  test("should display quick links", async ({ page }) => {
    await expect(page.getByText("Quick Links")).toBeVisible()
    await expect(page.getByText("Prometheus")).toBeVisible()
    await expect(page.getByText("Grafana Dashboard")).toBeVisible()
    await expect(page.getByText("MLflow Tracking")).toBeVisible()
    await expect(page.getByText("API Documentation")).toBeVisible()
  })

  test("should display prometheus metrics info", async ({ page }) => {
    await expect(page.getByText("Prometheus Metrics")).toBeVisible()
    await expect(page.getByText("http_requests_total")).toBeVisible()
    await expect(page.getByText("http_request_duration_seconds")).toBeVisible()
    await expect(page.getByText("inference_ttft_seconds")).toBeVisible()
    await expect(page.getByText("model_cache_size")).toBeVisible()
  })

  test("should have Grafana button", async ({ page }) => {
    await expect(
      page.getByRole("link", { name: /Open Grafana/ })
    ).toBeVisible()
  })

  test("should show offline status when API is down", async ({ page }) => {
    await page.route("**/health", async (route) => {
      await route.abort()
    })

    await page.reload()
    // Wait for the status to update
    await expect(page.getByText("Offline")).toBeVisible({ timeout: 10000 })
  })

  test("should show online status when API responds", async ({ page }) => {
    await page.route("**/health", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          status: "healthy",
          version: "0.1.0",
          timestamp: new Date().toISOString(),
        }),
      })
    })

    await page.reload()
    await expect(page.getByText("Online")).toBeVisible({ timeout: 10000 })
  })
})
