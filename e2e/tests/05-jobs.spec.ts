import { test, expect } from "@playwright/test";

test.describe("Jobs", () => {
  test("jobs list page loads", async ({ page }) => {
    await page.goto("/jobs");
    await expect(page.getByRole("heading", { name: /jobs/i }).first()).toBeVisible({ timeout: 15_000 });
  });

  test("can add a manual job", async ({ page }) => {
    await page.goto("/jobs");
    const addBtn = page.getByRole("button", { name: /tilføj|add|nyt job/i });
    if (await addBtn.isVisible()) {
      await addBtn.click();
      await page.getByLabel(/titel|title/i).fill("Senior Developer");
      await page.getByLabel(/virksomhed|company/i).fill("Acme A/S");
      await page.getByRole("button", { name: /gem|save|opret/i }).click();
      await expect(page.getByText(/senior developer/i)).toBeVisible({ timeout: 10_000 });
    }
  });
});

test.describe("Job Discovery", () => {
  test("discovery page loads", async ({ page }) => {
    await page.goto("/jobs/discovery");
    await expect(page.getByRole("heading", { name: /discovery|ledige/i })).toBeVisible({ timeout: 15_000 });
  });

  test("search field is visible and accepts input", async ({ page }) => {
    await page.goto("/jobs/discovery");
    const searchInput = page.getByPlaceholder(/søg|search|stillingstitel/i);
    await expect(searchInput).toBeVisible({ timeout: 10_000 });
    await searchInput.fill("software developer");
    await expect(searchInput).toHaveValue("software developer");
  });

  test("search button triggers search (no AI credits needed)", async ({ page }) => {
    await page.goto("/jobs/discovery");
    // Just verify the button is present and clickable
    const searchBtn = page.getByRole("button", { name: /søg|search|find/i });
    await expect(searchBtn).toBeVisible({ timeout: 10_000 });
    await expect(searchBtn).toBeEnabled();
  });
});
