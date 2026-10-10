import type { Browser } from "playwright";

// Lazily-initialized, module-level singleton: launching a browser per
// request is slow (~1-2s cold start). This assumes web/ runs as a
// persistent Node process (npm run dev / next start), not a serverless
// function per invocation - true for this project's deployment.
let browserPromise: Promise<Browser> | null = null;

async function getBrowser(): Promise<Browser> {
  if (!browserPromise) {
    const { chromium } = await import("playwright");
    browserPromise = chromium.launch({ headless: true });
  }
  return browserPromise;
}

export interface ScreenshotResult {
  status: 200;
  body: Buffer;
}
export interface ScreenshotError {
  status: 404 | 503;
  detail: string;
}

/**
 * Screenshots one `data-*="true"` element from the non-interactive
 * /r/{run_id}/export page. Used by both the chart and stats PNG routes -
 * they differ only in which card's selector they ask for.
 */
export async function screenshotExportCard(
  origin: string,
  run_id: string,
  selector: string
): Promise<ScreenshotResult | ScreenshotError> {
  if (!/^[A-Za-z0-9_-]+$/.test(run_id)) {
    return { status: 404, detail: "Invalid run_id" };
  }

  const browser = await getBrowser();
  const page = await browser.newPage({ viewport: { width: 960, height: 1400 } });

  try {
    const response = await page.goto(`${origin}/r/${run_id}/export`, {
      waitUntil: "domcontentloaded",
      timeout: 10000,
    });

    if (response && response.status() === 404) {
      return { status: 404, detail: "Run was not found" };
    }

    const card = page.locator(selector);
    try {
      await card.waitFor({ state: "visible", timeout: 10000 });
    } catch {
      const notFound = await page.locator("text=/not found/i").count();
      return notFound > 0
        ? { status: 404, detail: "Run was not found" }
        : { status: 503, detail: "Card could not be rendered" };
    }

    const buffer = await card.screenshot({ type: "png" });
    return { status: 200, body: buffer };
  } catch (err) {
    console.error("screenshot failed:", err);
    return { status: 503, detail: "Card could not be rendered" };
  } finally {
    await page.close();
  }
}
