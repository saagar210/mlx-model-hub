import { test, expect } from "@playwright/test"

test.describe("Dark Mode", () => {
  test.beforeEach(async ({ page }) => {
    // Clear any stored theme preference
    await page.goto("/")
    await page.evaluate(() => localStorage.clear())
    await page.reload()
  })

  test("should have theme toggle button in header", async ({ page }) => {
    // Look for the theme toggle button (has sr-only "Toggle theme" text)
    const themeToggle = page.getByRole("button", { name: /toggle theme/i })
    await expect(themeToggle).toBeVisible()
  })

  test("should switch to dark mode", async ({ page }) => {
    // Click theme toggle
    const themeToggle = page.getByRole("button", { name: /toggle theme/i })
    await themeToggle.click()

    // Select dark mode from dropdown
    await page.getByRole("menuitem", { name: /dark/i }).click()

    // Verify dark mode is applied
    const html = page.locator("html")
    await expect(html).toHaveClass(/dark/)
  })

  test("should switch to light mode", async ({ page }) => {
    // First set dark mode
    const themeToggle = page.getByRole("button", { name: /toggle theme/i })
    await themeToggle.click()
    await page.getByRole("menuitem", { name: /dark/i }).click()

    // Then switch to light mode
    await themeToggle.click()
    await page.getByRole("menuitem", { name: /light/i }).click()

    // Verify light mode is applied
    const html = page.locator("html")
    await expect(html).not.toHaveClass(/dark/)
  })

  test("should persist theme preference across page navigation", async ({ page }) => {
    // Set dark mode
    const themeToggle = page.getByRole("button", { name: /toggle theme/i })
    await themeToggle.click()
    await page.getByRole("menuitem", { name: /dark/i }).click()

    // Navigate to another page
    await page.getByRole("link", { name: /models/i }).click()
    await page.waitForURL("**/models")

    // Verify dark mode is still applied
    const html = page.locator("html")
    await expect(html).toHaveClass(/dark/)
  })

  test("should persist theme preference after page reload", async ({ page }) => {
    // Set dark mode
    const themeToggle = page.getByRole("button", { name: /toggle theme/i })
    await themeToggle.click()
    await page.getByRole("menuitem", { name: /dark/i }).click()

    // Reload page
    await page.reload()

    // Verify dark mode is still applied
    const html = page.locator("html")
    await expect(html).toHaveClass(/dark/)
  })

  test("should use system preference when set to system", async ({ page }) => {
    // Click theme toggle
    const themeToggle = page.getByRole("button", { name: /toggle theme/i })
    await themeToggle.click()

    // Select system from dropdown
    await page.getByRole("menuitem", { name: /system/i }).click()

    // Verify theme follows system (we can't easily test the actual system preference,
    // but we can verify the option was selected by checking localStorage or class)
    const themeValue = await page.evaluate(() => localStorage.getItem("theme"))
    expect(themeValue).toBe("system")
  })

  test("dark mode should work on dashboard page", async ({ page }) => {
    await page.goto("/")

    // Set dark mode
    const themeToggle = page.getByRole("button", { name: /toggle theme/i })
    await themeToggle.click()
    await page.getByRole("menuitem", { name: /dark/i }).click()

    // Verify dashboard content is visible in dark mode
    await expect(page.getByRole("heading", { name: /dashboard/i })).toBeVisible()
    const html = page.locator("html")
    await expect(html).toHaveClass(/dark/)
  })

  test("dark mode should work on models page", async ({ page }) => {
    await page.goto("/models")

    // Set dark mode
    const themeToggle = page.getByRole("button", { name: /toggle theme/i })
    await themeToggle.click()
    await page.getByRole("menuitem", { name: /dark/i }).click()

    // Verify models page content is visible in dark mode
    await expect(page.getByRole("heading", { name: /models/i })).toBeVisible()
    const html = page.locator("html")
    await expect(html).toHaveClass(/dark/)
  })

  test("dark mode should work on training page", async ({ page }) => {
    await page.goto("/training")

    // Set dark mode
    const themeToggle = page.getByRole("button", { name: /toggle theme/i })
    await themeToggle.click()
    await page.getByRole("menuitem", { name: /dark/i }).click()

    // Verify training page content is visible in dark mode
    await expect(page.getByRole("heading", { name: /training/i })).toBeVisible()
    const html = page.locator("html")
    await expect(html).toHaveClass(/dark/)
  })

  test("dark mode should work on inference page", async ({ page }) => {
    await page.goto("/inference")

    // Set dark mode
    const themeToggle = page.getByRole("button", { name: /toggle theme/i })
    await themeToggle.click()
    await page.getByRole("menuitem", { name: /dark/i }).click()

    // Verify inference page content is visible in dark mode
    await expect(page.getByRole("heading", { name: /inference/i })).toBeVisible()
    const html = page.locator("html")
    await expect(html).toHaveClass(/dark/)
  })

  test("dark mode should work on metrics page", async ({ page }) => {
    await page.goto("/metrics")

    // Set dark mode
    const themeToggle = page.getByRole("button", { name: /toggle theme/i })
    await themeToggle.click()
    await page.getByRole("menuitem", { name: /dark/i }).click()

    // Verify metrics page content is visible in dark mode
    await expect(page.getByRole("heading", { name: /metrics/i })).toBeVisible()
    const html = page.locator("html")
    await expect(html).toHaveClass(/dark/)
  })

  test("dark mode should work on discover page", async ({ page }) => {
    await page.goto("/discover")

    // Set dark mode
    const themeToggle = page.getByRole("button", { name: /toggle theme/i })
    await themeToggle.click()
    await page.getByRole("menuitem", { name: /dark/i }).click()

    // Verify discover page content is visible in dark mode
    await expect(page.getByRole("heading", { name: /discover/i })).toBeVisible()
    const html = page.locator("html")
    await expect(html).toHaveClass(/dark/)
  })
})
