import { test, expect } from "@playwright/test"

test.describe("Navigation", () => {
  test("should display the dashboard page", async ({ page }) => {
    await page.goto("/")

    await expect(page).toHaveTitle(/MLX Model Hub/)
    // Use first() since there are multiple Dashboard headings (header + page)
    await expect(page.getByRole("heading", { name: "Dashboard" }).first()).toBeVisible()
    await expect(page.getByText("Overview of your MLX Model Hub")).toBeVisible()
  })

  test("should navigate to models page", async ({ page }) => {
    await page.goto("/")

    // Click on the sidebar link (uses exact match to avoid matching other links)
    await page.getByRole("link", { name: "Models", exact: true }).first().click()
    await expect(page).toHaveURL("/models")
    await expect(page.getByRole("heading", { name: "Models" }).first()).toBeVisible()
  })

  test("should navigate to training page", async ({ page }) => {
    await page.goto("/")

    await page.getByRole("link", { name: "Training", exact: true }).first().click()
    await expect(page).toHaveURL("/training")
    await expect(page.getByRole("heading", { name: "Training" }).first()).toBeVisible()
  })

  test("should navigate to inference page", async ({ page }) => {
    await page.goto("/")

    await page.getByRole("link", { name: "Inference", exact: true }).first().click()
    await expect(page).toHaveURL("/inference")
    await expect(page.getByRole("heading", { name: "Inference" }).first()).toBeVisible()
  })

  test("should navigate to metrics page", async ({ page }) => {
    await page.goto("/")

    await page.getByRole("link", { name: "Metrics", exact: true }).first().click()
    await expect(page).toHaveURL("/metrics")
    await expect(page.getByRole("heading", { name: "Metrics" }).first()).toBeVisible()
  })

  test("should navigate to discover page", async ({ page }) => {
    await page.goto("/")

    await page.getByRole("link", { name: "Discover", exact: true }).first().click()
    await expect(page).toHaveURL("/discover")
    await expect(page.getByRole("heading", { name: "Discover Models" })).toBeVisible()
  })

  test("sidebar should highlight active page", async ({ page }) => {
    await page.goto("/models")

    // The active sidebar link should have the active styles
    const sidebar = page.locator("nav")
    const modelsLink = sidebar.getByRole("link", { name: "Models", exact: true })
    await expect(modelsLink).toHaveClass(/bg-primary/)
  })

  test("should navigate via quick actions on dashboard", async ({ page }) => {
    await page.goto("/")

    // Test quick action links
    const downloadModelLink = page.getByRole("link", { name: /Download a Model/ })
    await expect(downloadModelLink).toBeVisible()

    const runInferenceLink = page.getByRole("link", { name: /Run Inference/ })
    await expect(runInferenceLink).toBeVisible()

    const startTrainingLink = page.getByRole("link", { name: /Start Training/ })
    await expect(startTrainingLink).toBeVisible()
  })
})
