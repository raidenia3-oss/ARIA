import { chromium } from "playwright";
import fs from "fs";
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.goto("http://localhost:3000/ame/ame_core", { waitUntil: "networkidle", timeout: 60000 });
  await page.screenshot({ path: "ame-debug.png", fullPage: true });
  const html = await page.content();
  fs.writeFileSync("ame-debug.html", html);
  console.log("HTML length:", html.length);
  console.log("Has input:", html.includes('type="text"'));
  console.log("Has Escribe tu mensaje:", html.includes("Escribe tu mensaje"));
  await browser.close();
})();
