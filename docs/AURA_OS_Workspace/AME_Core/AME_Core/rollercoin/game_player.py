"""
Módulo RollerCoin para AURA
Ejecuta los mini-juegos automáticamente.
"""

import asyncio
import random
from playwright.async_api import Page


class GamePlayer:
    """
    Juega los mini-juegos de RollerCoin.
    Cada juego tiene su propia estrategia.
    """

    def __init__(self, page: Page):
        self.page = page
        self.results = []

    async def play_game(self, game: dict) -> dict:
        """Juega un mini-juego navegando a su URL directa"""
        name = game.get("name", "desconocido")
        url = game.get("url")
        result = {"game": name, "success": False, "clicks": 0}

        print(f"🎮 Iniciando: {name}")

        try:
            # Navegar al juego por URL si está disponible
            if url:
                await self.page.goto(url)
            else:
                # Buscar y hacer click en Play
                play_btn = await self.page.query_selector(
                    "button:has-text('Play'), a:has-text('Play')"
                )
                if play_btn:
                    await play_btn.click()

            await self.page.wait_for_load_state("networkidle")
            await asyncio.sleep(4)

            # Screenshot para debug
            await self.page.screenshot(path=f"AME_Core/rollercoin/game_{name[:20]}.png")

            # Detectar tipo de juego y ejecutar estrategia
            result = await self._auto_play(name.lower(), result)

            # Volver a la página de juegos
            await asyncio.sleep(2)
            await self.page.goto("https://rollercoin.com/game/games")
            await self.page.wait_for_load_state("networkidle")

        except Exception as e:
            result["error"] = str(e)
            print(f"❌ Error jugando {name}: {e}")
            # Volver a juegos aunque falle
            try:
                await self.page.goto("https://rollercoin.com/game/games")
            except Exception:
                pass

        return result

    async def _auto_play(self, game_name: str, result: dict) -> dict:
        """Selecciona y ejecuta la estrategia según el juego"""

        # Esperar a que el juego cargue
        await asyncio.sleep(2)

        # Estrategias por juego
        if any(word in game_name for word in ["token", "blaster", "coin", "shoot"]):
            return await self._strategy_clicker(result)

        elif any(word in game_name for word in ["match", "memory", "pair"]):
            return await self._strategy_memory(result)

        elif any(word in game_name for word in ["runner", "run", "jump"]):
            return await self._strategy_runner(result)

        elif any(word in game_name for word in ["puzzle", "slide", "block"]):
            return await self._strategy_puzzle(result)

        else:
            # Estrategia genérica para juegos desconocidos
            return await self._strategy_generic(result)

    async def _strategy_clicker(self, result: dict) -> dict:
        """Estrategia para juegos de hacer click en objetos (canvas/área de juego)"""
        print("   → Estrategia: Clicker en canvas")

        # Enfocar el canvas si existe
        canvas = await self.page.query_selector("canvas")
        if canvas:
            await canvas.click()
            await asyncio.sleep(0.5)
            box = await canvas.bounding_box()
        else:
            box = None

        end_time = asyncio.get_event_loop().time() + 50
        clicks = 0

        while asyncio.get_event_loop().time() < end_time:
            if box:
                # Click en área central-superior (donde suelen caer tokens)
                x = box["x"] + box["width"] * random.uniform(0.2, 0.8)
                y = box["y"] + box["height"] * random.uniform(0.1, 0.6)
                await self.page.mouse.click(x, y)
                clicks += 1
                await asyncio.sleep(random.uniform(0.15, 0.35))
            else:
                # Sin canvas: buscar área de juego con selectores genéricos
                game_area = await self.page.query_selector(
                    "[class*=game-area], [class*=game-container], [class*=GameArea]"
                )
                if game_area:
                    box = await game_area.bounding_box()
                    if box:
                        x = box["x"] + box["width"] * random.uniform(0.2, 0.8)
                        y = box["y"] + box["height"] * random.uniform(0.2, 0.8)
                        await self.page.mouse.click(x, y)
                        clicks += 1
                        await asyncio.sleep(0.3)

            if await self._game_ended():
                break

        result["success"] = True
        result["clicks"] = clicks
        print(f"   Clicks: {clicks}")
        return result

    async def _strategy_memory(self, result: dict) -> dict:
        """Estrategia para juegos de memoria/pares"""
        print("   → Estrategia: Memory match")

        seen_cards = {}
        end_time = asyncio.get_event_loop().time() + 55

        while asyncio.get_event_loop().time() < end_time:
            cards = await self.page.query_selector_all(
                "[class*='card'], [class*='tile'], [class*='cell']"
            )

            if len(cards) >= 2:
                # Primer click para revelar
                await cards[0].click()
                await asyncio.sleep(0.5)

                # Segundo click
                if len(cards) > 1:
                    await cards[1].click()
                    await asyncio.sleep(1)

            await asyncio.sleep(0.5)

            if await self._game_ended():
                break

        result["success"] = True
        return result

    async def _strategy_runner(self, result: dict) -> dict:
        """Estrategia para juegos de correr/saltar"""
        print("   → Estrategia: Runner (Space/Up para saltar)")

        end_time = asyncio.get_event_loop().time() + 55
        jumps = 0

        # Click en el juego para enfocarlo
        canvas = await self.page.query_selector("canvas")
        if canvas:
            await canvas.click()

        while asyncio.get_event_loop().time() < end_time:
            # Saltar cada 1-2 segundos
            await self.page.keyboard.press("Space")
            jumps += 1
            await asyncio.sleep(random.uniform(0.8, 1.5))

            # También probar flechas
            await self.page.keyboard.press("ArrowUp")
            await asyncio.sleep(random.uniform(0.8, 1.5))

            if await self._game_ended():
                break

        result["success"] = True
        result["jumps"] = jumps
        return result

    async def _strategy_puzzle(self, result: dict) -> dict:
        """Estrategia para puzzles — clicks aleatorios"""
        print("   → Estrategia: Puzzle (clicks exploratorios)")

        end_time = asyncio.get_event_loop().time() + 55

        while asyncio.get_event_loop().time() < end_time:
            # Buscar elementos interactivos
            interactive = await self.page.query_selector_all(
                "button:not([disabled]), [class*='block'],"
                "[class*='piece'], [class*='cell']:not([class*='empty'])"
            )
            if interactive:
                target = random.choice(interactive)
                await target.click()
                await asyncio.sleep(random.uniform(0.3, 0.8))

            if await self._game_ended():
                break

        result["success"] = True
        return result

    async def _strategy_generic(self, result: dict) -> dict:
        """Estrategia genérica para juegos desconocidos"""
        print("   → Estrategia: Genérica (observar + clicks)")

        end_time = asyncio.get_event_loop().time() + 55

        # Enfocar canvas si existe
        canvas = await self.page.query_selector("canvas")
        if canvas:
            await canvas.click()

        while asyncio.get_event_loop().time() < end_time:
            # Mix de clicks y teclas
            if random.random() > 0.5 and canvas:
                box = await canvas.bounding_box()
                if box:
                    x = box["x"] + box["width"] * random.uniform(0.2, 0.8)
                    y = box["y"] + box["height"] * random.uniform(0.2, 0.8)
                    await self.page.mouse.click(x, y)
            else:
                key = random.choice(["Space", "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"])
                await self.page.keyboard.press(key)

            await asyncio.sleep(random.uniform(0.3, 0.7))

            if await self._game_ended():
                break

        result["success"] = True
        return result

    async def _game_ended(self) -> bool:
        """Detecta si el juego terminó y hace clic en continuar si es necesario"""
        selectors = [
            "text=Play Again",
            "text=PLAY AGAIN",
            "text=Try Again",
            "text=Game Over",
            "text=You Win",
            "text=Continue",
            "[class*=game-over]",
            "[class*=result]",
            "[class*=GameOver]",
            "[class*=PlayAgain]",
            "button:has-text('Play Again')",
            "button:has-text('Continue')",
            "button:has-text('OK')",
        ]
        for sel in selectors:
            try:
                el = await self.page.query_selector(sel)
                if el and await el.is_visible():
                    print("   Fin del juego detectado")
                    # Click en continuar
                    for click_sel in [
                        "button:has-text('Play Again')",
                        "button:has-text('Continue')",
                        "button:has-text('OK')",
                        "button:has-text('Claim')",
                    ]:
                        try:
                            btn = await self.page.query_selector(click_sel)
                            if btn and await btn.is_visible():
                                await btn.click()
                                await asyncio.sleep(1)
                                break
                        except Exception:
                            pass
                    return True
            except Exception:
                continue
        return False
