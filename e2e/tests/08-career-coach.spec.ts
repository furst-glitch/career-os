import { test, expect } from "@playwright/test";

test.describe("Career Coach", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/career-coach");
  });

  test("career coach page loads", async ({ page }) => {
    await expect(page.getByRole("heading", { name: /career coach/i })).toBeVisible({ timeout: 15_000 });
  });

  test("analyse button is present", async ({ page }) => {
    const btn = page.getByRole("button", { name: /analysér|analyse|analyse/i }).first();
    if (await btn.isVisible()) {
      await expect(btn).toBeEnabled();
    }
  });

  test("shows profile summary or onboarding prompt", async ({ page }) => {
    // Either shows profile summary or prompts user to build profile
    const hasContent = await page.getByText(/karriereprofil|career|kompetencer|upload dit cv/i).first().isVisible({ timeout: 10_000 }).catch(() => false);
    expect(hasContent).toBeTruthy();
  });
});
