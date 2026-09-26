import { chromium } from "playwright";
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  page.on('console', msg => {
    if (msg.type() === 'error') console.log('CONSOLE ERROR:', msg.text());
  });
  await page.goto("http://localhost:3000/ame/ame_core", { waitUntil: "networkidle", timeout: 60000 });
  await page.waitForTimeout(5000);
  console.log('Body text:', await page.evaluate(() => document.body.innerText.slice(0, 500)));
  const inputCount = await page.locator('input[type="text"]').count();
  console.log('Input count:', inputCount);
  await browser.close();
})();
