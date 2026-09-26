import { chromium } from "playwright";
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  page.on('console', msg => console.log('CONSOLE:', msg.type(), msg.text()));
  page.on('pageerror', err => console.log('PAGEERROR:', err.message));
  await page.goto("http://localhost:3000/ame/ame_core", { waitUntil: "networkidle", timeout: 60000 });
  await page.waitForTimeout(5000);
  await page.screenshot({ path: "ame-debug4.png", fullPage: true });
  console.log("Body text:", await page.evaluate(() => document.body.innerText.slice(0, 500)));
  const inputCount = await page.locator('input[type="text"]').count();
  console.log("Input count:", inputCount);
  await browser.close();
})();
