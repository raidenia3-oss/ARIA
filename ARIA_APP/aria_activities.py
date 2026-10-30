# -*- coding: utf-8 -*-
"""ARIA - Actividades: ver reels de Instagram, jugar minijuegos de RollerCoin."""
import os
import time

PROFILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "aria_browser_profile_pw")


def ver_reels_instagram(cantidad=5, headless=True):
    """Abre Instagram reels y los recorre (scroll) guardando info."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
    resultados = []
    try:
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(PROFILE, headless=headless)
            page = ctx.new_page()
            page.goto("https://www.instagram.com/reels/", timeout=30000)
            page.wait_for_load_state("domcontentloaded", timeout=15000)
            time.sleep(3)
            for i in range(cantidad):
                # extraer texto visible del reel actual
                try:
                    txt = page.inner_text("article")[:300] if page.query_selector("article") else ""
                except Exception:
                    txt = ""
                resultados.append({"reel": i+1, "texto": txt[:200]})
                # scroll al siguiente reel
                page.keyboard.press("ArrowDown")
                time.sleep(2)
            ctx.close()
            return {"status": "ok", "reels_vistos": len(resultados), "detalle": resultados}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def explorar_rollercoin(headless=True):
    """Explora RollerCoin: paginas principales, juegos, market, etc."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
    paginas = ["/", "/games", "/mining", "/market", "/profile", "/leaderboard"]
    resultados = []
    try:
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(PROFILE, headless=headless)
            page = ctx.new_page()
            for path in paginas:
                try:
                    page.goto("https://rollercoin.com" + path, timeout=20000)
                    page.wait_for_load_state("domcontentloaded", timeout=10000)
                    time.sleep(2)
                    title = page.title()
                    text = page.inner_text("body")[:400]
                    # buscar juegos (links con /game)
                    games = []
                    for a in page.query_selector_all("a"):
                        href = a.get_attribute("href") or ""
                        if "game" in href.lower() or "play" in href.lower():
                            games.append(href)
                    resultados.append({"path": path, "title": title, "text": text[:300], "games": games[:10]})
                except Exception as exc:
                    resultados.append({"path": path, "error": str(exc)})
            ctx.close()
            return {"status": "ok", "paginas": len(resultados), "detalle": resultados}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def jugar_rollercoin_game(game_url, headless=True, duracion=15):
    """Abre un minijuego de RollerCoin y lo juega (clicks) por duracion segundos."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
    try:
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(PROFILE, headless=headless)
            page = ctx.new_page()
            page.goto(game_url, timeout=30000)
            page.wait_for_load_state("domcontentloaded", timeout=15000)
            time.sleep(4)
            # cerrar popups/modales
            for sel in ['button:has-text("Don\'t allow")', 'button:has-text("No thanks")', '.modal .close', '[aria-label="Close"]', 'button.close']:
                try:
                    page.click(sel, timeout=1000, force=True)
                except Exception:
                    pass
            time.sleep(1)
            # click START con force
            try:
                page.click('text=START', timeout=5000, force=True)
                time.sleep(2)
            except Exception:
                pass
            clicks = 0
            t0 = time.time()
            while time.time() - t0 < duracion:
                page.mouse.click(640, 400)
                clicks += 1
                time.sleep(0.3)
            title = page.title()
            text = page.inner_text("body")[:400]
            ctx.close()
            return {"status": "ok", "title": title, "clicks": clicks, "text": text[:300]}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def run(action="explore", **kw):
    if action == "reels":
        return ver_reels_instagram(kw.get("cantidad", 5), kw.get("headless", True))
    if action == "explore":
        return explorar_rollercoin(kw.get("headless", True))
    if action == "play":
        return jugar_rollercoin_game(kw.get("url", "https://rollercoin.com"), kw.get("headless", True), kw.get("duracion", 15))
    return {"status": "error", "error": "accion desconocida: %s" % action}