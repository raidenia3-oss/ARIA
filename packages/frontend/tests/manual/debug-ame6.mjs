import { chromium } from "playwright";
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  
  await page.addInitScript(() => {
    window.__errors = [];
    window.addEventListener('error', (e) => {
      window.__errors.push({ type: 'error', msg: e.message, filename: e.filename, lineno: e.lineno });
    });
    window.addEventListener('unhandledrejection', (e) => {
      window.__errors.push({ type: 'unhandledrejection', msg: e.reason?.message || String(e.reason) });
    });
  });
  
  page.on('console', msg => {
    if (msg.type() === 'error') console.log('CONSOLE ERROR:', msg.text());
  });
  
  await page.goto("http://localhost:3000/ame/ame_core", { waitUntil: "networkidle", timeout: 60000 });
  await page.waitForTimeout(8000);
  
  const errors = await page.evaluate(() => window.__errors || []);
  console.log('Errors captured:', JSON.stringify(errors, null, 2));
  
  const reactRoot = await page.evaluate(() => {
    const root = document.querySelector('#root') || document.querySelector('[data-reactroot]') || document.querySelector('#__next');
    return root ? root.innerHTML.slice(0, 500) : 'NO_REACT_ROOT';
  });
  console.log('React root:', reactRoot);
  
  await browser.close();
})();
