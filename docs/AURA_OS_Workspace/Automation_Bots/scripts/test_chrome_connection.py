import asyncio
from playwright.async_api import async_playwright


async def test():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        print("Pestanas abiertas:")
        for ctx in browser.contexts:
            for page in ctx.pages:
                print(" -", page.url)
        await browser.close()


asyncio.run(test())
