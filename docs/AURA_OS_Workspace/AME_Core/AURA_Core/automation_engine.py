"""
AURA Automation Engine - Control de navegadores con Playwright
"""

import asyncio
import json
from playwright.async_api import async_playwright


class AutomationEngine:
    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None

    async def initialize(self):
        """Inicializa el navegador headless"""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=True)
        self.context = await self.browser.new_context()
        self.page = await self.context.new_page()
        return {"status": "initialized", "browser": "chromium", "headless": True}

    async def navigate(self, url: str):
        """Navega a una URL específica"""
        if not self.page:
            await self.initialize()
        await self.page.goto(url, wait_until="domcontentloaded")
        return {"url": self.page.url, "title": await self.page.title(), "status": "navigated"}

    async def capture_dom(self):
        """Captura el estado actual del DOM"""
        if not self.page:
            return {"error": "Browser not initialized"}

        content = await self.page.content()
        return {
            "url": self.page.url,
            "dom_length": len(content),
            "dom_preview": content[:2000],  # Primeros 2000 caracteres
        }

    async def screenshot(self):
        """Captura screenshot de la página actual"""
        if not self.page:
            return {"error": "Browser not initialized"}

        screenshot_bytes = await self.page.screenshot(full_page=False)
        import base64

        return {
            "screenshot": base64.b64encode(screenshot_bytes).decode("utf-8"),
            "url": self.page.url,
        }

    async def close(self):
        """Cierra el navegador"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        self.page = None
        self.context = None
        self.browser = None
        return {"status": "closed"}


# Instancia singleton
_engine = AutomationEngine()


async def get_engine() -> AutomationEngine:
    """Obtiene la instancia del motor de automatización"""
    return _engine
