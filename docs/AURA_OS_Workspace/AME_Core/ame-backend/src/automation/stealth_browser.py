"""
Stealth browser automation with anti-detection for AURA backend.
"""

from __future__ import annotations

import os
import random
import string
import time
from typing import Optional, Dict, Any

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from .humanizer import smart_delay, human_type, human_click


class StealthBrowser:
    def __init__(self, headless: bool = True) -> None:
        self.headless = headless
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def start(self) -> None:
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
            ],
        )

        user_agent = self._random_user_agent()
        viewport = self._random_viewport()

        self.context = await self.browser.new_context(
            user_agent=user_agent,
            viewport=viewport,
            locale="en-US",
            timezone_id="America/New_York",
            permissions=["geolocation"],
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "DNT": "1",
            },
        )

        self.page = await self.context.new_page()

        await self._inject_stealth_scripts()
        await self._mask_webdriver()
        await self._spoof_canvas()
        await self._spoof_webgl()
        await self._spoof_plugins()
        await self._spoof_permissions()

    def _random_user_agent(self) -> str:
        agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        ]
        return random.choice(agents)

    def _random_viewport(self) -> Dict[str, int]:
        widths = [1366, 1440, 1536, 1920, 1600, 1680]
        heights = [768, 900, 864, 1080, 1050, 1050]
        return {"width": random.choice(widths), "height": random.choice(heights)}

    async def _inject_stealth_scripts(self) -> None:
        if not self.page:
            return

        await self.page.add_init_script("""
            // Override navigator properties
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });

            // Mock permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );

            // Override chrome runtime
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };

            // Override permissions API
            const originalRequest = window.navigator.permissions.request;
            window.navigator.permissions.request = (parameter) => (
                parameter.name === 'clipboard-read' ?
                    Promise.resolve({ state: 'granted' }) :
                    originalRequest(parameter)
            );
        """)

    async def _mask_webdriver(self) -> None:
        if not self.page:
            return
        await self.page.add_init_script("""
            // Remove webdriver flags
            delete navigator.__proto__.webdriver;
            window.navigator.webdriver = false;

            // Override automation-related properties
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
                configurable: true
            });

            // Mock automation detect
            window.navigator.automation = false;
        """)

    async def _spoof_canvas(self) -> None:
        if not self.page:
            return
        await self.page.add_init_script("""
            // Canvas fingerprinting protection
            const originalGetImageData = CanvasRenderingContext2D.prototype.getImageData;
            CanvasRenderingContext2D.prototype.getImageData = function(x, y, w, h) {
                const imageData = originalGetImageData.call(this, x, y, w, h);
                const data = imageData.data;
                for (let i = 0; i < data.length; i += 4) {
                    data[i] = data[i] + (Math.random() - 0.5) * 2;
                    data[i + 1] = data[i + 1] + (Math.random() - 0.5) * 2;
                    data[i + 2] = data[i + 2] + (Math.random() - 0.5) * 2;
                }
                return imageData;
            };

            // Add noise to canvas text rendering
            const originalFillText = CanvasRenderingContext2D.prototype.fillText;
            CanvasRenderingContext2D.prototype.fillText = function(text, x, y, maxWidth) {
                const noise = (Math.random() - 0.5) * 0.5;
                return originalFillText.call(this, text, x + noise, y + noise, maxWidth);
            };
        """)

    async def _spoof_webgl(self) -> None:
        if not self.page:
            return
        await self.page.add_init_script("""
            // WebGL fingerprinting protection
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) {
                    return 'Intel Inc.';
                }
                if (parameter === 37446) {
                    return 'Intel Iris Xe Graphics';
                }
                return getParameter.call(this, parameter);
            };

            // Add slight variations to WebGL renderer
            const originalReadPixels = WebGLRenderingContext.prototype.readPixels;
            WebGLRenderingContext.prototype.readPixels = function(x, y, w, h, format, type, pixels) {
                originalReadPixels.call(this, x, y, w, h, format, type, pixels);
                if (Math.random() > 0.9) {
                    for (let i = 0; i < pixels.length; i++) {
                        pixels[i] = pixels[i] ^ (Math.random() * 5);
                    }
                }
            };
        """)

    async def _spoof_plugins(self) -> None:
        if not self.page:
            return
        await self.page.add_init_script("""
            // Mock plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                    { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                    { name: 'Native Client', filename: 'internal-nacl-plugin' },
                ]
            });
        """)

    async def _spoof_permissions(self) -> None:
        if not self.page:
            return
        await self.page.add_init_script("""
            // Override permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (params) => {
                if (params.name === 'notifications' || params.name === 'geolocation') {
                    return Promise.resolve({ state: 'granted', onchange: null });
                }
                return originalQuery(params);
            };
        """)

    async def open(self, url: str) -> None:
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")

        await smart_delay(1.0, 3.0)
        await self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await smart_delay(0.5, 1.5)

    async def click(self, selector: str) -> None:
        if not self.page:
            raise RuntimeError("Browser not started")
        await self.page.wait_for_selector(selector, state="visible", timeout=30000)
        await human_click(self.page, selector)

    async def type_text(self, selector: str, text: str) -> None:
        if not self.page:
            raise RuntimeError("Browser not started")
        await self.page.wait_for_selector(selector, state="visible", timeout=30000)
        await human_type(self.page, selector, text)

    async def solve_captcha(
        self, site_key: str, page_url: str, captcha_type: str = "recaptcha"
    ) -> Optional[str]:
        from .captcha_solver import solve_challenge

        return await solve_challenge(site_key, page_url, captcha_type)

    async def inject_captcha_token(
        self, token: str, selector: str = "textarea[name='g-recaptcha-response']"
    ) -> None:
        if not self.page:
            raise RuntimeError("Browser not started")
        await self.page.evaluate(f"document.querySelector('{selector}').value = '{token}';")
        await self.page.dispatch_event(selector, "change")

    async def close(self) -> None:
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
