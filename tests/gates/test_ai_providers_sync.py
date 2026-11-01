"""Gate de sincronia de las copias de ai_providers.py.

La resolucion de modelos vive en cuatro archivos (raiz, ARIA_APP, y las dos
app Tauri). Antes de este gate cada edicion podia tocar la raiz y las copias
seguian con el modelo viejo, sin ningun sintoma: el divergence es silenciosa
porque cada copia es un archivo valido por si mismo.

Solo se compara el CUERPO (linea 1 en adelante). La primera linea es el docstring
de branding y difiere a proposito: la raiz dice "AURA AI Providers" y las copias
dicen "ARIA AI Providers". Por eso este gate no exige igualdad byte a byte, que
fallaria de entrada y teaches a ignorar el fallo.

Los artefactos de build (target/, _up_/) y los worktrees de Agent Manager se
excluyen a proposito: los primeros los regenera `tauri build` desde el repo, y los
segundos son ramas independientes. Si se anade una quinta copia al repo, el gate
falla para que se registre explicitamente en vez de quedarse sin vigilar.
"""

from __future__ import annotations

import os
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
CANONICAL = ROOT / "ai_providers.py"

# Copias que deben existir y coincidir con la raiz. Anadir una exige editarla.
EXPECTED_COPIES = (
    ROOT / "ARIA_APP" / "ai_providers.py",
    ROOT / "aura-v5-tauri" / "ARIA_APP" / "ai_providers.py",
    ROOT / "aura-v5-tauri-webgpu" / "ARIA_APP" / "ai_providers.py",
)

EXCLUDED_PARTS = (
    ".git", ".venv", "node_modules", ".kilo", "target", "_up_", "dist", "build",
)


def _body(path: pathlib.Path) -> list[str]:
    """Contenido desde la linea 2 en adelante (excluye el branding)."""
    return path.read_text(encoding="utf-8").splitlines()[1:]


def _first_line_difference(expected: list[str], actual: list[str]) -> str:
    for index, (want, got) in enumerate(zip(expected, actual), start=2):
        if want != got:
            return f"linea {index}: raiz={want.strip()[:70]!r} copia={got.strip()[:70]!r}"
    if len(expected) != len(actual):
        return f"largo distinto: raiz={len(expected) + 1} lineas, copia={len(actual) + 1}"
    return ""


def _discovered_copies() -> list[pathlib.Path]:
    """Copia de ai_providers.py en el arbol, saltando lo excluido al caminar.

    Se usa os.walk con poda en vez de rglob: rglob recorre tambien los
    directorios excluidos y el gate se colgaba varios minutos cuando un
    worktree de Agent Manager (copia completa del repo) aparecio en el arbol.
    """
    found = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_PARTS]
        if "ai_providers.py" not in filenames:
            continue
        path = pathlib.Path(dirpath) / "ai_providers.py"
        if path != CANONICAL:
            found.append(path)
    return sorted(found)


def test_canonical_file_exists():
    assert CANONICAL.is_file(), "no existe la copia canonica de ai_providers.py"


def test_expected_copies_all_exist():
    missing = [str(p.relative_to(ROOT)) for p in EXPECTED_COPIES if not p.is_file()]
    assert not missing, f"copias de ai_providers.py ausentes: {missing}"


def test_no_copy_escaped_the_gate():
    """Una copia nueva sin registrar queda sin vigilar, que es como ocurre la deriva."""
    registered = {p.resolve() for p in EXPECTED_COPIES}
    unregistered = [str(p.relative_to(ROOT)) for p in _discovered_copies() if p.resolve() not in registered]
    assert not unregistered, (
        "copias de ai_providers.py sin registrar en este gate: "
        f"{unregistered}\n agregalas a EXPECTED_COPIES si son fuente, "
        "o a EXCLUDED_PARTS si son artefactos."
    )


@pytest.mark.parametrize("copy", EXPECTED_COPIES, ids=lambda p: str(p.relative_to(ROOT)))
def test_copy_matches_canonical_body(copy):
    assert copy.is_file(), f"falta {copy.relative_to(ROOT)}"
    diff = _first_line_difference(_body(CANONICAL), _body(copy))
    assert not diff, (
        f"{copy.relative_to(ROOT)} diverge de ai_providers.py: {diff}\n"
        "La resolucion de modelos debe ser identica en las cuatro copias; "
        "si el divergence es intencional, se documenta aqui y no se propaga en silencio."
    )


@pytest.mark.parametrize("copy", (CANONICAL, *EXPECTED_COPIES), ids=lambda p: str(p.relative_to(ROOT)) if p != CANONICAL else "ai_providers.py")
def test_every_copy_pins_the_same_default_model(copy):
    text = copy.read_text(encoding="utf-8")
    assert 'DEFAULT_OLLAMA_MODEL = "spark25-ab"' in text, (
        f"{copy.relative_to(ROOT)} no fija spark25-ab como modelo por defecto"
    )


@pytest.mark.parametrize("copy", (CANONICAL, *EXPECTED_COPIES), ids=lambda p: str(p.relative_to(ROOT)) if p != CANONICAL else "ai_providers.py")
def test_every_copy_sends_the_think_flag(copy):
    text = copy.read_text(encoding="utf-8")
    assert "_ollama_request_flags" in text, (
        f"{copy.relative_to(ROOT)} no define _ollama_request_flags: spark2_5 razona por "
        "defecto y la respuesta llega envuelta en <think>"
    )
    assert '"think"' in text, f"{copy.relative_to(ROOT)} no manda think en las flags de Ollama"
