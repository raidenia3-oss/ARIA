import { chromium } from "playwright";
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const logs = [];
  page.on('console', msg => logs.push({ type: msg.type(), text: msg.text() }));
  page.on('pageerror', err => logs.push({ type: 'pageerror', text: err.message }));
  await page.goto("http://localhost:3000/ame/ame_core", { waitUntil: "networkidle", timeout: 60000 });
  await page.waitForTimeout(8000);
  await page.screenshot({ path: "ame-debug5.png", fullPage: true });
  console.log('Logs:', JSON.stringify(logs, null, 2));
  console.log('Body text:', await page.evaluate(() => document.body.innerText.slice(0, 500)));
  const inputCount = await page.locator('input[type="text"]').count();
  console.log('Input count:', inputCount);
  await browser.close();
})();
