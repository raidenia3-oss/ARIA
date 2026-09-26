#!/usr/bin/env python3
"""
validate_page.py — Auditor automático de la Landing Page.
Verifica:
  a) Cierre correcto de etiquetas HTML (parse well-formedness).
  b) Scripts de Adsterra en posiciones correctas.
  c) Enlaces sin rotos (href no vacío ni '#').
"""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import List, Optional, Tuple

INDEX_HTML = Path(__file__).resolve().parent / "index.html"


class TagChecker(HTMLParser):
    """Verifica que las etiquetas no-autocierre se cierren correctamente."""
    def __init__(self) -> None:
        super().__init__()
        self.errors: List[str] = []
        self._stack: List[str] = []
        self._self_closing = {
            "br", "hr", "img", "input", "meta", "link", "source",
            "area", "base", "col", "embed", "param", "track", "wbr",
        }

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        if tag not in self._self_closing:
            self._stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in self._self_closing:
            return
        # Buscar en la pila hacia atrás
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i] == tag:
                self._stack.pop(i)
                return
        self.errors.append(f"Etiqueta de cierre </{tag}> sin apertura correspondiente")

    def final_check(self) -> int:
        if self._stack:
            self.errors.append(f"Etiquetas sin cerrar: {', '.join(self._stack)}")
        return len(self.errors)


def check_html_tags(html: str) -> int:
    """a) Verificar que las etiquetas Tailwind cierren perfectamente."""
    checker = TagChecker()
    checker.feed(html)
    errs = checker.final_check()
    for e in checker.errors:
        print(f"  ERROR TAG: {e}")
    return errs


def check_adsterra(html: str) -> int:
    """b) Verificar que los scripts de Adsterra estén en posiciones correctas."""
    errors = 0
    # Social bar script debe estar en <head>
    head_part = html.split("</head>")[0] if "</head>" in html else ""
    if 'data-adsterra="social-bar"' in head_part:
        print("  OK: Social Bar script en <head>")
    else:
        print("  ERROR: Script de Social Bar no encontrado en <head>")
        errors += 1

    # Popunder script debe estar en <body> (después de </head>)
    body_part = html.split("</head>")[-1] if "</head>" in html else html
    if 'data-adsterra="popunder"' in body_part:
        print("  OK: Popunder script en <body>")
    else:
        print("  ERROR: Script de Popunder no encontrado en <body>")
        errors += 1

    # Social bar container div
    if 'id="adsterra-social-bar"' in html:
        print("  OK: Social Bar container div presente")
    else:
        print("  ERROR: Social Bar container div faltante")
        errors += 1

    # Función dispararPopunder
    if "function dispararPopunder" in html:
        print("  OK: función dispararPopunder() definida")
    else:
        print("  ERROR: función dispararPopunder() no definida")
        errors += 1

    return errors


def check_links(html: str) -> int:
    """c) Verificar que no existan enlaces rotos (href != '' y != '#')."""
    errors = 0
    pattern = re.compile(r'<a\s+[^>]*href\s*=\s*"([^"]*)"', re.IGNORECASE)
    for href in pattern.findall(html):
        href_stripped = href.strip()
        if href_stripped == "" or href_stripped == "#":
            print(f"  ERROR: Enlace roto encontrado: href=\"{href}\"")
            errors += 1
    if errors == 0:
        print("  OK: Todos los enlaces tienen href válido")
    return errors


def main() -> int:
    if not INDEX_HTML.exists():
        print(f"ERROR: {INDEX_HTML} no existe")
        return 1

    html = INDEX_HTML.read_text(encoding="utf-8")

    print("=== Auditoría Automática de Landing Page ===\n")
    total_errors = 0

    print("[a] Cierre de etiquetas HTML:")
    total_errors += check_html_tags(html)

    print("\n[b] Scripts y contenedores Adsterra:")
    total_errors += check_adsterra(html)

    print("\n[c] Enlaces:")
    total_errors += check_links(html)

    print(f"\n=== TOTAL: {total_errors} errores ===")
    return 1 if total_errors > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
