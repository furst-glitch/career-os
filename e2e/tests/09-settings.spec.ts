import { test, expect } from "@playwright/test";

test.describe("Settings", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/settings");
  });

  test("settings page loads", async ({ page }) => {
    await expect(page.getByRole("heading", { name: /indstillinger|settings/i })).toBeVisible({ timeout: 15_000 });
  });

  test("has Dokumenter tab", async ({ page }) => {
    const docsTab = page.getByRole("tab", { name: /dokumenter/i })
      .or(page.getByRole("button", { name: /dokumenter/i }));
    await expect(docsTab).toBeVisible();
    await docsTab.click();
    await expect(page.getByText(/cv skabelon|template/i).first()).toBeVisible({ timeout: 5_000 });
  });

  test("has API-nøgler tab", async ({ page }) => {
    const keysTab = page.getByRole("tab", { name: /api|nøgler/i })
      .or(page.getByRole("button", { name: /api|nøgler/i }));
    await expect(keysTab).toBeVisible();
  });
});
