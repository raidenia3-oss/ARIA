# -*- coding: utf-8 -*-
"""Automatizacion de RollerCoin con Playwright (navegador). Sin servidores, salida."""
import os

def explore(url="https://rollercoin.com", headless=True):
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        return {"status": "error", "error": "playwright no instalado: %s" % exc}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            page = browser.new_page()
            page.goto(url, timeout=30000)
            page.wait_for_load_state("domcontentloaded", timeout=15000)
            title = page.title()
            text = page.inner_text("body")[:1500]
            links = [a.get_attribute("href") for a in page.query_selector_all("a") if a.get_attribute("href")]
            links = [l for l in links if l][:30]
            shot = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rollercoin_shot.png")
            page.screenshot(path=shot, full_page=False)
            browser.close()
            return {"status": "ok", "title": title, "text": text, "links": links, "screenshot": shot}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}

def play_game(game_url, headless=True, duration=10):
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        return {"status": "error", "error": "playwright no instalado: %s" % exc}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            page = browser.new_page()
            page.goto(game_url, timeout=30000)
            page.wait_for_load_state("domcontentloaded", timeout=15000)
            title = page.title()
            # simple interaction: click center a few times
            for _ in range(5):
                page.mouse.click(640, 400)
                page.wait_for_timeout(500)
            text = page.inner_text("body")[:800]
            browser.close()
            return {"status": "ok", "title": title, "text": text}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}