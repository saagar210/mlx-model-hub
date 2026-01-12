import { test, expect } from "@playwright/test"

test.describe("Navigation", () => {
  test("should display the dashboard page", async ({ page }) => {
    await page.goto("/")

    await expect(page).toHaveTitle(/MLX Model Hub/)
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible()
    await expect(page.getByText("Overview of your MLX Model Hub")).toBeVisible()
  })

  test("should navigate to models page", async ({ page }) => {
    await page.goto("/")

    await page.getByRole("link", { name: "Models" }).click()
    await expect(page).toHaveURL("/models")
    await expect(page.getByRole("heading", { name: "Models" })).toBeVisible()
  })

  test("should navigate to training page", async ({ page }) => {
    await page.goto("/")

    await page.getByRole("link", { name: "Training" }).click()
    await expect(page).toHaveURL("/training")
    await expect(page.getByRole("heading", { name: "Training" })).toBeVisible()
  })

  test("should navigate to inference page", async ({ page }) => {
    await page.goto("/")

    await page.getByRole("link", { name: "Inference" }).click()
    await expect(page).toHaveURL("/inference")
    await expect(page.getByRole("heading", { name: "Inference" })).toBeVisible()
  })

  test("should navigate to metrics page", async ({ page }) => {
    await page.goto("/")

    await page.getByRole("link", { name: "Metrics" }).click()
    await expect(page).toHaveURL("/metrics")
    await expect(page.getByRole("heading", { name: "Metrics" })).toBeVisible()
  })

  test("sidebar should highlight active page", async ({ page }) => {
    await page.goto("/models")

    const modelsLink = page.getByRole("link", { name: "Models" })
    await expect(modelsLink).toHaveClass(/bg-primary/)
  })
})
