import { test, expect } from "@playwright/test";

test.describe("Login", () => {
  test.use({ storageState: { cookies: [], origins: [] } }); // fresh state

  test("shows login page at /login", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByRole("heading", { name: /log ind|login|sign in/i })).toBeVisible();
  });

  test("rejects invalid credentials", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel(/e-mail|email/i).fill("wrong@example.com");
    await page.getByLabel(/adgangskode|password/i).fill("wrongpassword");
    await page.getByRole("button", { name: /log ind|sign in|login/i }).click();
    // Should show error, not redirect
    await expect(page).not.toHaveURL(/\/dashboard/);
    await expect(page.getByText(/ugyldig|forkert|invalid|incorrect/i)).toBeVisible({ timeout: 10_000 });
  });

  test("authenticated user lands on dashboard", async ({ page }) => {
    // Auth state already set by global setup
    await page.goto("/");
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 15_000 });
    await expect(page.getByText(/dashboard/i).first()).toBeVisible();
  });
});
