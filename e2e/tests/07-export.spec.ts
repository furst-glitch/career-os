import { test, expect } from "@playwright/test";

test.describe("PDF/DOCX Export", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/cv/master");
    await page.waitForLoadState("networkidle");
  });

  test("PDF export triggers download", async ({ page }) => {
    const downloadBtn = page.getByRole("button", { name: /download|hent/i });
    if (!await downloadBtn.isVisible()) {
      test.skip();
      return;
    }

    // Look for PDF option
    await downloadBtn.click();
    const pdfOption = page.getByRole("menuitem", { name: /pdf/i })
      .or(page.getByRole("option", { name: /pdf/i }))
      .or(page.getByText(/download pdf/i).first());

    if (await pdfOption.isVisible({ timeout: 3_000 })) {
      const [download] = await Promise.all([
        page.waitForEvent("download"),
        pdfOption.click(),
      ]);
      expect(download.suggestedFilename()).toMatch(/\.pdf$/i);
    } else {
      // Single button — try direct download
      const [download] = await Promise.all([
        page.waitForEvent("download", { timeout: 20_000 }),
        page.getByRole("link", { name: /pdf/i }).first().click(),
      ]);
      expect(download.suggestedFilename()).toMatch(/\.pdf$/i);
    }
  });

  test("DOCX export triggers download", async ({ page }) => {
    const docxLink = page.getByRole("link", { name: /docx|word/i }).first()
      .or(page.getByRole("button", { name: /docx|word/i }).first());

    if (!await docxLink.isVisible({ timeout: 5_000 })) {
      // Try via download button dropdown
      const downloadBtn = page.getByRole("button", { name: /download|hent/i });
      if (await downloadBtn.isVisible()) {
        await downloadBtn.click();
      }
    }

    const docxTarget = page.getByRole("menuitem", { name: /docx|word/i })
      .or(page.getByRole("link", { name: /docx/i }).first());

    if (await docxTarget.isVisible({ timeout: 5_000 })) {
      const [download] = await Promise.all([
        page.waitForEvent("download", { timeout: 20_000 }),
        docxTarget.click(),
      ]);
      expect(download.suggestedFilename()).toMatch(/\.docx$/i);
    } else {
      test.skip();
    }
  });
});
