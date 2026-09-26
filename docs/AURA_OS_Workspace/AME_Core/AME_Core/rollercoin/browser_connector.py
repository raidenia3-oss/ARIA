"""
browser_connector.py - Conexion a navegador existente.
Se conecta a Chrome en modo debug (puerto 9222).
"""

import asyncio
import sys

from playwright.async_api import async_playwright


class BrowserConnector:
    """Se conecta al navegador Chrome ya abierto via CDP."""

    DEBUG_PORT = 9222

    def __init__(self):
        self.playwright = None
        self.browser = None
        self.page = None

    async def connect_to_existing_browser(self) -> bool:
        """
        Se conecta al navegador ya abierto via CDP (Chrome DevTools Protocol).
        Busca una pestana con 'rollercoin.com' en la URL.
        Retorna True si se conecto exitosamente.
        """
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.connect_over_cdp(
                f"http://localhost:{self.DEBUG_PORT}"
            )

            # Buscar pestana con RollerCoin
            for context in self.browser.contexts:
                for page in context.pages:
                    if "rollercoin.com" in page.url:
                        self.page = page
                        print(f"Conectado a pestana RollerCoin: {page.url}")
                        return True

            # Si no encontro RollerCoin, usar la primera pestana disponible
            if self.browser.contexts:
                ctx = self.browser.contexts[0]
                if ctx.pages:
                    self.page = ctx.pages[0]
                    print(f"RollerCoin no encontrado, usando: {self.page.url}")
                    print("   Navega a rollercoin.com en el navegador")
                    return True

            print("No hay pestanas abiertas en el navegador")
            return False

        except Exception as e:
            print(f"No se pudo conectar al navegador: {e}")
            print("\n   SOLUCION:")
            print("   1. Ejecuta primero: python scripts/launch_chrome_debug.py")
            print("   2. Entra a rollercoin.com en ese Chrome")

    async def handle_login_if_needed(self, gmail) -> bool:
        """
        Si la pagina actual es /sign-in o /login, espera a que el usuario
        inicie sesion manualmente. Retorna True cuando detecta que ya
        hay sesion iniciada (URL cambia a algo distinto de sign-in/login).
        """
        try:
            current_url = self.page.url
            if "sign-in" not in current_url and "login" not in current_url:
                return True

            print("\nDetectada pagina de login")
            print("   Por favor, inicia sesion en el navegador.")
            print("   El sistema esperara hasta que entres a RollerCoin...")

            timeout = 300  # 5 minutos
            step = 2
            elapsed = 0

            while elapsed < timeout:
                await asyncio.sleep(step)
                elapsed += step
                try:
                    url = self.page.url
                    if "sign-in" not in url and "login" not in url:
                        print(f"Sesion iniciada detectada despues de {elapsed}s")
                        return True
                except Exception:
                    pass

            print("Timeout esperando login")
            return False

        except Exception as e:
            print(f"❌ Error en handle_login_if_needed: {e}")
            return False

    async def ensure_on_rollercoin(self) -> bool:
        """Verifica que estamos en RollerCoin, si no navega alla."""
        if not self.page:
            return False
        if "rollercoin.com" not in self.page.url:
            try:
                await self.page.goto("https://rollercoin.com/game")
                await self.page.wait_for_load_state("networkidle")
            except Exception as e:
                print(f"Error navegando a RollerCoin: {e}")
                return False
        return "rollercoin.com" in self.page.url

    async def get_page(self):
        """Retorna la pagina actual del navegador."""
        return self.page

    async def close(self):
        """Cierra la conexion con Playwright."""
        if self.playwright:
            await self.playwright.stop()
