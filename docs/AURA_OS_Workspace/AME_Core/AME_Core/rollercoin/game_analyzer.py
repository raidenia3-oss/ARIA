"""
game_analyzer.py - Analiza el estado del juego en RollerCoin.
Navega a rollercoin.com/game y detecta bateria, juegos, quests.
"""

import asyncio
import re
from typing import Any, Dict, List, Optional

# Selectores de bateria, ordenados por probabilidad de acierto
BATTERY_SELECTORS = [
    "button:has-text('Reload')",
    "button:has-text('Recharge')",
    "button:has-text('RELOAD')",
    "button:has-text('Refuel')",
    "button:has-text('Charge')",
    "[class*='battery'] button",
    "[class*='energy'] button",
    "[class*='fuel'] button",
    "[class*='reload']",
    "[class*='recharge']",
]


class GameAnalyzer:
    """Analiza el estado completo del juego en RollerCoin."""

    def __init__(self, page, kb=None):
        self.page = page
        self.kb = kb

    async def analyze_full_state(self) -> Dict[str, Any]:
        """Analiza el estado: bateria, juegos, quests, hashrate."""
        result = {"games": [], "battery": 0, "quests": [], "hashrate": "0 H/s"}

        try:
            current_url = self.page.url
            if "/game" not in current_url:
                await self.page.goto("https://rollercoin.com/game", wait_until="networkidle")
                await asyncio.sleep(2)

            result["battery"] = await self._get_battery_status()
            result["hashrate"] = await self._get_hashrate()
            result["games"] = await self._get_games()
            result["quests"] = await self._get_quests()

        except Exception as e:
            print(f"Error en analyze_full_state: {e}")

        return result

    async def _get_battery_status(self) -> dict:
        """
        Detecta el estado real de la bateria mirando el DOM.
        Retorna dict con needs_reload y button_enabled.
        """
        try:
            await self.page.goto("https://rollercoin.com/game")
            await self.page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)

            for sel in BATTERY_SELECTORS:
                try:
                    btn = await self.page.query_selector(sel)
                    if btn:
                        visible = await btn.is_visible()
                        enabled = await btn.is_enabled()
                        if visible:
                            return {
                                "needs_reload": True,
                                "button_enabled": enabled,
                                "selector_used": sel,
                            }
                except Exception:
                    continue

            # No se encontro boton = bateria llena
            return {"needs_reload": False, "button_enabled": False}

        except Exception as e:
            return {"needs_reload": False, "error": str(e)}

    async def _get_hashrate(self) -> str:
        """Obtiene el hashrate actual."""
        try:
            hr = await self.page.query_selector("[class*='hashrate'], [class*='hash']")
            if hr:
                return (await hr.inner_text()).strip()
        except Exception:
            pass
        return "0 H/s"

    async def _get_games(self) -> List[Dict[str, Any]]:
        """Detecta juegos usando el learner inteligente."""
        from game_learner import GameLearner

        learner = GameLearner()
        games: List[Dict[str, Any]] = []

        try:
            result = await learner.scan_games_page(self.page)
            raw_games = result.get("games", [])

            for g in raw_games:
                games.append(
                    {
                        "name": g.get("name", "Desconocido"),
                        "cooldown": (f"{g['cooldown_sec']}s" if g.get("cooldown_sec") else None),
                        "has_play_button": g.get("playable", False),
                        "url": g.get("url"),
                    }
                )

            if games:
                games.sort(key=lambda x: (0 if x["has_play_button"] else 1, 0))
                print(f"Juegos: {result['total']} total, " f"{result['playable']} disponibles")
                return games

            print("GameLearner no encontro juegos - usando fallback")
            return []

        except Exception as e:
            print(f"Error en scan con GameLearner: {e}")
            return []

    async def _extract_game_info(self, el) -> Optional[Dict[str, Any]]:
        """Extrae nombre, cooldown y boton de un elemento de juego."""
        try:
            # Nombre
            name = None
            for s in [
                "[class*='name']",
                "[class*='title']",
                "h3",
                "h4",
                "[class*='gameTitle']",
                "[class*='game-name']",
            ]:
                ne = await el.query_selector(s)
                if ne:
                    name = (await ne.inner_text()).strip()
                    break
            if not name:
                name = (await el.inner_text()).strip()[:50]

            # Cooldown
            cooldown = None
            cd = await el.query_selector(
                "[class*='cooldown'], [class*='timer'], " "[class*='countdown'], span"
            )
            if cd:
                t = (await cd.inner_text()).strip()
                if re.search(r"\d+:\d+", t):
                    cooldown = t

            # Boton Play
            play = await el.query_selector(
                "button:has-text('Play'), a:has-text('Play'), " "button:has-text('PLAY')"
            )

            return {
                "name": name or "Desconocido",
                "cooldown": cooldown,
                "has_play_button": play is not None,
            }
        except Exception:
            return None

    async def _get_quests(self) -> List[str]:
        """Obtiene quests activos."""
        quests = []
        try:
            for el in await self.page.query_selector_all(
                "[class*='quest'], [class*='mission'], " "[class*='task'], [class*='daily']"
            ):
                try:
                    t = (await el.inner_text()).strip()
                    if t:
                        quests.append(t[:100])
                except Exception:
                    continue
        except Exception:
            pass
        return quests
