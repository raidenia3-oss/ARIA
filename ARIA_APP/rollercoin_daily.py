# -*- coding: utf-8 -*-
"""Automatizacion diaria de RollerCoin con Playwright + boveda (vault)."""
import os
import json

def _credenciales():
    """Obtiene email/password de RollerCoin desde vault o entorno."""
    email = os.environ.get("ROLLERCOIN_EMAIL", "").strip()
    password = os.environ.get("ROLLERCOIN_PASSWORD", "").strip()
    # intentar vault
    try:
        from vault import Vault
        v = Vault()
        master = os.environ.get("ARIA_MASTER") or os.environ.get("ARIA_VAULT_MASTER")
        if master and v.existe():
            v.abrir(master)
            email = v.get("ROLLERCOIN_EMAIL") or email
            password = v.get("ROLLERCOIN_PASSWORD") or password
            v.cerrar()
    except Exception:
        pass
    return email, password

def guardar_credenciales(email, password, master=None):
    """Guarda credenciales en la boveda (requiere master)."""
    try:
        from vault import Vault
        v = Vault()
        master = master or os.environ.get("ARIA_MASTER") or os.environ.get("ARIA_VAULT_MASTER")
        if not master:
            return {"status": "error", "error": "falta master (ARIA_MASTER)"}
        if not v.existe():
            v.crear(master)
        else:
            v.abrir(master)
        v.set("ROLLERCOIN_EMAIL", email)
        v.set("ROLLERCOIN_PASSWORD", password)
        v.cerrar()
        return {"status": "ok", "guardado": True}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}

def login(headless=True):
    """Login en RollerCoin via Playwright usando credenciales de boveda/env."""
    email, password = _credenciales()
    if not email or not password:
        return {"status": "error", "error": "sin credenciales (vault o ROLLERCOIN_EMAIL/PASSWORD)"}
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        return {"status": "error", "error": "playwright no instalado: %s" % exc}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            ctx = browser.new_context()
            page = ctx.new_page()
            page.goto("https://rollercoin.com", timeout=30000)
            page.wait_for_load_state("domcontentloaded", timeout=15000)
            # buscar boton login
            try:
                page.click("text=Log in", timeout=5000)
            except Exception:
                pass
            page.wait_for_timeout(1000)
            # llenar credenciales
            try:
                page.fill('input[type="email"], input[name="email"], input[placeholder*="mail" i]', email, timeout=5000)
            except Exception:
                pass
            try:
                page.fill('input[type="password"], input[name="password"]', password, timeout=5000)
            except Exception:
                pass
            try:
                page.click('button:has-text("Log in"), button:has-text("Sign in"), button[type="submit"]', timeout=5000)
            except Exception:
                pass
            page.wait_for_timeout(3000)
            title = page.title()
            url = page.url
            # guardar cookies
            cookies = ctx.cookies()
            cookie_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rollercoin_cookies.json")
            with open(cookie_file, "w", encoding="utf-8") as f:
                json.dump(cookies, f)
            browser.close()
            return {"status": "ok", "title": title, "url": url, "cookies": len(cookies)}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}

def daily_run(headless=True):
    """Ejecuta una sesion diaria: login + explorar + reportar."""
    lr = login(headless=headless)
    if lr.get("status") != "ok":
        return lr
    # explorar dashboard
    try:
        from rollercoin_play import explore
        ex = explore("https://rollercoin.com", headless=headless)
    except Exception as exc:
        ex = {"status": "error", "error": str(exc)}
    return {"status": "ok", "login": lr, "explore": {"title": ex.get("title"), "text_len": len(ex.get("text", ""))}}