// Shared setup for the browser checks. Requires: npm i -D puppeteer-core, and a local Chrome.
import puppeteer from "puppeteer-core";

export const CHROME = process.env.CHROME_PATH ?? "/usr/bin/google-chrome";

export async function launch() {
  return puppeteer.launch({ executablePath: CHROME, headless: true, args: ["--no-sandbox", "--disable-gpu"] });
}

export function pageUrl(base, path) {
  return `${base}${path}`;
}

export async function bodyText(page) {
  return page.evaluate(() => document.body.innerText);
}

/** Opens the floating AI Assistant panel (closed by default) and waits for its input. */
export async function openAssistant(page) {
  const open = await page.$eval("#question", (el) => el.offsetParent !== null).catch(() => false);
  if (open) return;
  await page.click("button::-p-text(AI Assistant)");
  await page.waitForSelector("#question", { visible: true });
}
