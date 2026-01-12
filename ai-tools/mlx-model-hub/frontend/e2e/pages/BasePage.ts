import { Page, Locator, expect } from "@playwright/test"

export class BasePage {
  readonly page: Page
  readonly sidebar: Locator
  readonly header: Locator
  readonly themeToggle: Locator

  constructor(page: Page) {
    this.page = page
    this.sidebar = page.locator('[class*="w-64"]').first()
    this.header = page.locator("header")
    this.themeToggle = page.getByRole("button", { name: /toggle theme/i })
  }

  async goto(path: string = "/") {
    await this.page.goto(path)
  }

  async waitForLoad() {
    await this.page.waitForLoadState("networkidle")
  }

  // Navigation helpers
  async navigateTo(pageName: "Dashboard" | "Discover" | "Models" | "Training" | "Inference" | "Metrics") {
    await this.page.getByRole("link", { name: pageName }).click()
    await this.waitForLoad()
  }

  // Theme helpers
  async toggleTheme(theme: "Light" | "Dark" | "System") {
    await this.themeToggle.click()
    await this.page.getByRole("menuitem", { name: theme }).click()
  }

  async expectTheme(theme: "light" | "dark") {
    const html = this.page.locator("html")
    if (theme === "dark") {
      await expect(html).toHaveClass(/dark/)
    } else {
      await expect(html).not.toHaveClass(/dark/)
    }
  }

  // API status helpers
  async expectApiOnline() {
    await expect(this.header.getByText("Online")).toBeVisible()
  }

  async expectApiOffline() {
    await expect(this.header.getByText("Offline")).toBeVisible()
  }

  // Toast helpers
  async expectToast(message: string | RegExp) {
    const toast = this.page.locator('[data-sonner-toast]')
    await expect(toast.filter({ hasText: message })).toBeVisible()
  }

  // Common assertions
  async expectHeading(text: string) {
    await expect(this.page.getByRole("heading", { name: text })).toBeVisible()
  }

  async expectUrl(path: string) {
    await expect(this.page).toHaveURL(new RegExp(path))
  }
}
