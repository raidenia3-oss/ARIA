#!/usr/bin/env python3
"""
web_auditor.py — Auditoría de la landing SaaS en aura-web/index.html
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))

from playwright.sync_api import sync_playwright

def main() -> int:
    html_path = Path('aura-web/index.html').resolve().as_uri()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 800})
        page.goto(html_path, wait_until='domcontentloaded')

        # a) Escribir texto de prueba
        page.fill('#prompt-input', 'hola')

        # b) Click en generar
        page.click('#prompt-generate-btn')

        # c) Esperar resultado optimizado (3s + margen)
        page.wait_for_selector('#prompt-output:not(.hidden)', timeout=10000)
        out_text = page.inner_text('#prompt-result')
        assert out_text and len(out_text.strip()) > 0, 'Output vacío'

        # d) Verificar placeholders Adsterra en el DOM/código
        assert page.locator('#adsterra-banner').count() > 0, 'Falta ADSTERRA BANNER'
        assert page.locator('#adsterra-popunder').count() > 0, 'Falta ADSTERRA POPUNDER'

        print('PASS: web_auditor')
        browser.close()
        return 0

if __name__ == '__main__':
    raise SystemExit(main())
