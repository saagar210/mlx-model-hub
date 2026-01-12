import { test, expect } from "@playwright/test"

test.describe("Inference Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/inference")
  })

  test("should display inference page header", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "Inference" })).toBeVisible()
    await expect(
      page.getByText("Test models in the interactive playground")
    ).toBeVisible()
  })

  test("should have model selector", async ({ page }) => {
    await expect(page.getByLabel("Model")).toBeVisible()
    await expect(page.getByText("Select a model")).toBeVisible()
  })

  test("should have message input", async ({ page }) => {
    await expect(
      page.getByPlaceholder("Type your message...")
    ).toBeVisible()
  })

  test("should have settings button", async ({ page }) => {
    const settingsButton = page.locator("button").filter({
      has: page.locator("svg"),
    })
    await expect(settingsButton.first()).toBeVisible()
  })

  test("should toggle settings panel", async ({ page }) => {
    // Settings panel should not be visible initially
    await expect(page.getByText("Max Tokens")).not.toBeVisible()

    // Click settings button (first icon button)
    await page.locator("button").filter({ has: page.locator("svg") }).first().click()

    // Settings panel should now be visible
    await expect(page.getByText("Max Tokens")).toBeVisible()
    await expect(page.getByText("Temperature")).toBeVisible()
    await expect(page.getByText("Top P")).toBeVisible()
  })

  test("should show empty conversation state", async ({ page }) => {
    await expect(
      page.getByText("Start a conversation by sending a message below")
    ).toBeVisible()
  })

  test("send button should be disabled without model selection", async ({
    page,
  }) => {
    await page.route("**/api/v1/models**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          models: [
            {
              id: "test-model",
              name: "Test Model",
              repository: "mlx-community/test",
              status: "cached",
              cached: true,
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
    await page.getByPlaceholder("Type your message...").fill("Hello")

    // Send button should be disabled until model is selected
    const sendButton = page.getByRole("button").filter({ hasText: "" }).last()
    await expect(sendButton).toBeDisabled()
  })

  test("should handle keyboard shortcut hint", async ({ page }) => {
    await expect(
      page.getByText("Press Enter to send, Shift+Enter for new line")
    ).toBeVisible()
  })
})
