"""Gate: la autonomía de ARIA está viva, no decorativa.

Tres cosas se habían quedado a medias y no se notaban, porque nada fallaba:

1. Las pulsiones solo se ajustaban cuando ARIA actuaba. Como no había nada
   entre manos, no actuaba, y las pulsiones nunca subían: jamás llegaba al
   umbral y jamás se proponía nada sola. Ahora se ajustan en cada vuelta.
2. La voz llamaba a Google (red) por el camino corto, saltándose el motor
   local. Google es una capacidad, no un requisito: solo entra con permiso
   explícito y siempre después del motor local.
3. El latido solo leía estado en vez de ejecutar. Una vuelta del runtime
   tiene que ser un `tick()` de verdad, con lo que eso implica.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ARIA_APP = ROOT / "ARIA_APP"
CORE = ARIA_APP / "aria_va_core.py"
RUNTIME = ARIA_APP / "autonomy" / "runtime.py"
DESKTOP = ARIA_APP / "desktop_ui.py"


def _tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8", errors="ignore"))


def _method_node(path: Path, name: str, cls: str | None = None):
    """El nodo AST de un metodo (o de una funcion si no se pasa clase)."""
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.ClassDef) and cls and node.name != cls:
            continue
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


# ── 1. Las pulsiones se mueven solas ────────────────────────────────────────


def test_las_pulsiones_se_ajustan_en_cada_vuelta():
    """El ajuste de pulsiones vive dentro de `tick()`, no en otro sitio."""
    tick = _method_node(RUNTIME, "tick", "Runtime")
    assert tick is not None, "Runtime.tick() debe existir"

    calls = {
        node.func.attr
        for node in ast.walk(tick)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "sense_drives" in calls, (
        "las pulsiones tienen que ajustarse en cada vuelta: si solo cambian "
        "al actuar, ARIA nunca llega al umbral por su cuenta"
    )


def test_la_pulsion_alta_propone_una_iniciativa_local():
    """Con la pulsion por encima del umbral, ARIA propone algo suyo."""
    code = RUNTIME.read_text(encoding="utf-8", errors="ignore")
    assert "THRESHOLD = 0.7" in code
    assert "_propose_initiative" in code
    assert 'origin"] = "propia"' in code or '"origin"] = "propia"' in code


# ── 2. La voz transcribe local primero ──────────────────────────────────────


def test_google_no_se_llama_fuera_del_camino_permitido():
    """`recognize_google` solo puede aparecer dentro de `_transcribe`."""
    tree = _tree(CORE)
    transcribe = _method_node(CORE, "_transcribe", "LocalVoice")
    assert transcribe is not None, "LocalVoice._transcribe() debe existir"

    dentro = set()
    for node in ast.walk(transcribe):
        lineno = getattr(node, "lineno", None)
        if lineno is not None:
            dentro.add(lineno)

    fuera = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "recognize_google"
            and node.lineno not in dentro
        ):
            fuera.append(node.lineno)

    assert not fuera, (
        "recognize_google fuera de _transcribe (lineas "
        + ", ".join(str(n) for n in fuera)
        + "): el bucle de escucha tiene que pasar por el camino local primero"
    )


def test_google_necesita_permiso_explicito():
    """Sin ARIA_STT_GOOGLE, Google no se llama ni se anuncia."""
    code = CORE.read_text(encoding="utf-8", errors="ignore")
    assert "ARIA_STT_GOOGLE" in code
    assert "_allow_google" in code


def test_el_bucle_de_escucha_usa_el_camino_local():
    """El bucle de escucha transcribe con `_transcribe`, no con Google."""
    listen = _method_node(CORE, "_listen_loop", "LocalVoice")
    assert listen is not None

    llamadas = {
        node.func.attr
        for node in ast.walk(listen)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "_transcribe" in llamadas, (
        "el bucle de escucha debe transcribir por el camino local primero"
    )
    assert "recognize_google" not in llamadas


# ── 3. El latido ejecuta de verdad ───────────────────────────────────────────


def test_el_latido_da_una_vuelta_real():
    """El latido llama a `tick()`, no a un simple `status()`."""
    beat = _method_node(ARIA_APP / "desktop_autonomy.py", "beat", "Heartbeat")
    assert beat is not None

    llamadas = {
        node.func.attr
        for node in ast.walk(beat)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "tick" in llamadas, "el latido tiene que ejecutar un tick del runtime"
    assert "status" not in llamadas


def test_el_escritorio_enseña_lo_que_aria_hace_sola():
    """Lo que ARIA hace sola sale en el chat y en la OSD."""
    code = DESKTOP.read_text(encoding="utf-8", errors="ignore")
    assert "_beat_summary" in code, "el escritorio debe resumir la vuelta del runtime"
    assert "aria_says.emit" in code
    assert "_append_osd" in code


@pytest.mark.parametrize(
    "rel",
    [
        "ARIA_APP/autonomy/runtime.py",
        "ARIA_APP/desktop_autonomy.py",
        "ARIA_APP/desktop_ui.py",
    ],
)
def test_el_camino_autonomo_sigue_siendo_local(rel):
    """El latido y la franja no pueden abrir puertos ni speak HTTP."""
    code = (ROOT / rel).read_text(encoding="utf-8", errors="ignore")
    for prohibido in ("uvicorn.run", "socket.listen", "http.server", "requests.get"):
        assert prohibido not in code, f"{rel} no puede usar {prohibido}"
