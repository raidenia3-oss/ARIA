import { chromium } from "playwright";
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  page.on('console', msg => console.log('CONSOLE:', msg.type(), msg.text()));
  page.on('pageerror', err => console.log('PAGEERROR:', err.message));
  await page.goto("http://localhost:3000/ame/ame_core", { waitUntil: "networkidle", timeout: 60000 });
  await page.waitForTimeout(8000);
  
  const domInfo = await page.evaluate(() => {
    const all = document.querySelectorAll('*');
    const visible = [];
    for (const el of all) {
      const style = window.getComputedStyle(el);
      if (style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0') {
        visible.push({
          tag: el.tagName,
          id: el.id,
          class: el.className,
          text: el.innerText?.slice(0, 100),
          children: el.children.length,
        });
      }
    }
    return {
      total: all.length,
      visibleCount: visible.length,
      visible: visible.slice(0, 30),
      bodyHTML: document.body.innerHTML.slice(0, 2000),
    };
  });
  
  console.log('DOM info:', JSON.stringify(domInfo, null, 2));
  await browser.close();
})();
