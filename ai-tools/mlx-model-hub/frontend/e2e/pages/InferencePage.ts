import { Page, Locator, expect } from "@playwright/test"
import { BasePage } from "./BasePage"

export class InferencePage extends BasePage {
  readonly modelSelect: Locator
  readonly promptInput: Locator
  readonly sendButton: Locator
  readonly stopButton: Locator
  readonly clearButton: Locator
  readonly settingsButton: Locator
  readonly streamingToggle: Locator
  readonly messagesContainer: Locator
  readonly settingsPanel: Locator

  constructor(page: Page) {
    super(page)
    this.modelSelect = page.getByRole("combobox").first()
    this.promptInput = page.getByPlaceholder("Type your message...")
    this.sendButton = page.getByRole("button").filter({ has: page.locator("svg.lucide-send") })
    this.stopButton = page.getByRole("button").filter({ has: page.locator("svg.lucide-stop-circle") })
    this.clearButton = page.getByRole("button").filter({ has: page.locator("svg.lucide-trash-2") })
    this.settingsButton = page.getByRole("button").filter({ has: page.locator("svg.lucide-settings") })
    this.streamingToggle = page.getByLabel(/streaming/i)
    this.messagesContainer = page.locator('[class*="ScrollArea"]')
    this.settingsPanel = page.locator("text=Settings").locator("..").locator("..")
  }

  async goto() {
    await super.goto("/inference")
  }

  async expectInferencePageVisible() {
    await this.expectHeading("Inference")
    await expect(this.page.getByText("Test models in the interactive playground")).toBeVisible()
  }

  async selectModel(modelName: string) {
    await this.modelSelect.click()
    await this.page.getByRole("option", { name: modelName }).click()
  }

  async sendMessage(message: string) {
    await this.promptInput.fill(message)
    await this.sendButton.click()
  }

  async expectUserMessage(message: string) {
    await expect(this.messagesContainer.getByText(message)).toBeVisible()
  }

  async expectAssistantResponse() {
    const assistantMessages = this.page.locator('[class*="bg-muted"]')
    await expect(assistantMessages.first()).toBeVisible()
  }

  async clearConversation() {
    await this.clearButton.click()
  }

  async toggleSettings() {
    await this.settingsButton.click()
  }

  async expectSettingsPanelVisible() {
    await expect(this.page.getByLabel("Max Tokens")).toBeVisible()
    await expect(this.page.getByLabel(/Temperature/)).toBeVisible()
    await expect(this.page.getByLabel(/Top P/)).toBeVisible()
  }

  async setMaxTokens(value: number) {
    await this.page.getByLabel("Max Tokens").fill(value.toString())
  }

  async setTemperature(value: number) {
    // Temperature is a range input
    await this.page.getByLabel(/Temperature/).fill(value.toString())
  }

  async toggleStreaming() {
    await this.streamingToggle.click()
  }

  async expectStreaming(enabled: boolean) {
    if (enabled) {
      await expect(this.page.getByText("Streaming enabled")).toBeVisible()
    }
  }

  async stopGeneration() {
    await this.stopButton.click()
  }

  async expectEmptyState() {
    await expect(this.page.getByText("Start a conversation")).toBeVisible()
  }
}
