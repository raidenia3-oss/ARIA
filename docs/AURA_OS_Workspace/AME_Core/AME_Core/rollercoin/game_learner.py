"""
Sistema de aprendizaje de selectores para RollerCoin.
Escanea el DOM real y actualiza los selectores automaticamente.
"""

import asyncio
import json
import re
from pathlib import Path
from playwright.async_api import Page

LEARNED_FILE = Path("AME_Core/rollercoin/learned_selectors.json")


class GameLearner:
    def __init__(self):
        self.data = self._load()

    def _load(self) -> dict:
        if LEARNED_FILE.exists():
            try:
                return json.loads(LEARNED_FILE.read_text())
            except Exception:
                pass
        return {
            "game_cards": [],
            "play_buttons": [],
            "cooldown_elements": [],
            "game_urls": {},
            "last_scan": None,
        }

    def save(self):
        LEARNED_FILE.write_text(json.dumps(self.data, indent=2, ensure_ascii=False))

    async def scan_games_page(self, page: Page) -> dict:
        """
        Escanea la pagina de juegos y detecta juegos jugables.
        Retorna dict con 'games', 'total', 'playable'.
        """
        print("[GameLearner] Escaneando pagina de juegos...")

        await page.goto("https://rollercoin.com/game/games")
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(4)

        games_found = []

        # Estrategia 1: selectores conocidos
        known_patterns = [
            "[class*='game-card']",
            "[class*='GameCard']",
            "[class*='game-item']",
            "[class*='mini-game']",
            "[class*='game-task']",
            "[class*='gameCard']",
            "[class*='game-container'] > div",
        ]

        for pattern in known_patterns:
            cards = await page.query_selector_all(pattern)
            if len(cards) >= 2:
                print(f"[GameLearner] Patron OK: {pattern} ({len(cards)} elementos)")
                self.data["game_cards"].append(pattern)

                for card in cards:
                    info = await self._extract_game_info(card, page)
                    if info:
                        games_found.append(info)

                if games_found:
                    break

        # Estrategia 2: botones Play
        if not games_found:
            print("[GameLearner] Buscando por botones Play...")
            buttons = await page.query_selector_all("button, a")

            for btn in buttons:
                try:
                    txt = (await btn.inner_text()).strip().lower()
                    if txt in ["play", "jugar", "play now", "start"]:
                        info = await self._extract_game_info_js(btn, page)
                        if info:
                            games_found.append(info)
                except Exception:
                    continue

        # Estrategia 3: links de juegos
        if not games_found:
            print("[GameLearner] Buscando por URLs de juegos...")
            links = await page.query_selector_all("a[href*='/game/']")
            for link in links:
                try:
                    href = await link.get_attribute("href") or ""
                    txt = (await link.inner_text()).strip()
                    if href and "/game/" in href and txt:
                        games_found.append(
                            {
                                "name": txt[:50],
                                "url": f"https://rollercoin.com{href}",
                                "cooldown_sec": 0,
                                "playable": True,
                                "selector": "link",
                            }
                        )
                        self.data["game_urls"][txt] = href
                except Exception:
                    continue

        # Guardar datos aprendidos
        self.data["last_scan"] = asyncio.get_event_loop().time()
        self.save()

        print(f"[GameLearner] Juegos detectados: {len(games_found)}")
        for g in games_found:
            print(
                f"  - {g['name']} | cooldown: {g['cooldown_sec']}s | " f"jugable: {g['playable']}"
            )

        return {
            "games": games_found,
            "total": len(games_found),
            "playable": sum(1 for g in games_found if g["playable"]),
        }

    async def _extract_game_info(self, card, page: Page) -> dict | None:
        """Extrae nombre, cooldown y estado de un card de juego."""
        try:
            full_text = (await card.inner_text()).strip()

            # Nombre
            name = ""
            for sel in [
                "h3",
                "h4",
                "[class*=name]",
                "[class*=title]",
                "strong",
                "b",
                "p:first-child",
            ]:
                try:
                    el = await card.query_selector(sel)
                    if el:
                        name = (await el.inner_text()).strip()
                        if len(name) > 2:
                            break
                except Exception:
                    continue

            if not name:
                lines = [l.strip() for l in full_text.split("\n") if l.strip()]
                name = lines[0][:50] if lines else "Juego desconocido"

            # Cooldown
            cooldown_sec = 0
            for sel in [
                "[class*=timer]",
                "[class*=cooldown]",
                "[class*=countdown]",
                "span:has-text(':')",
            ]:
                try:
                    el = await card.query_selector(sel)
                    if el:
                        timer_txt = (await el.inner_text()).strip()
                        cooldown_sec = self._parse_time(timer_txt)
                        break
                except Exception:
                    continue

            # Boton Play
            playable = False
            play_url = None
            for sel in [
                "button:has-text('Play')",
                "button:has-text('PLAY')",
                "a:has-text('Play')",
                "button:not([disabled])",
            ]:
                try:
                    btn = await card.query_selector(sel)
                    if btn:
                        enabled = await btn.is_enabled()
                        visible = await btn.is_visible()
                        if enabled and visible:
                            playable = True
                            href = await btn.get_attribute("href")
                            if href:
                                play_url = f"https://rollercoin.com{href}"
                            break
                except Exception:
                    continue

            return {
                "name": name,
                "cooldown_sec": cooldown_sec,
                "playable": playable,
                "url": play_url,
                "selector": "card",
            }
        except Exception:
            return None

    async def _extract_game_info_js(self, btn, page: Page) -> dict | None:
        """Extrae info corta de un boton de juego."""
        try:
            href = await btn.get_attribute("href") or ""
            txt = (await btn.inner_text()).strip()
            return {
                "name": txt or "Juego",
                "cooldown_sec": 0,
                "playable": True,
                "url": f"https://rollercoin.com{href}" if href else None,
                "selector": "button",
            }
        except Exception:
            return None

    def _parse_time(self, text: str) -> int:
        """Convierte '4:32' o '1:23:45' a segundos."""
        if not text:
            return 0
        match = re.search(r"(\d+):(\d+)(?::(\d+))?", text)
        if match:
            parts = [int(x) for x in match.groups() if x is not None]
            if len(parts) == 3:
                return parts[0] * 3600 + parts[1] * 60 + parts[2]
            elif len(parts) == 2:
                return parts[0] * 60 + parts[1]
        return 0
