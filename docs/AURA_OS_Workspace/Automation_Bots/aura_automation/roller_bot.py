#!/usr/bin/env python3
"""
roller_bot.py — Motor de automatización Rollercoin
Playwright con antidetect, movimientos humanos, OpenCV vision
"""

import asyncio
import json
import random
import time
import os
import logging
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("RollerBot")

# Intentar importar dependencias opcionales
try:
    import cv2
    import numpy as np

    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    log.warning("OpenCV no disponible, modo visión desactivado")

try:
    import pyautogui

    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False

try:
    from playwright.async_api import async_playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


class HumanMouse:
    """Simula movimientos de mouse realistas con curvas bezier"""

    @staticmethod
    async def move(page, x, y, steps=random.randint(8, 15)):
        """Mueve el mouse con trayectoria no lineal"""
        from playwright.async_api import Position

        for i in range(steps):
            px = x * (i / steps) + random.randint(-2, 2)
            py = y * (i / steps) + random.randint(-2, 2)
            await page.mouse.move(px, py)
            await asyncio.sleep(random.uniform(0.01, 0.04))

    @staticmethod
    async def click(page, x, y):
        """Click con pausa humana"""
        await HumanMouse.move(page, x, y)
        await asyncio.sleep(random.uniform(0.05, 0.15))
        await page.mouse.click(x, y)
        await asyncio.sleep(random.uniform(0.1, 0.3))


class VisionEngine:
    """Reconocimiento visual con OpenCV y templates"""

    def __init__(self):
        self.templates_dir = Path("aura_automation/templates")
        self.templates_dir.mkdir(exist_ok=True)
        self.templates = {}

    def load_template(self, name, path=None):
        """Carga una plantilla .png para matching"""
        if not CV2_AVAILABLE:
            return None
        p = path or str(self.templates_dir / f"{name}.png")
        if os.path.exists(p):
            tmpl = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
            self.templates[name] = tmpl
            return tmpl
        return None

    def find_template(self, screenshot_path, template_name, threshold=0.8):
        """Busca template en screenshot, retorna (x, y, w, h) o None"""
        if not CV2_AVAILABLE or template_name not in self.templates:
            return None
        screen = cv2.imread(screenshot_path, cv2.IMREAD_GRAYSCALE)
        if screen is None:
            return None
        res = cv2.matchTemplate(screen, self.templates[template_name], cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        if max_val >= threshold:
            h, w = self.templates[template_name].shape
            return (*max_loc, w, h)
        return None

    def capture_screenshot(self, page, path="screenshot.png"):
        """Toma screenshot de la página"""
        import asyncio

        return page.screenshot(path=path, full_page=False)


class RollerBot:
    """Bot principal Rollercoin con anti-detección"""

    def __init__(self, email="", password=""):
        self.email = email
        self.password = password
        self.browser = None
        self.page = None
        self.running = False
        self.stats = {"games_played": 0, "earnings": 0, "errors": 0}
        self.vision = VisionEngine()
        self._creds_path = Path("aura_automation/credentials.json")

        # Cargar credenciales si existen
        if self._creds_path.exists():
            try:
                creds = json.loads(self._creds_path.read_text())
                self.email = creds.get("email", email)
                self.password = creds.get("password", password)
            except Exception:
                pass

    async def start(self):
        """Inicia el bot con navegador stealth"""
        if not PLAYWRIGHT_AVAILABLE:
            log.error(
                "Playwright no instalado. pip install playwright && playwright install chromium"
            )
            return False

        self.running = True
        p = await async_playwright().start()

        # Configurar navegador con evasión de fingerprint
        self.browser = await p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--no-sandbox",
                f"--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            ],
        )

        ctx = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            timezone_id="America/New_York",
        )

        # Evadir detección de WebDriver
        await ctx.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        """)

        self.page = await ctx.new_page()
        log.info("Navegador iniciado con perfil stealth")
        return True

    async def login(self):
        """Inicia sesión en Rollercoin con interacciones humanas"""
        if not self.page:
            log.error("Bot no iniciado")
            return False

        log.info("Navegando a Rollercoin...")
        await self.page.goto("https://rollercoin.com/login", wait_until="networkidle")
        await asyncio.sleep(random.uniform(1, 3))

        # Email
        email_sel = 'input[type="email"], input[name="email"], input[placeholder*="email"]'
        try:
            await self.page.wait_for_selector(email_sel, timeout=10000)
            el = await self.page.query_selector(email_sel)
            if el:
                await el.click()
                await asyncio.sleep(random.uniform(0.2, 0.5))
                await el.fill(self.email, timeout=5000)
                log.info("Email ingresado")
        except Exception as e:
            log.warning(f"No se encontró campo email: {e}")

        await asyncio.sleep(random.uniform(0.5, 1.5))

        # Password
        pass_sel = 'input[type="password"]'
        try:
            await self.page.wait_for_selector(pass_sel, timeout=5000)
            el = await self.page.query_selector(pass_sel)
            if el:
                await el.click()
                await asyncio.sleep(random.uniform(0.2, 0.5))
                await el.fill(self.password, timeout=5000)
                log.info("Password ingresado")
        except Exception:
            log.warning("No se encontró campo password")

        # Click login
        btn_sel = 'button[type="submit"], button:has-text("Sign in"), button:has-text("Login")'
        try:
            btn = await self.page.query_selector(btn_sel)
            if btn:
                box = await btn.bounding_box()
                if box:
                    await HumanMouse.click(
                        self.page, box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
                    )
                log.info("Login clicked")
        except Exception as e:
            log.warning(f"Error en login: {e}")

        await asyncio.sleep(random.uniform(3, 6))
        return True

    async def play_games_loop(self, max_games=50):
        """Loop principal de juego"""
        while self.running:
            log.info(f"Juegos realizados: {self.stats['games_played']}")
            await asyncio.sleep(random.uniform(30, 60))
            self.stats["games_played"] += 1

            if self.stats["games_played"] >= max_games:
                log.info("Límite de juegos alcanzado")
                break

    async def stop(self):
        """Detiene el bot"""
        self.running = False
        if self.browser:
            await self.browser.close()
        log.info("Bot detenido")

    def get_status(self):
        """Estado actual del bot"""
        return {
            "running": self.running,
            "stats": self.stats,
            "vision_available": CV2_AVAILABLE,
        }

    def set_credentials(self, email, password):
        """Guarda credenciales"""
        self.email = email
        self.password = password
        self._creds_path.write_text(json.dumps({"email": email, "password": password}, indent=2))
        log.info("Credenciales guardadas")
