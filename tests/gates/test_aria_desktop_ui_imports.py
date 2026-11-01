"""Gate: en el camino del escritorio no hay nombres sin definir.

El 2026-10-21 `ARIA_APP/desktop_ui.py` usaba `re.sub` en `_render_markdown`
sin haber importado `re`. NameError en un slot = PyQt5 aborta el proceso:
ARIA se caia al primer mensaje. Nadie lo vio porque la app se "~probaba~"
sin escribir nada.

Este gate no necesita linters externos (la regla del repo es no instalar
paquetes): usa `symtable`, que viene en la biblioteca estandar, para listar
los nombres que el modulo usa como globales sin haberlos definido ni
importado.
"""

from __future__ import annotations

import builtins
import symtable
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

#: Los archivos del camino canonico del escritorio.
CANONICAL = (
    ROOT / "ARIA_APP" / "desktop_ui.py",
    ROOT / "ARIA_APP" / "desktop_autonomy.py",
    ROOT / "ARIA_APP" / "aria_main.py",
    ROOT / "ARIA_APP" / "aria_va_core.py",
    ROOT / "ARIA_APP" / "autonomy" / "runtime.py",
    ROOT / "ARIA_APP" / "autonomy" / "perception.py",
)


def _undefined_globals(path: Path) -> list[str]:
    """Nombres usados como globales que el modulo no define ni importa."""
    source = path.read_text(encoding="utf-8")
    tabla = symtable.symtable(source, str(path), "exec")

    definidos = set()
    for simbolo in tabla.get_symbols():
        if simbolo.is_assigned() or simbolo.is_imported() or simbolo.is_namespace():
            definidos.add(simbolo.get_name())

    conocidos = definidos | set(dir(builtins))

    perdidos: list[str] = []
    for ambito in tabla.get_children():
        for simbolo in ambito.get_symbols():
            nombre = simbolo.get_name()
            if not simbolo.is_global() or not simbolo.is_referenced():
                continue
            if nombre.startswith("__") or nombre in conocidos:
                continue
            perdidos.append(f"{nombre} (en {ambito.get_name()})")
    return sorted(set(perdidos))


@pytest.mark.parametrize("ruta", CANONICAL, ids=lambda p: p.name)
def test_ningun_nombre_esta_sin_definir(ruta):
    if not ruta.is_file():
        pytest.skip(f"{ruta} no existe todavia")

    perdidos = _undefined_globals(ruta)

    assert not perdidos, (
        f"{ruta.name} usa nombres que no define ni importa: {perdidos}. "
        "Un NameError dentro de un slot aborta la app entera."
    )


def test_el_escritorio_no_usa_motor_web():
    """Ni QWebEngine ni 'page()': la interfaz es nativa, no una pagina."""
    texto = (ROOT / "ARIA_APP" / "desktop_ui.py").read_text(encoding="utf-8")
    codigo = "\n".join(
        linea for linea in texto.splitlines() if not linea.strip().startswith("#")
    )

    assert "QWebEngine" not in codigo
    assert ".page()" not in codigo
    assert "evaluateJavaScript" not in codigo
