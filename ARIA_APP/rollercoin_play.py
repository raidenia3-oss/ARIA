# -*- coding: utf-8 -*-
"""Automatizacion de RollerCoin con Playwright (anti-deteccion)."""
import os
import random
import time

PROFILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "aria_browser_profile_pw")
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
STEALTH_ARGS = ["--disable-blink-features=AutomationControlled", "--no-sandbox"]


def _launch(headless=True):
    from playwright.sync_api import sync_playwright
    p = sync_playwright().start()
    ctx = p.chromium.launch_persistent_context(
        PROFILE, headless=headless,
        viewport={"width": random.choice([1280, 1366, 1440]),
                  "height": random.choice([720, 768, 900])},
        user_agent=USER_AGENT, args=STEALTH_ARGS)
    ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return p, ctx


def explore(url="https://rollercoin.com", headless=True):
    p, ctx = _launch(headless)
    try:
        page = ctx.new_page()
        page.goto(url, timeout=30000)
        page.wait_for_load_state("domcontentloaded", timeout=15000)
        time.sleep(random.uniform(2, 4))
        title = page.title()
        text = page.inner_text("body")[:1500]
        links = [a.get_attribute("href") for a in page.query_selector_all("a") if a.get_attribute("href")]
        links = [l for l in links if l][:30]
        shot = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rollercoin_shot.png")
        page.screenshot(path=shot, full_page=False)
        ctx.close(); p.stop()
        return {"status": "ok", "title": title, "text": text, "links": links, "screenshot": shot}
    except Exception as exc:
        try:
            ctx.close(); p.stop()
        except Exception:
            pass
        return {"status": "error", "error": str(exc)}


def play_game(game_url, headless=True, duration=10):
    p, ctx = _launch(headless)
    try:
        page = ctx.new_page()
        page.goto(game_url, timeout=30000)
        page.wait_for_load_state("domcontentloaded", timeout=15000)
        time.sleep(random.uniform(3, 5))
        for sel in ['button:has-text("Don\'t allow")', 'button:has-text("No thanks")']:
            try:
                page.click(sel, timeout=1000, force=True)
            except Exception:
                pass
        time.sleep(random.uniform(1, 2))
        try:
            page.click('text=START', timeout=5000, force=True)
            time.sleep(random.uniform(2, 3))
        except Exception:
            pass
        clicks = 0
        t0 = time.time()
        while time.time() - t0 < duration:
            x = random.randint(500, 780)
            y = random.randint(300, 500)
            page.mouse.move(x + random.randint(-5, 5), y + random.randint(-5, 5))
            time.sleep(random.uniform(0.05, 0.15))
            page.mouse.click(x, y)
            clicks += 1
            time.sleep(random.uniform(0.2, 0.6))
            if random.random() < 0.15:
                time.sleep(random.uniform(1, 2))
        title = page.title()
        text = page.inner_text("body")[:800]
        ctx.close(); p.stop()
        return {"status": "ok", "title": title, "clicks": clicks, "text": text[:300]}
    except Exception as exc:
        try:
            ctx.close(); p.stop()
        except Exception:
            pass
        return {"status": "error", "error": str(exc)}


def run(action="explore", **kw):
    if action == "explore":
        return explore(kw.get("url", "https://rollercoin.com"), kw.get("headless", True))
    if action == "play":
        return play_game(kw.get("url", "https://rollercoin.com/game/choose_game"), kw.get("headless", True), kw.get("duration", 10))
    if action == "list_games":
        return list_games(kw.get("headless", True))
    return {"status": "error", "error": "accion desconocida: %s" % action}
def list_games(headless=True):
    p, ctx = _launch(headless)
    try:
        page = ctx.new_page()
        page.goto('https://rollercoin.com/game/choose_game', timeout=30000)
        page.wait_for_load_state('domcontentloaded', timeout=15000)
        time.sleep(random.uniform(4, 6))
        text = page.inner_text('body')
        ctx.close()
        p.stop()
        import re
        games = []
        pattern = re.compile(r'^(.+?)\n\ndifficulty:\n\n(\d+)\n\nlevel:\n\n(\d+)\n\nSTART\n\n(.+?)\n\ntime:\n\n(\d+)\s*sec\n\nreward:\n\n(\d+)\s*pts', re.MULTILINE | re.DOTALL)
        for m in pattern.finditer(text):
            name = m.group(1).strip().split(chr(10))[-1].strip()
            if name in ('NEW', 'HOT', 'COMMUNITY', 'Coming soon...'):
                continue
            games.append({
                'name': name,
                'difficulty': int(m.group(2)),
                'level': int(m.group(3)),
                'description': m.group(4).strip()[:80],
                'time': int(m.group(5)),
                'reward': int(m.group(6))
            })
        return {'status': 'ok', 'count': len(games), 'games': games}
    except Exception as exc:
        try:
            ctx.close()
            p.stop()
        except Exception:
            pass
        return {'status': 'error', 'error': str(exc)}
