import { test, expect } from "@playwright/test"

test.describe("Training Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/training")
  })

  test("should display training page header", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "Training" })).toBeVisible()
    await expect(
      page.getByText("Fine-tune models with LoRA on Apple Silicon")
    ).toBeVisible()
  })

  test("should display stats cards", async ({ page }) => {
    await expect(page.getByText("Total Jobs")).toBeVisible()
    await expect(page.getByText("Running")).toBeVisible()
    await expect(page.getByText("Completed")).toBeVisible()
  })

  test("should have new training job button", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: /New Training Job/ })
    ).toBeVisible()
  })

  test("should open create training job dialog", async ({ page }) => {
    await page.getByRole("button", { name: /New Training Job/ }).click()

    await expect(page.getByRole("dialog")).toBeVisible()
    await expect(page.getByText("Create Training Job")).toBeVisible()
    await expect(page.getByLabel("Base Model")).toBeVisible()
    await expect(page.getByLabel("Dataset Path")).toBeVisible()
    await expect(page.getByLabel("Output Directory")).toBeVisible()
    await expect(page.getByLabel("Epochs")).toBeVisible()
    await expect(page.getByLabel("Batch Size")).toBeVisible()
    await expect(page.getByLabel("Learning Rate")).toBeVisible()
  })

  test("should close create dialog on cancel", async ({ page }) => {
    await page.getByRole("button", { name: /New Training Job/ }).click()
    await expect(page.getByRole("dialog")).toBeVisible()

    await page.getByRole("button", { name: "Cancel" }).click()
    await expect(page.getByRole("dialog")).not.toBeVisible()
  })

  test("should show empty state when no jobs", async ({ page }) => {
    await page.route("**/api/v1/training**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ jobs: [], total: 0, page: 1, page_size: 20 }),
      })
    })

    await page.reload()
    await expect(page.getByText("No training jobs yet")).toBeVisible()
  })

  test("should display training jobs when available", async ({ page }) => {
    await page.route("**/api/v1/training**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          jobs: [
            {
              id: "job-123",
              model_id: "model-1",
              status: "running",
              config: {
                base_model: "mlx-community/test-model",
                dataset_path: "/data/train.jsonl",
                output_dir: "/output",
                num_epochs: 3,
                batch_size: 4,
                learning_rate: 0.0001,
                use_lora: true,
              },
              metrics: {
                epoch: 1,
                step: 100,
                loss: 2.5,
                learning_rate: 0.0001,
              },
              started_at: "2024-01-01T00:00:00Z",
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
    await expect(page.getByText("job-123".slice(0, 8))).toBeVisible()
    await expect(page.getByText("mlx-community/test-model")).toBeVisible()
  })
})
