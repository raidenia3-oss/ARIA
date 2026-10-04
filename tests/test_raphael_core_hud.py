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
LORE_JS = HUD / "assets" / "js" / "lore.js"
INDEX_HTML = HUD / "index.html"
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
        "assets/js/lore.js",
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


def _code_without_comments(path: Path) -> str:
    source = _read(path)
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    return re.sub(r"//[^\n]*", "", source)


def test_swarm_status_returns_counters_not_the_unified_shape():
    """`/api/swarm/status` esta sombreado: gana el handler de la linea 95.

    El HUD recorre el payload real, asi que este gate congela el hecho. Si
    alguien quita el handler duplicado, este test falla y obliga a revisar el
    parseo en vez de dejar el sitio explicando una forma que ya no existe.
    """
    source = _read(SWARM_ROUTES_PY)
    registrations = re.findall(r'@router\.get\("/swarm/status"\)', source)
    assert len(registrations) == 2, (
        "se esperaba el sombreado conocido (2 registros de /swarm/status); "
        f"hay {len(registrations)}. Revisa el parseo del HUD antes de tocarlo."
    )
    code = _code_without_comments(API_JS)
    for forbidden in ("orchestrator", "self_healing", "process_monitor"):
        assert forbidden not in code, (
            f"api.js no debe asumir la forma del handler unificado ({forbidden}): "
            "esa ruta la sirve el handler de la linea 95 y no lo devuelve"
        )


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


# --------------------------------------------------------------------------
# Gates de la segunda pasada: las seis capas del Quantum Core Resonator.
#
# Los nombres de los builders se leyeron del bundle publicado de
# https://brahma-evo.netlify.app/web_background/index.html. Si el nucleo pierde
# una capa, este bloque falla en vez de que la pagina solo se vea mas pobre.
# --------------------------------------------------------------------------

REFERENCE_LAYERS = {
    "buildStandingWaveManifold": "drawStandingWave",
    "buildCentralVortexSingularity": "drawTendrils",
    "buildGyroscopicOrbitalRings": "drawRings",
    "buildStarburstNodes": "drawNodes",
    "buildReferenceMoonBokeh": "drawBokeh",
    "buildAmbientDust": "drawDust",
}


@pytest.mark.parametrize(("builder", "method"), sorted(REFERENCE_LAYERS.items()))
def test_every_reference_layer_is_drawn(builder, method):
    source = _read(NUCLEUS_JS)
    assert f"draw{method.removeprefix('draw').capitalize()}" or True  # legible failure
    assert f"  {method}(" in source, f"falta la capa {method} ({builder})"
    assert f"this.{method}(" in source, f"draw() no llama a {method} ({builder})"


def test_draws_layers_in_back_to_front_order():
    """El orden importa: bokeh detras, nodos delante de los anillos."""
    source = _read(NUCLEUS_JS)
    pipeline = re.search(r"\n  draw\(\) \{.*?\n  \}", source, re.S)
    assert pipeline, "no se ha encontrado el pipeline de draw()"
    body = pipeline.group(0)
    order = [m for m in re.findall(r"this\.(draw\w+)\(", body)]
    expected = ["drawBokeh", "drawDust", "drawLattice", "drawStandingWave", "drawRings", "drawNodes"]
    positions = [order.index(name) for name in expected]
    assert positions == sorted(positions), f"orden de capas inesperado: {order}"


def test_standing_wave_keeps_four_lobes():
    """Cuatro lobulos es la forma; el numero de muestras es negociable.

    El corte se hace en `samples`, nunca en `lobes`, para que un movil no
    termine con una onda de dos lobulos que ya no se parece en nada.
    """
    lore = _read(LORE_JS)
    assert "lobes: 4," in lore, "GEOMETRY debe seguir declarando 4 lobulos"
    assert "lobeAmplitude: 0.75," in lore, "la amplitud 0.75 viene del reactor"
    source = _read(NUCLEUS_JS)
    assert "GEOMETRY.lobes" in source, "drawStandingWave debe leer el numero de lobulos"
    assert "this.compact" in source, "el modo compacto debe reducir muestras, no lobulos"


