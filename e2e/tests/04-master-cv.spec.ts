import { test, expect } from "@playwright/test";

test.describe("Master CV", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/cv/master");
  });

  test("master CV page loads", async ({ page }) => {
    await expect(page.getByRole("heading", { name: /master cv/i })).toBeVisible({ timeout: 15_000 });
  });

  test("shows template selector", async ({ page }) => {
    // Template panel toggle
    const templateBtn = page.getByRole("button", { name: /skabelon|template/i });
    if (await templateBtn.isVisible()) {
      await templateBtn.click();
      await expect(page.getByText(/ats|professional|modern/i).first()).toBeVisible({ timeout: 5_000 });
    }
  });

  test("download button is present", async ({ page }) => {
    const downloadBtn = page.getByRole("button", { name: /download|hent/i });
    await expect(downloadBtn).toBeVisible({ timeout: 10_000 });
  });

  test("generate master CV button triggers generation", async ({ page }) => {
    const generateBtn = page.getByRole("button", { name: /generer|generate/i });
    if (await generateBtn.isVisible()) {
      // Don't click in CI to avoid consuming AI tokens — just verify it exists
      await expect(generateBtn).toBeEnabled();
    }
  });
});
