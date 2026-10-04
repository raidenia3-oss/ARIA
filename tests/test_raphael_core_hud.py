"""Gate del HUD Raphael Core (`v6/raphael_core/`).

El HUD se supone honesto: cada element core apunta a un endpoint real y cada
blueprint a un fichero real del arbol. Estos tests lo comprueban contra el disco
para que una ruta renombrada o un endpoint movido no dejen el sitio mintiendo.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HUD = ROOT / "v6" / "raphael_core"
APP_JS = HUD / "assets" / "js" / "app.js"
API_JS = HUD / "assets" / "js" / "api.js"
NUCLEUS_JS = HUD / "assets" / "js" / "nucleus.js"
MAIN_PY = ROOT / "backend" / "main.py"
SWARM_ROUTES_PY = ROOT / "backend" / "swarm_routes.py"

PROBES = {
    "/health",
    "/health/detailed",
    "/api/swarm/agents/status",
    "/api/swarm/metrics",
    "/api/swarm/roles",
    "/api/swarm/status",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_hud_files_exist():
    for rel in (
        "index.html",
        "netlify.toml",
        "README.md",
        "assets/css/raphael.css",
        "assets/js/app.js",
        "assets/js/api.js",
        "assets/js/nucleus.js",
    ):
        assert (HUD / rel).is_file(), f"falta {rel} en v6/raphael_core"


def test_every_blueprint_path_exists():
    paths = re.findall(r'path:\s*"([^"]+)"', _read(APP_JS))
    assert paths, "no se ha encontrado ningun blueprint en app.js"
    missing = [p for p in paths if not (ROOT / p).exists()]
    assert not missing, f"blueprints que no existen en el arbol: {missing}"


def test_readme_documents_every_probe():
    readme = _read(HUD / "README.md")
    for endpoint in sorted(PROBES):
        assert endpoint in readme, f"el README no documenta {endpoint}"


@pytest.mark.parametrize(
    ("endpoint", "handler_source"),
    [
        ("/health", MAIN_PY),
        ("/health/detailed", MAIN_PY),
        ("/api/swarm/agents/status", SWARM_ROUTES_PY),
        ("/api/swarm/metrics", SWARM_ROUTES_PY),
        ("/api/swarm/roles", SWARM_ROUTES_PY),
        ("/api/swarm/status", SWARM_ROUTES_PY),
    ],
)
def test_probe_endpoint_is_registered(endpoint, handler_source):
    """Cada sonda del HUD tiene que existir como ruta en el backend."""
    source = _read(handler_source)
    suffix = endpoint[len("/api"):] if endpoint.startswith("/api") else endpoint
    assert f'"{suffix}"' in source, f"{endpoint} no aparece en {handler_source.name}"


def test_api_js_only_probes_declared_endpoints():
    probes = set(re.findall(r'probe\("([^"]+)"', _read(API_JS)))
    assert probes == PROBES, f"sondas inesperadas o ausentes: {probes ^ PROBES}"


def test_every_element_core_has_a_probe():
    """Un nucleo en orbita sin sonda seria luz decorativa, es decir, mentira."""
    cores = re.findall(
        r'\{\s*id:\s*"([a-z]+)",\s*label:\s*"([^"]+)",[^}]*?endpoint:\s*"([^"]+)"',
        _read(NUCLEUS_JS),
    )
    assert len(cores) == 6, f"se esperaban 6 element cores, hay {len(cores)}"
    ids = [core_id for core_id, _, _ in cores]
    assert len(set(ids)) == 6, f"element cores duplicados: {ids}"
    endpoints = {endpoint for _, _, endpoint in cores}
    assert endpoints == PROBES, f"orbitas sin sonda coherente: {endpoints ^ PROBES}"


def test_hud_never_invents_a_measurement():
    """El HUD no puede rellenar con ceros: si no hay dato, no hay numero."""
    api_source = _read(API_JS)
    assert '"unavailable"' in api_source
    assert "data_source" in api_source
    for forbidden in ("Math.random(", "Date.now("):
        assert forbidden not in api_source, f"la capa de datos usa {forbidden}"
        assert forbidden not in _read(APP_JS), f"app.js usa {forbidden}"


def test_nucleus_randomness_is_only_visual():
    """La aleatoriedad solo puede pintar polvo, nunca fabricar telemetria."""
    source = _read(NUCLEUS_JS)
    dust = re.search(r"this\.dust\s*=\s*Array\.from\(.*?\}\);", source, re.S)
    assert dust, "no se ha encontrado la construccion del polvo en nucleus.js"
    outside = source.replace(dust.group(0), "")
    assert "Math.random(" not in outside, "aleatoriedad fuera del polvo visual"
    assert "setVitality" in source, "el nucleo debe recibir su nivel de vida de las sondas"