import { chromium } from "playwright";
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const resources = [];
  page.on('response', async (r) => {
    const url = r.url();
    if (url.includes('_next/static/chunks/app/ame')) {
      resources.push({ url, status: r.status(), size: await r.body().then(b => b.length).catch(() => -1) });
    }
  });
  await page.goto("http://localhost:3000/ame/ame_core", { waitUntil: "networkidle", timeout: 60000 });
  await page.waitForTimeout(5000);
  console.log('AME page resources:', resources);
  const allJs = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('script')).map(s => s.src || 'inline').slice(0, 20);
  });
  console.log('Scripts:', allJs);
  await browser.close();
})();
