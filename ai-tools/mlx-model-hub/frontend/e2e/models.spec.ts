import { test, expect } from "@playwright/test"

test.describe("Models Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/models")
  })

  test("should display models page header", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "Models" })).toBeVisible()
    await expect(
      page.getByText("Manage your MLX models from Hugging Face")
    ).toBeVisible()
  })

  test("should have download model button", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: /Download Model/ })
    ).toBeVisible()
  })

  test("should have refresh button", async ({ page }) => {
    const refreshButton = page.getByRole("button").filter({ has: page.locator("svg") }).first()
    await expect(refreshButton).toBeVisible()
  })

  test("should open download model dialog", async ({ page }) => {
    await page.getByRole("button", { name: /Download Model/ }).click()

    await expect(page.getByRole("dialog")).toBeVisible()
    await expect(
      page.getByText("Enter a Hugging Face repository ID")
    ).toBeVisible()
    await expect(
      page.getByPlaceholder("mlx-community/Llama-3.2-3B-Instruct-4bit")
    ).toBeVisible()
  })

  test("should close download dialog on cancel", async ({ page }) => {
    await page.getByRole("button", { name: /Download Model/ }).click()
    await expect(page.getByRole("dialog")).toBeVisible()

    await page.getByRole("button", { name: "Cancel" }).click()
    await expect(page.getByRole("dialog")).not.toBeVisible()
  })

  test("should show empty state when no models", async ({ page }) => {
    // Mock empty API response
    await page.route("**/api/v1/models**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ models: [], total: 0, page: 1, page_size: 20 }),
      })
    })

    await page.reload()
    await expect(page.getByText("No models yet")).toBeVisible()
  })

  test("should display models in table when available", async ({ page }) => {
    // Mock API response with models
    await page.route("**/api/v1/models**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          models: [
            {
              id: "test-model-1",
              name: "Test Model",
              repository: "mlx-community/test-model",
              status: "cached",
              cached: true,
              size_bytes: 1073741824,
              created_at: "2024-01-01T00:00:00Z",
              updated_at: "2024-01-01T00:00:00Z",
            },
          ],
          total: 1,
          page: 1,
          page_size: 20,
        }),
      })
    })

    await page.reload()
    await expect(page.getByText("Test Model")).toBeVisible()
    await expect(page.getByText("mlx-community/test-model")).toBeVisible()
  })
})
