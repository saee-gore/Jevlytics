// Live mode checks. Needs the API running and a valid token in TOKEN_FILE (one line, the bare token).
//   APP_URL=http://localhost:3000 TOKEN_FILE=./token.txt node e2e/live-flows.mjs
import fs from "node:fs";
import { bodyText, launch, pageUrl } from "./_common.mjs";

const BASE = process.env.APP_URL ?? "http://localhost:3000";
const token = fs.readFileSync(process.env.TOKEN_FILE ?? "./token.txt", "utf8").trim();
const browser = await launch();
const page = await browser.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
const out = {};

// Store the token the same way the Settings page does, then use the app normally.
await page.goto(pageUrl(BASE, "/settings"), { waitUntil: "networkidle0" });
await page.evaluate((t) => sessionStorage.setItem("mpa_access_token", t), token);

await page.goto(pageUrl(BASE, "/activity"), { waitUntil: "networkidle0" });
await page.type("#question", "What was our decline rate last month?");
await page.click("button[type=submit]");
await page.waitForFunction(() => document.body.innerText.includes("Analytics is temporarily unavailable") || document.body.innerText.includes("answered"), { timeout: 60000 }).catch(() => {});
out.assistantResponded = (await bodyText(page)).includes("temporarily unavailable") || (await bodyText(page)).includes("Decline rate");

await page.goto(pageUrl(BASE, "/capabilities"), { waitUntil: "networkidle0" });
out.capabilitiesRows = await page.evaluate(() => document.querySelectorAll("tbody tr").length);

await page.goto(pageUrl(BASE, "/settings"), { waitUntil: "networkidle0" });
out.healthShown = (await bodyText(page)).includes("Database: ok") || (await bodyText(page)).includes("database");

out.pageErrors = errors;
console.log(JSON.stringify(out, null, 2));
await browser.close();