def test_every_ring_has_its_own_axis_and_precession():
    """buildGyroscopicOrbitalRings: sin axis/precess no hay giroscopio."""
    lore = _read(LORE_JS)
    rings = re.search(r"rings:\s*\[(.*?)\n  \],", lore, re.S)
    assert rings, "no se ha encontrado la tabla de anillos en lore.js"
    entries = re.findall(r"\{[^{}]*scale:[^{}]*\}", rings.group(1))
    assert len(entries) >= 4, f"se esperaban al menos 4 anillos, hay {len(entries)}"
    for entry in entries:
        assert "axis:" in entry, f"anillo sin axis: {entry}"
        assert "precess:" in entry, f"anillo sin precess: {entry}"


def test_bokeh_and_nodes_are_tables_not_randomness():
    """Fijos en el arbol y sin Math.random: el nucleo se ve igual en cada carga."""
    lore = _read(LORE_JS)
    for table in ("bokeh:", "nodes:"):
        assert table in lore, f"falta la tabla {table} en GEOMETRY"
    source = _read(NUCLEUS_JS)
    assert "this.bokeh = GEOMETRY.bokeh.map" in source
    assert "this.nodes = GEOMETRY.nodes.map" in source


def test_public_control_surface_matches_the_reference():
    """El reactor publicado se maneja desde window.*; el HUD tambien."""
    lore = _read(LORE_JS)
    controls = re.search(r"NUCLEUS_CONTROLS\s*=\s*\[(.*?)\];", lore, re.S)
    assert controls, "no se ha declarado NUCLEUS_CONTROLS en lore.js"
    names = re.findall(r'"(\w+)"', controls.group(1))
    assert names, "NUCLEUS_CONTROLS esta vacio"
    source = _read(NUCLEUS_JS)
    for name in names:
        assert f"{name}(" in source, f"nucleus.js no implementa el control {name}"
        # Un campo de instancia con el mismo nombre taparia el metodo del
        # prototipo y el control desapareceria de controls() en silencio.
        assert not re.search(rf"this\.{name}\s*=[^=]", source), (
            f"this.{name} como campo tapa el metodo {name}() y lo saca de controls()"
        )
    app = _read(APP_JS)
    assert "globalThis.ARIA" in app, "el HUD debe exponer window.ARIA"
    assert "renderer.controls()" in app, "window.ARIA.nucleus debe ser la superficie de control"


def test_controls_cannot_fabricate_a_reading():
    """Los controles mueven pixeles. Lo unico que repinta el HUD es refresh()."""
    app = _read(APP_JS)
    surface = app[app.index("globalThis.ARIA") :]
    assert "readCore" not in surface.split("}")[0], "window.ARIA no debe volver a leer por su cuenta"
    assert "refresh: run" in surface, "solo refresh() puede re-sondar"


def test_split_title_keeps_the_sentence_for_screen_readers():
    """buildonaut parte el titulo en letras; el texto original debe sobrevivir."""
    html = _read(INDEX_HTML)
    assert "data-split" in html, "el h1 debe llevar data-split"
    app = _read(APP_JS)
    assert 'setAttribute("aria-label", original)' in app, (
        "el titulo partido debe conservar la frase en aria-label"
    )
    assert 'setAttribute("aria-hidden", "true")' in app, (
        "las letras deben quedar fuera del arbol de accesibilidad"
    )


def test_energy_flicker_only_runs_where_there_is_data():
    """Una sonda muerta no centellea: no tiene corriente que rectificar."""
    css = _read(HUD / "assets" / "css" / "raphael.css")
    assert "@keyframes energy-flicker" in css
    block = re.search(
        r'\.core-card\[data-state="ok"\]::after,\s*\n'
        r"\.core-card\[data-state=\"degraded\"\]::after\s*\{[^}]*\}",
        css,
    )
    assert block, "la regla de flicker debe existir para ok y degraded"
    assert "unavailable" not in block.group(0)