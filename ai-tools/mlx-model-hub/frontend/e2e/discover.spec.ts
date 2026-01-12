import { test, expect } from "@playwright/test"
import { mockDiscoverModels, mockCompatibility, emptyDiscoverModels } from "./fixtures/mock-data"

test.describe("Discover Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/discover")
  })

  test("should display discover page header", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "Discover Models" })).toBeVisible()
    await expect(
      page.getByText("Browse and download MLX models")
    ).toBeVisible()
  })

  test("should have search input", async ({ page }) => {
    await expect(page.getByPlaceholder("Search MLX models...")).toBeVisible()
  })

  test("should have sort select", async ({ page }) => {
    await expect(page.getByRole("combobox")).toBeVisible()
  })

  test("should display popular models section", async ({ page }) => {
    // Mock API response with models
    await page.route("**/api/v1/discover/models**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockDiscoverModels),
      })
    })

    await page.reload()
    await expect(page.getByText("Popular Models")).toBeVisible()
  })

  test("should search for models", async ({ page }) => {
    // Mock search response
    await page.route("**/api/v1/discover/models**", async (route) => {
      const url = new URL(route.request().url())
      const query = url.searchParams.get("q") || url.searchParams.get("search")

      if (query === "llama") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            models: [mockDiscoverModels.models[0]], // Llama model
            total_count: 1,
            page: 1,
            page_size: 20,
          }),
        })
      } else {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(mockDiscoverModels),
        })
      }
    })

    await page.reload()

    const searchInput = page.getByPlaceholder("Search MLX models...")
    await searchInput.fill("llama")

    // Wait for debounced search
    await page.waitForTimeout(600)

    await expect(page.getByText("Llama-3.2-3B-Instruct-4bit")).toBeVisible()
  })

  test("should show no results message for invalid search", async ({ page }) => {
    // Mock empty search response
    await page.route("**/api/v1/discover/models**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(emptyDiscoverModels),
      })
    })

    await page.reload()

    const searchInput = page.getByPlaceholder("Search MLX models...")
    await searchInput.fill("nonexistentmodel12345")

    // Wait for debounced search
    await page.waitForTimeout(600)

    await expect(page.getByText(/no models found/i).or(page.getByText(/no results/i))).toBeVisible()
  })

  test("should sort models by downloads", async ({ page }) => {
    await page.route("**/api/v1/discover/models**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockDiscoverModels),
      })
    })

    await page.reload()

    const sortSelect = page.getByRole("combobox")
    await sortSelect.click()

    // Select sort option
    await page.getByRole("option", { name: /downloads/i }).click()
  })

  test("should display model cards with stats", async ({ page }) => {
    await page.route("**/api/v1/discover/models**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockDiscoverModels),
      })
    })

    await page.reload()

    // Check for model card elements
    await expect(page.getByText("Llama-3.2-3B-Instruct-4bit")).toBeVisible()
    // Check for download count (150K for first model)
    await expect(page.getByText(/150/).or(page.getByText("150K"))).toBeVisible()
  })

  test("should open download dialog when clicking download", async ({ page }) => {
    await page.route("**/api/v1/discover/models**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockDiscoverModels),
      })
    })

    await page.route("**/api/v1/discover/compatibility**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockCompatibility),
      })
    })

    await page.reload()

    // Find and click download button on first model card
    const downloadButton = page.getByRole("button", { name: /download/i }).first()
    await downloadButton.click()

    // Check dialog appears
    await expect(page.getByRole("dialog")).toBeVisible()
  })

  test("should close download dialog on cancel", async ({ page }) => {
    await page.route("**/api/v1/discover/models**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockDiscoverModels),
      })
    })

    await page.route("**/api/v1/discover/compatibility**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockCompatibility),
      })
    })

    await page.reload()

    const downloadButton = page.getByRole("button", { name: /download/i }).first()
    await downloadButton.click()

    await expect(page.getByRole("dialog")).toBeVisible()

    await page.getByRole("button", { name: "Cancel" }).click()
    await expect(page.getByRole("dialog")).not.toBeVisible()
  })

  test("should show compatibility status", async ({ page }) => {
    await page.route("**/api/v1/discover/models**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockDiscoverModels),
      })
    })

    await page.route("**/api/v1/discover/compatibility**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockCompatibility),
      })
    })

    await page.reload()

    const downloadButton = page.getByRole("button", { name: /download/i }).first()
    await downloadButton.click()

    // Check compatibility message appears in dialog
    await expect(
      page.getByText(/compatible/i).or(page.getByText(/memory/i))
    ).toBeVisible()
  })

  test("should display model size information", async ({ page }) => {
    await page.route("**/api/v1/discover/models**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockDiscoverModels),
      })
    })

    await page.reload()

    // Check for size display (2 GB for first model)
    await expect(page.getByText(/2.*GB/i).or(page.getByText(/2\.0/i))).toBeVisible()
  })

  test("should display quantization badge", async ({ page }) => {
    await page.route("**/api/v1/discover/models**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockDiscoverModels),
      })
    })

    await page.reload()

    // Check for quantization badge (4bit)
    await expect(page.getByText(/4bit/i).or(page.getByText(/4-bit/i))).toBeVisible()
  })
})
