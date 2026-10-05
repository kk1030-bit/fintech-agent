// Headless screenshot helper for A's UI checks (W01–W04).
// Usage: node shoot.mjs plan.json
// plan.json: [{"url": "...", "width": 1440, "height": 900, "out": "x.png",
//              "fullPage": false, "wait_ms": 500, "click": "#selector", "type": ["#sel","text"],
//              "eval": "js expression run before the shot"}]
// Needs: npm i @sparticuz/chromium puppeteer-core (dev-only; not a runtime dependency).
import chromium from '@sparticuz/chromium';
import puppeteer from 'puppeteer-core';
import fs from 'node:fs';

const plan = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const browser = await puppeteer.launch({ args: chromium.args, executablePath: await chromium.executablePath(), headless: true });
const report = [];
for (const step of plan) {
  const page = await browser.newPage();
  await page.setViewport({ width: step.width, height: step.height, deviceScaleFactor: 1, isMobile: step.width < 768, hasTouch: step.width < 768 });
  if (step.localStorage) {
    await page.evaluateOnNewDocument(entries => { for (const [k, v] of Object.entries(entries)) localStorage.setItem(k, v); }, step.localStorage);
  }
  await page.goto(step.url, { waitUntil: 'networkidle0', timeout: 30000 }).catch(() => {});
  if (step.type) { await page.click(step.type[0], { clickCount: 3 }); await page.type(step.type[0], step.type[1]); }
  if (step.click) { for (const sel of [].concat(step.click)) { await page.click(sel); await new Promise(r => setTimeout(r, step.between_ms ?? 400)); } }
  if (step.eval) await page.evaluate(step.eval);
  await new Promise(r => setTimeout(r, step.wait_ms ?? 500));
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  await page.screenshot({ path: step.out, fullPage: !!step.fullPage });
  report.push({ out: step.out, url: step.url, viewport: `${step.width}x${step.height}`, horizontal_overflow_px: overflow, taken_at: new Date().toISOString() });
  await page.close();
}
await browser.close();
console.log(JSON.stringify(report, null, 1));
