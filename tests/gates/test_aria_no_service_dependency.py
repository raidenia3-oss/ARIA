"""Gate: ARIA no se construye en dependencia de ningún servicio.

Contexto: el 2026-10-20 la autonomía de ARIA se había conectado al runtime
en Rust (`v6/axum-poc`, puerto 8002) por HTTP. Eso convertía a un servicio
externo en una pieza obligatoria de ARIA: sin el núcleo en pie, el escritorio
se quedaba sin percepción, sin agenda y sin lecciones.

ARIA es una aplicación de escritorio en un solo proceso: la autonomía vive en
`ARIA_APP/autonomy/`, en el mismo proceso que la dibuja. Eso no es una
cuestión de estilo, así que se verifica con gate y no con buena voluntad:

- el camino del escritorio no habla con loopback ni con puertos de servicio
- el camino del escritorio no arranca servidores (ni HTTP, ni sockets)
- la autonomía no importa clientes de red: no sale a buscar nada por su cuenta
- la autonomía no depende de que exista el cliente HTTP del núcleo

Lo que se verifica aquí, y por qué:

- la regla base se cumple: ARIA arranca y piensa sin nada más encendido
- una dependencia no puede colarse de vuelta "sólo para el panel de autonomía"
- el runtime nativo sigue siendo la única fuente de percepción y lecciones
"""

from __future__ import annotations

import io
import re
import tokenize
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ARIA_APP = ROOT / "ARIA_APP"

#: Los archivos que forman el proceso único de ARIA.
DESKTOP_FILES = [
    Path("ARIA_APP/aria_main.py"),
    Path("ARIA_APP/desktop_ui.py"),
    Path("ARIA_APP/desktop_autonomy.py"),
    Path("ARIA_APP/desktop_tray.py"),
    Path("ARIA_APP/aria_va_core.py"),
    Path("ARIA_APP/autonomy/__init__.py"),
    Path("ARIA_APP/autonomy/runtime.py"),
    Path("ARIA_APP/autonomy/perception.py"),
]

#: El runtime autónomo: no puede necesitar la red para funcionar.
AUTONOMY_FILES = [
    Path("ARIA_APP/autonomy/__init__.py"),
    Path("ARIA_APP/autonomy/runtime.py"),
    Path("ARIA_APP/autonomy/perception.py"),
    Path("ARIA_APP/desktop_autonomy.py"),
]

#: Dependencias de servicio: direcciones y puertos que son de otro proceso.
SERVICE_PATTERNS = [
    (re.compile(r"https?://(?:127\.0\.0\.1|localhost|0\.0\.0\.0|\[::1\])", re.IGNORECASE),
     "dirección de loopback"),
    (re.compile(r"(?<![\d.])(?:8000|8002|8080|11434|11500)(?![\d.])"),
     "puerto de servicio"),
]

#: Servidores que ARIA no puede montar en su propio proceso.
SERVER_PATTERNS = [
    (re.compile(r"\buvicorn\.run\b"), "uvicorn.run"),
    (re.compile(r"\b(?:socket|sock)\.(?:listen|bind|accept)\b"), "socket.listen/bind"),
    (re.compile(r"^\s*from\s+fastapi\b", re.MULTILINE), "import fastapi"),
    (re.compile(r"^\s*import\s+fastapi\b", re.MULTILINE), "import fastapi"),
    (re.compile(r"\bhttp\.server\b"), "http.server"),
    (re.compile(r"\bsocketserver\b"), "socketserver"),
    (re.compile(r"\bHTTPServer\b"), "HTTPServer"),
    (re.compile(r"\bFastAPI\s*\("), "FastAPI"),
    (re.compile(r"\bFlask\s*\("), "Flask"),
]

#: Clientes de red: la autonomía no sale a buscar nada por su cuenta.
NETWORK_IMPORTS = [
    "urllib.request",
    "http.client",
    "httpx",
    "requests",
    "aiohttp",
    "websockets",
]

#: Generadores externos: ARIA no puede depender de que haya un modelo para
#: arrancar, pensar ni decidir. El generador, si lo hay, es un extra.
GENERATIVE_IMPORTS = [
    "ai_providers",
    "openai",
    "anthropic",
    "ollama",
    "litellm",
    "cohere",
    "google.generativeai",
    "google_genai",
    "mistralai",
    "groq",
]


def _strip_py_comments(text: str) -> str:
    """Quita los comentarios de Python dejando el codigo y los strings."""
    out = list(text)
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type != tokenize.COMMENT:
                continue
            (srow, scol), (erow, ecol) = tok.start, tok.end
            if srow != erow:
                continue
            line = out[srow - 1]
            out[srow - 1] = line[:scol] + " " * (ecol - scol) + line[ecol:]
    except Exception:
        out = [
            line for line in out
            if not line.lstrip().startswith("#")
        ]
    return "\n".join(out)


