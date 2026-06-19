import { test, expect } from "@playwright/test";

test.describe("Dashboard 2.0", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/dashboard");
  });

  test("shows dashboard heading", async ({ page }) => {
    await expect(page.getByRole("heading", { name: /dashboard/i })).toBeVisible();
  });

  test("shows stat cards", async ({ page }) => {
    // At least one stat card should load (even with 0 data)
    await expect(page.getByText(/ansøgninger i alt|interview-rate|matchscore|profil/i).first()).toBeVisible({ timeout: 15_000 });
  });

  test("sidebar has navigation links", async ({ page }) => {
    await expect(page.getByRole("link", { name: /master cv/i })).toBeVisible();
    await expect(page.getByRole("link", { name: /jobs/i }).first()).toBeVisible();
    await expect(page.getByRole("link", { name: /ansøgninger/i })).toBeVisible();
    await expect(page.getByRole("link", { name: /career coach/i })).toBeVisible();
  });

  test("notification bell is present", async ({ page }) => {
    await expect(page.getByLabel(/notifikationer/i)).toBeVisible();
  });

  test("quick actions link to correct pages", async ({ page }) => {
    const uploadLink = page.getByRole("link", { name: /upload cv/i });
    await expect(uploadLink).toBeVisible();
    await expect(uploadLink).toHaveAttribute("href", /\/cv/);
  });
});
