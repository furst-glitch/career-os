/**
 * Global setup: log in once and persist auth state for all tests.
 * Requires env: TEST_USER_EMAIL, TEST_USER_PASSWORD
 */
import { test as setup, expect } from "@playwright/test";
import path from "path";

const AUTH_FILE = path.join(__dirname, "../playwright/.auth/user.json");

setup("authenticate", async ({ page }) => {
  const email = process.env.TEST_USER_EMAIL;
  const password = process.env.TEST_USER_PASSWORD;

  if (!email || !password) {
    throw new Error("TEST_USER_EMAIL and TEST_USER_PASSWORD must be set");
  }

  await page.goto("/login");
  await expect(page).toHaveTitle(/CareerOS/i, { timeout: 15_000 });

  await page.getByLabel(/e-mail|email/i).fill(email);
  await page.getByLabel(/adgangskode|password/i).fill(password);
  await page.getByRole("button", { name: /log ind|sign in|login/i }).click();

  // Wait for redirect to dashboard
  await expect(page).toHaveURL(/\/dashboard/, { timeout: 20_000 });

  await page.context().storageState({ path: AUTH_FILE });
});
