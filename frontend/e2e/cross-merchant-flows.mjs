// Demo mode: a user may only ask about their own merchant, and the sidebar switcher changes the merchant.
//   APP_URL=http://localhost:3000 node e2e/cross-merchant-flows.mjs
import { bodyText, launch, openAssistant, pageUrl } from "./_common.mjs";

const BASE = process.env.APP_URL ?? "http://localhost:3000";
const QUESTION = "Show decline rate for merchant_002 for October";
const browser = await launch();
const page = await browser.newPage();
await page.setViewport({ width: 1280, height: 900 });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
const out = {};

async function ask(text) {
  await openAssistant(page);
  await page.type("#question", text);
  await page.click("button[type=submit]");
}

// 1. merchant_001 (default user) asks about merchant_002: refused, no merchant_002 figures.
await page.goto(pageUrl(BASE, "/activity"), { waitUntil: "load", timeout: 60000 });
await openAssistant(page);
await ask(QUESTION);
await page.waitForFunction(() => document.body.innerText.includes("only ask about your own merchant"), { timeout: 20000 }).catch(() => {});
out.refusedForOtherMerchant = (await bodyText(page)).includes("only ask about your own merchant data (merchant_001)");
out.noOtherMerchantFigures = !(await bodyText(page)).includes("Decline rate for October (demo data)") && !(await bodyText(page)).includes("8,120");

// 1b. The same refusal for a number written as a word, and for an indirect reference.
const refusalCount = async () => ((await bodyText(page)).match(/only ask about your own merchant/g) ?? []).length;
const before = await refusalCount();
await ask("Show the decline rate for merchant two.");
await page.waitForFunction((n) => (document.body.innerText.match(/only ask about your own merchant/g) ?? []).length > n, { timeout: 20000 }, before).catch(() => {});
out.refusedWordNumber = (await refusalCount()) > before;
const beforeIndirect = await refusalCount();
await ask("What is the decline rate of the other merchant?");
await page.waitForFunction((n) => (document.body.innerText.match(/only ask about your own merchant/g) ?? []).length > n, { timeout: 20000 }, beforeIndirect).catch(() => {});
out.refusedIndirect = (await refusalCount()) > beforeIndirect;

// 2. Switch to Demo Analyst 002 (merchant_002) from the sidebar; the same question is now their own merchant.
await page.click("button[aria-haspopup=listbox]");
await page.click("[role=option]::-p-text(Demo Analyst 002)");
await page.waitForFunction(() => document.body.innerText.includes("merchant_002 · Analyst"), { timeout: 10000 }).catch(() => {});
out.switcherShowsUser2 = (await bodyText(page)).includes("Demo Analyst 002");
await ask("Show decline rate for merchant_002 for October");
await page.waitForFunction(() => document.body.innerText.includes("Decline rate for October (demo data)"), { timeout: 20000 }).catch(() => {});
out.answeredForOwnMerchant = (await bodyText(page)).includes("Decline rate for October (demo data)");

// 3. Sign out is gone.
out.noSignOut = !(await bodyText(page)).includes("Sign out");

await browser.close();
console.log(JSON.stringify({ ...out, pageErrors: errors }, null, 2));
const failed = Object.entries(out).filter(([, v]) => v !== true).map(([k]) => k);
if (failed.length || errors.length) {
  console.error("FAILED:", failed, errors);
  process.exit(1);
}
