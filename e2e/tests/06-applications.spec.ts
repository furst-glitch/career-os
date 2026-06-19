import { test, expect } from "@playwright/test";

test.describe("Applications Pipeline", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/applications");
  });

  test("applications page loads", async ({ page }) => {
    await expect(page.getByRole("heading", { name: /ansøgninger|applications/i })).toBeVisible({ timeout: 15_000 });
  });

  test("shows pipeline status columns or list", async ({ page }) => {
    // Either kanban columns or a list view
    const hasList = await page.getByRole("table").isVisible().catch(() => false);
    const hasKanban = await page.locator("[data-status], [class*='pipeline'], [class*='kanban']").first().isVisible().catch(() => false);
    const hasEmpty = await page.getByText(/ingen ansøgninger|no applications|kom i gang/i).isVisible().catch(() => false);
    expect(hasList || hasKanban || hasEmpty).toBeTruthy();
  });
});