def _read(rel: Path) -> str:
    path = ROOT / rel
    assert path.is_file(), f"falta el archivo del proceso unico de ARIA: {rel}"
    return _strip_py_comments(path.read_text(encoding="utf-8", errors="ignore"))


@pytest.mark.parametrize("rel", DESKTOP_FILES, ids=lambda p: str(p))
def test_el_escritorio_no_depende_de_ningun_servicio(rel):
    code = _read(rel)
    offenders = []
    for pattern, label in SERVICE_PATTERNS:
        for match in pattern.finditer(code):
            line_no = code[:match.start()].count("\n") + 1
            offenders.append(f"{rel}:{line_no} -> {label} ({match.group(0)})")
    assert not offenders, (
        "ARIA no puede depender de un servicio en otro proceso:\n  "
        + "\n  ".join(offenders)
    )


@pytest.mark.parametrize("rel", DESKTOP_FILES, ids=lambda p: str(p))
def test_el_escritorio_no_arranca_servidores(rel):
    code = _read(rel)
    offenders = []
    for pattern, label in SERVER_PATTERNS:
        for match in pattern.finditer(code):
            line_no = code[:match.start()].count("\n") + 1
            offenders.append(f"{rel}:{line_no} -> {label}")
    assert not offenders, (
        "ARIA es un proceso unico: no puede montar servidores:\n  "
        + "\n  ".join(offenders)
    )


@pytest.mark.parametrize("rel", AUTONOMY_FILES, ids=lambda p: str(p))
def test_la_autonomia_no_importa_clientes_de_red(rel):
    code = _read(rel)
    offenders = []
    for module in NETWORK_IMPORTS:
        pattern = re.compile(rf"^\s*(?:import|from)\s+{re.escape(module)}\b", re.MULTILINE)
        for match in pattern.finditer(code):
            line_no = code[:match.start()].count("\n") + 1
            offenders.append(f"{rel}:{line_no} -> {module}")
    assert not offenders, (
        "La autonomia de ARIA no necesita la red para funcionar:\n  "
        + "\n  ".join(offenders)
    )


def test_no_queda_el_cliente_http_del_nucleo():
    """El proxy al runtime en Rust se fue con la dependencia."""
    leftovers = [
        path for path in (ARIA_APP / "backend").rglob("autonomy_client.py")
    ]
    assert not leftovers, (
        "el cliente HTTP del núcleo no debe volver: "
        + ", ".join(str(p) for p in leftovers)
    )


@pytest.mark.parametrize(
    "rel",
    sorted(set(DESKTOP_FILES) | set(AUTONOMY_FILES)),
    ids=lambda p: str(p),
)
def test_aria_no_depende_de_ningun_generador(rel):
    """ARIA no se construye en dependencia de un modelo ni de un servicio de IA.

    La regla del proyecto: lo que ARIA necesita para arrancar y pensar vive
    en su proceso. Un proveedor de IA (remoto o local en otro puerto) puede
    estar disponible, pero no puede ser un requisito: si el import de un
    generador se cuela aquí, ARIA vuelve a depender de algo ajeno.
    """
    code = _read(rel)
    offenders = []
    for module in GENERATIVE_IMPORTS:
        pattern = re.compile(rf"^\s*(?:import|from)\s+{re.escape(module)}\b", re.MULTILINE)
        for match in pattern.finditer(code):
            line_no = code[:match.start()].count("\n") + 1
            offenders.append(f"{rel}:{line_no} -> {module}")
    assert not offenders, (
        "ARIA no puede depender de un generador externo:\n  "
        + "\n  ".join(offenders)
    )


def test_la_autonomia_no_necesita_un_generador_para_pensar():
    """El runtime decide y habla con reglas: el cerebro es un extra."""
    runtime = ARIA_APP / "autonomy" / "runtime.py"
    code = runtime.read_text(encoding="utf-8", errors="ignore")
    assert "brain: Any = None" in code, (
        "el runtime debe poder arrancar sin cerebro"
    )
    assert "_fallback_utterance" in code, (
        "si no hay cerebro, ARIA debe tener algo que decir de todas formas"
    )


def test_la_autonomia_nativa_existe_y_es_local():
    """El runtime autónomo es código de ARIA, no una llamada a otro sitio."""
    runtime = ARIA_APP / "autonomy" / "runtime.py"
    assert runtime.is_file(), "ARIA_APP/autonomy/runtime.py debe existir"
    code = runtime.read_text(encoding="utf-8", errors="ignore")
    assert "class Runtime" in code
    assert 'SERVER = "in-process"' in code


def test_el_escritorio_usa_el_runtime_local():
    """La franja de autonomía lee el runtime del proceso, no un servicio."""
    desktop = (ARIA_APP / "desktop_ui.py").read_text(encoding="utf-8", errors="ignore")
    assert "desktop_autonomy" in desktop
    assert "autonomy_bridge" not in desktop, (
        "el escritorio no debe volver a hablar con un puente HTTP"
    )
