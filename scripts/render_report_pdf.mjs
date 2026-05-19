import { existsSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const [htmlPathArg, pdfPathArg] = process.argv.slice(2);

if (!htmlPathArg || !pdfPathArg) {
  console.error("usage: node scripts/render_report_pdf.mjs <report.html> <report.pdf>");
  process.exit(2);
}

const htmlPath = path.resolve(htmlPathArg);
const pdfPath = path.resolve(pdfPathArg);

if (!existsSync(htmlPath)) {
  console.error(`HTML report does not exist: ${htmlPath}`);
  process.exit(2);
}

let chromium;
try {
  ({ chromium } = await import("playwright"));
} catch (error) {
  console.error(`Playwright is not available: ${error?.message ?? error}`);
  process.exit(3);
}

let browser;
try {
  browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({
    viewport: { width: 1280, height: 1600 },
    deviceScaleFactor: 1,
  });
  await page.goto(pathToFileURL(htmlPath).href, { waitUntil: "networkidle" });
  await page.pdf({
    path: pdfPath,
    format: "Letter",
    printBackground: true,
    displayHeaderFooter: false,
    margin: {
      top: "0.55in",
      right: "0.55in",
      bottom: "0.55in",
      left: "0.55in",
    },
  });
} catch (error) {
  console.error(`Failed to render PDF: ${error?.message ?? error}`);
  process.exit(4);
} finally {
  if (browser) {
    await browser.close();
  }
}
