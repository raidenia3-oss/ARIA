# -*- coding: utf-8 -*-
"""ARIA - Actividades: ver reels de Instagram, jugar minijuegos de RollerCoin.
Incluye medidas anti-deteccion: delays aleatorios, movimiento humano del raton,
user-agent realista, args anti-automation."""
import os
import time
import random

PROFILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "aria_browser_profile_pw")

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-features=IsolateOrigins,site-per-process",
    "--no-sandbox",
]


def _human_delay(min_s=0.5, max_s=2.0):
    time.sleep(random.uniform(min_s, max_s))


def _human_click(page, x, y, jitter=8):
    """Click con movimiento suave y offset aleatorio."""
    jx = x + random.randint(-jitter, jitter)
    jy = y + random.randint(-jitter, jitter)
    # movimiento suave desde posicion actual
    try:
        cur = page.mouse.position if hasattr(page.mouse, "position") else {"x": 640, "y": 400}
    except Exception:
        cur = {"x": 640, "y": 400}
    steps = random.randint(8, 16)
    for i in range(1, steps + 1):
        ix = int(cur["x"] + (jx - cur["x"]) * i / steps + random.randint(-2, 2))
        iy = int(cur["y"] + (jy - cur["y"]) * i / steps + random.randint(-2, 2))
        page.mouse.move(ix, iy)
        time.sleep(random.uniform(0.01, 0.03))
    page.mouse.click(jx, jy)
    _human_delay(0.2, 0.6)


def _launch(headless=True):
    from playwright.sync_api import sync_playwright
    p = sync_playwright().start()
    ctx = p.chromium.launch_persistent_context(
        PROFILE, headless=headless,
        viewport={"width": random.choice([1280, 1366, 1440, 1920]),
                  "height": random.choice([720, 768, 900, 1080])},
        user_agent=USER_AGENT,
        args=STEALTH_ARGS,
    )
    # stealth: ocultar webdriver
    ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return p, ctx


def ver_reels_instagram(cantidad=5, headless=True):
    """Abre Instagram reels y los recorre con delays humanos."""
    p, ctx = _launch(headless)
    resultados = []
    try:
        page = ctx.new_page()
        page.goto("https://www.instagram.com/reels/", timeout=30000)
        page.wait_for_load_state("domcontentloaded", timeout=15000)
        _human_delay(3, 5)
        for i in range(cantidad):
            try:
                txt = page.inner_text("article")[:200] if page.query_selector("article") else ""
            except Exception:
                txt = ""
            resultados.append({"reel": i+1, "texto": txt[:150]})
            # scroll humano
            page.keyboard.press("ArrowDown")
            _human_delay(2, 4)
            # ocasionalmente scroll arriba/abajo para parecer humano
            if random.random() < 0.3:
                page.mouse.wheel(0, random.randint(-200, 200))
                _human_delay(0.5, 1.5)
        ctx.close()
        p.stop()
        return {"status": "ok", "reels_vistos": len(resultados), "detalle": resultados}
    except Exception as exc:
        try:
            ctx.close(); p.stop()
        except Exception:
            pass
        return {"status": "error", "error": str(exc)}


def explorar_rollercoin(headless=True):
    """Explora RollerCoin: paginas principales con delays humanos."""
    p, ctx = _launch(headless)
    paginas = ["/", "/game", "/game/choose_game", "/game/season/season-pass", "/game/market"]
    resultados = []
    try:
        page = ctx.new_page()
        for path in paginas:
            try:
                page.goto("https://rollercoin.com" + path, timeout=20000)
                page.wait_for_load_state("domcontentloaded", timeout=10000)
                _human_delay(2, 4)
                title = page.title()
                text = page.inner_text("body")[:300]
                games = []
                for a in page.query_selector_all("a"):
                    href = a.get_attribute("href") or ""
                    if "game" in href.lower():
                        games.append(href)
                resultados.append({"path": path, "title": title[:60], "text": text[:200], "games": list(set(games))[:8]})
                # scroll humano
                page.mouse.wheel(0, random.randint(200, 500))
                _human_delay(1, 2)
            except Exception as exc:
                resultados.append({"path": path, "error": str(exc)})
        ctx.close()
        p.stop()
        return {"status": "ok", "paginas": len(resultados), "detalle": resultados}
    except Exception as exc:
        try:
            ctx.close(); p.stop()
        except Exception:
            pass
        return {"status": "error", "error": str(exc)}


def jugar_rollercoin_game(game_url="https://rollercoin.com/game/choose_game", headless=True, duracion=15):
    """Abre un minijuego y lo juega con comportamiento humano."""
    p, ctx = _launch(headless)
    try:
        page = ctx.new_page()
        page.goto(game_url, timeout=30000)
        page.wait_for_load_state("domcontentloaded", timeout=15000)
        _human_delay(3, 5)
        # cerrar popups/modales
        for sel in ['button:has-text("Don\'t allow")', 'button:has-text("No thanks")', '.modal .close', '[aria-label="Close"]']:
            try:
                page.click(sel, timeout=1000, force=True)
            except Exception:
                pass
        _human_delay(1, 2)
        # click START con force
        try:
            page.click('text=START', timeout=5000, force=True)
            _human_delay(2, 3)
        except Exception:
            pass
        clicks = 0
        t0 = time.time()
        while time.time() - t0 < duracion:
            _human_click(page, random.randint(500, 780), random.randint(300, 500))
            clicks += 1
            # pausas aleatorias para parecer humano
            if random.random() < 0.2:
                _human_delay(1, 2)
            else:
                _human_delay(0.2, 0.5)
        title = page.title()
        text = page.inner_text("body")[:300]
        ctx.close()
        p.stop()
        return {"status": "ok", "title": title[:60], "clicks": clicks, "text": text[:200]}
    except Exception as exc:
        try:
            ctx.close(); p.stop()
        except Exception:
            pass
        return {"status": "error", "error": str(exc)}


def run(action="explore", **kw):
    if action == "reels":
        return ver_reels_instagram(kw.get("cantidad", 5), kw.get("headless", True))
    if action == "explore":
        return explorar_rollercoin(kw.get("headless", True))
    if action == "play":
        return jugar_rollercoin_game(kw.get("url", "https://rollercoin.com/game/choose_game"), kw.get("headless", True), kw.get("duracion", 15))
    return {"status": "error", "error": "accion desconocida: %s" % action}