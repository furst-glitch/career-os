import { test, expect } from "@playwright/test";
import path from "path";
import fs from "fs";

const FIXTURE_CV = path.join(__dirname, "../fixtures/sample-cv.pdf");

test.describe("CV Upload", () => {
  test.beforeAll(() => {
    // Create a minimal valid PDF fixture if not present
    if (!fs.existsSync(path.dirname(FIXTURE_CV))) {
      fs.mkdirSync(path.dirname(FIXTURE_CV), { recursive: true });
    }
    if (!fs.existsSync(FIXTURE_CV)) {
      // Minimal valid PDF (Acrobat-compatible header + body)
      const minPdf =
        "%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n" +
        "2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n" +
        "3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n" +
        "xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n" +
        "0000000058 00000 n \n0000000115 00000 n \n" +
        "trailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF";
      fs.writeFileSync(FIXTURE_CV, minPdf);
    }
  });

  test("CV upload page loads", async ({ page }) => {
    await page.goto("/cv");
    await expect(page.getByRole("heading", { name: /cv|upload/i }).first()).toBeVisible();
  });

  test("upload zone accepts PDF", async ({ page }) => {
    await page.goto("/cv");
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(FIXTURE_CV);
    // Should show file name or uploading state
    await expect(page.getByText(/sample-cv|uploading|behandler|parsing/i).first()).toBeVisible({ timeout: 10_000 });
  });
});
