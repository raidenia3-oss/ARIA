# -*- coding: utf-8 -*-
"""ARIA - Navegador propio basado en Playwright (sin puertos, sin localhost).

Lanza Chromium con perfil dedicado en data/aria_browser_profile. Integra la
boveda (vault) para auto-rellenar credenciales. Todo en proceso, salida.
"""
import os
import json

PROFILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "aria_browser_profile")
os.makedirs(PROFILE_DIR, exist_ok=True)


def disponible():
    try:
        import playwright  # noqa
        return True
    except Exception:
        return False


def _credenciales(dominio):
    """Busca credenciales en la boveda para un dominio."""
    try:
        from vault import Vault
        v = Vault()
        master = os.environ.get("ARIA_MASTER") or os.environ.get("ARIA_VAULT_MASTER")
        if master and v.existe():
            v.abrir(master)
            user = v.get("BROWSER_USER_%s" % dominio.upper())
            pwd = v.get("BROWSER_PASS_%s" % dominio.upper())
            v.cerrar()
            return user, pwd
    except Exception:
        pass
    return None, None


def guardar_credencial(dominio, user, password, master=None):
    try:
        from vault import Vault
        v = Vault()
        master = master or os.environ.get("ARIA_MASTER") or os.environ.get("ARIA_VAULT_MASTER")
        if not master:
            return {"status": "error", "error": "falta master"}
        if not v.existe():
            v.crear(master)
        else:
            v.abrir(master)
        v.set("BROWSER_USER_%s" % dominio.upper(), user)
        v.set("BROWSER_PASS_%s" % dominio.upper(), password)
        v.cerrar()
        return {"status": "ok", "dominio": dominio}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def abrir(url="https://www.google.com", headless=False, dominio=None):
    """Abre el navegador de ARIA con perfil propio."""
    if not disponible():
        return {"status": "error", "error": "playwright no instalado"}
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(
                PROFILE_DIR, headless=headless,
                viewport={"width": 1280, "height": 800},
            )
            page = ctx.new_page()
            page.goto(url, timeout=30000)
            page.wait_for_load_state("domcontentloaded", timeout=15000)
            title = page.title()
            # auto-login si hay credenciales
            if dominio:
                user, pwd = _credenciales(dominio)
                if user and pwd:
                    try:
                        page.fill('input[type="email"], input[name="email"], input[name="username"], input[type="text"]', user, timeout=3000)
                        page.fill('input[type="password"]', pwd, timeout=3000)
                    except Exception:
                        pass
            shot = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "aria_browser_shot.png")
            page.screenshot(path=shot, full_page=False)
            ctx.close()
            return {"status": "ok", "title": title, "url": url, "screenshot": shot}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def navegar(url, headless=True):
    return abrir(url, headless=headless)


def run(action="open", **kw):
    if action == "open":
        return abrir(kw.get("url", "https://www.google.com"), kw.get("headless", False), kw.get("dominio"))
    if action == "guardar_credencial":
        return guardar_credencial(kw.get("dominio", ""), kw.get("user", ""), kw.get("password", ""), kw.get("master"))
    if action == "disponible":
        return {"disponible": disponible()}
    return {"status": "error", "error": "accion desconocida: %s" % action}