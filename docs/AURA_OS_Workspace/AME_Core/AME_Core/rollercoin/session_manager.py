"""
Módulo RollerCoin para AURA
Gestiona la sesión de RollerCoin.
El usuario inicia sesión manualmente UNA VEZ,
el módulo guarda las cookies y las reutiliza.
"""

import asyncio
import json
import os
from pathlib import Path
from playwright.async_api import async_playwright, BrowserContext

COOKIES_PATH = Path("AME_Core/rollercoin/session_cookies.json")
BASE_URL = "https://rollercoin.com"


class SessionManager:
    """
    Gestiona la sesión de RollerCoin.
    El usuario inicia sesión manualmente UNA VEZ,
    el módulo guarda las cookies y las reutiliza.
    """

    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    async def start(self, headless=False):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=headless, args=["--no-sandbox"]
        )

        # Cargar cookies guardadas si existen
        if COOKIES_PATH.exists():
            cookies = json.loads(COOKIES_PATH.read_text())
            self.context = await self.browser.new_context()
            await self.context.add_cookies(cookies)
            print("✅ Sesión cargada desde cookies guardadas")
        else:
            self.context = await self.browser.new_context()
            print("ℹ️  No hay sesión guardada")

        self.page = await self.context.new_page()
        return self.page

    async def verify_session(self) -> bool:
        """Verifica si la sesión sigue activa"""
        await self.page.goto(f"{BASE_URL}/game")
        await self.page.wait_for_load_state("networkidle")

        # Si redirige al login, sesión expirada
        if "login" in self.page.url or "sign" in self.page.url:
            print("❌ Sesión expirada — necesitas iniciar sesión manualmente")
            return False
        print("✅ Sesión activa")
        return True

    async def manual_login_and_save(self):
        """
        Abre el navegador para que el usuario inicie sesión
        manualmente. Después guarda las cookies.
        """
        print("\n" + "=" * 50)
        print("INICIO DE SESIÓN MANUAL REQUERIDO")
        print("=" * 50)
        print("1. Se abrirá el navegador en RollerCoin")
        print("2. Inicia sesión manualmente (email + código)")
        print("3. Cuando estés dentro del juego, presiona Enter aquí")
        print("=" * 50 + "\n")

        await self.page.goto(f"{BASE_URL}/login")
        input("Presiona Enter cuando hayas iniciado sesión...")

        # Guardar cookies
        cookies = await self.context.cookies()
        COOKIES_PATH.parent.mkdir(parents=True, exist_ok=True)
        COOKIES_PATH.write_text(json.dumps(cookies, indent=2))
        print("✅ Cookies guardadas — no necesitarás loguear de nuevo")

    async def save_cookies(self):
        """Guarda cookies actuales (llamar después de cada sesión)"""
        cookies = await self.context.cookies()
        COOKIES_PATH.write_text(json.dumps(cookies, indent=2))

    async def close(self):
        await self.save_cookies()
        await self.browser.close()
        await self.playwright.stop()
