"""
Acciones concretas de RollerCoin (bateria, quests, etc).
Metodos cortos, cada uno < 80 lineas.
"""

import asyncio
import re

from playwright.async_api import Page

# Lista de selectores para el boton de recarga, ordenados por prioridad
BATTERY_SELECTORS = [
    "button:has-text('Reload')",
    "button:has-text('Recharge')",
    "button:has-text('Refuel')",
    "button:has-text('Charge')",
    "button:has-text('Fuel')",
    "[class*='reload'] button",
    "[class*='recharge'] button",
    "[class*='battery'] button",
    "[class*='fuel'] button",
    "[class*='power'] button",
    "button:has-text('Battery')",
]


class RollerCoinActions:
    """Acciones especificas de RollerCoin"""

    def __init__(self, page: Page):
        self.page = page

    async def reload_battery(self) -> bool:
        """
        Busca el boton de recarga de bateria con selectores
        en orden de prioridad. Si el boton existe pero esta
        disabled, la bateria ya esta llena y no se recarga.
        """
        try:
            await self.page.goto("https://rollercoin.com/game")
            await self.page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)

            # Buscar boton con la lista de selectores
            btn = None
            for sel in BATTERY_SELECTORS:
                try:
                    candidate = await self.page.query_selector(sel)
                    if candidate:
                        btn = candidate
                        break
                except Exception:
                    continue

            # Fallback: buscar entre todos los botones por texto
            if not btn:
                buttons = await self.page.query_selector_all("button")
                for b in buttons:
                    try:
                        txt = (await b.inner_text()).strip()
                        if re.search(r"reload|recharge|charge|fuel|refuel", txt, re.IGNORECASE):
                            btn = b
                            break
                    except Exception:
                        continue

            if not btn:
                print("ℹ️  No se encontro boton de recarga → bateria llena")
                return False

            # Verificar si esta deshabilitado
            disabled = await btn.get_attribute("disabled")
            enabled = await btn.is_enabled()
            if disabled or not enabled:
                print("ℹ️  Boton de recarga deshabilitado → bateria ya llena")
                return False

            await btn.click()
            await asyncio.sleep(2)
            print("✅ Bateria recargada")
            return True

        except Exception as e:
            print(f"❌ Error recargando bateria: {e}")
            return False

    async def claim_quests(self, quests: list) -> int:
        """Reclama recompensas de quests completadas"""
        claimed = 0
        try:
            await self.page.goto("https://rollercoin.com/game/quests")
            await self.page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)

            claim_buttons = await self.page.query_selector_all(
                "button:has-text('Claim'), button:has-text('Collect')"
            )
            for btn in claim_buttons:
                try:
                    await btn.click()
                    await asyncio.sleep(1)
                    claimed += 1
                except Exception:
                    continue

            if claimed:
                print(f"✅ {claimed} quests reclamadas")
        except Exception as e:
            print(f"❌ Error reclamando quests: {e}")
        return claimed

    async def navigate_to_games(self):
        """Navega a la seccion de juegos"""
        await self.page.goto("https://rollercoin.com/game/games")
        await self.page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)
