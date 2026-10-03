"""Contrato de honestidad de /health y de los targets de los launchers.

Verificacion ESTATICA (ast + lectura de texto): no importa `backend.main` —cuyo
import arrastra ~150 modulos y side effects— ni arranca uvicorn. Los tests
fallan si alguien revierte el contrato y son deterministas.

Dos defectos que estos tests blindan:

1. `backend/main.py` registra `/health` DOS veces: el handler `health()` y
   `detailed_health`, mas abajo. Starlette resuelve en orden de registro, asi que
   gana `health()` y `detailed_health` queda como codigo muerto para esa ruta.
   `health()` devolvia un literal `{"status": "healthy", "service":
   "aura-news-api"}` sin medir nada.

2. `scripts/start_aura_local.bat` y `scripts/start_aura_production.bat` apuntaban
   a `ame_backend.src.main:app`, que no existe: `ame_backend/` solo contiene
   `.env.local`. El entrypoint real es `ARIA_APP/backend/app.py` servido como
   `app:app` desde `ARIA_APP/backend` (v5/electron/main.ts:111).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MAIN_PY = REPO_ROOT / "backend" / "main.py"
ARIA_APP_BACKEND = REPO_ROOT / "ARIA_APP" / "backend"

# Los dos launchers que este arreglo corrigio. start_aura_full.bat,
# scripts/run_wifi.ps1 y .devcontainer/post-create.sh siguen apuntando a
# ame_backend: se reportan, no se tocan (fuera de la lista de ficheros).
LAUNCHERS = {
    "start_aura_local.bat": REPO_ROOT / "scripts" / "start_aura_local.bat",
    "start_aura_production.bat": REPO_ROOT / "scripts" / "start_aura_production.bat",
}

# Literales que el contrato prohíbe: afirmarian una medicion que no se hizo.
FORBIDDEN_HEALTH_LITERALS = {"healthy", "aura-news-api"}
FORBIDDEN_HEALTH_KEYS = {"cpu", "memory", "disk", "uptime", "latency", "rss"}


def _health_handler() -> ast.AsyncFunctionDef:
    """Localiza el handler `health` por nombre, no por numero de linea.

    Los numeros de linea se desplazan con cada edit; el nombre no.
    """
    tree = ast.parse(MAIN_PY.read_text(encoding="utf-8"), filename=str(MAIN_PY))
    for node in tree.body:
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "health":
            return node
    raise AssertionError("backend/main.py ya no define un handler async `health`")


def _decorated_get_paths(fn: ast.AsyncFunctionDef) -> set[str]:
    paths: set[str] = set()
    for dec in fn.decorator_list:
        if not isinstance(dec, ast.Call):
            continue
        target = dec.func
        if not isinstance(target, ast.Attribute) or target.attr != "get":
            continue
        if not (isinstance(target.value, ast.Name) and target.value.id == "app"):
            continue
        for arg in dec.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                paths.add(arg.value)
    return paths


def _returned_literal_strings(fn: ast.AsyncFunctionDef) -> dict[str, set[str]]:
    """Clave -> literales de cadena que aparecen en su valor.

    Claves que NO sean literales (p. ej. una f-string) se descartan: aqui solo
    queremos auditar los literales que se devuelven tal cual.
    """
    returns = [
        node
        for node in ast.walk(fn)
        if isinstance(node, ast.Return) and node.value is not None
    ]
    assert len(returns) == 1, "se esperaba exactamente un return en el handler health"
    node = returns[0].value
    assert isinstance(node, ast.Dict), "el handler health debe devolver un dict literal"
    out: dict[str, set[str]] = {}
    for key, value in zip(node.keys, node.values):
        if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
            continue
        out[key.value] = {
            sub.value
            for sub in ast.walk(value)
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str)
        }
    return out


def test_health_serves_both_paths() -> None:
    assert _decorated_get_paths(_health_handler()) == {"/health", "/api/health"}


def test_health_declares_unavailable_with_a_reason() -> None:
    """`/health` no mide dependencias, asi que debe decirlo, no fingir salud."""
    returned = _returned_literal_strings(_health_handler())
    assert returned["data_source"] == {"unavailable"}
    assert returned["detail"], "detail no puede ser una cadena vacia"


def test_health_does_not_claim_a_fabricated_status() -> None:
    returned = _returned_literal_strings(_health_handler())
    literals = set().union(*returned.values())
    assert not (literals & FORBIDDEN_HEALTH_LITERALS)


def test_health_invents_no_resource_metrics() -> None:
    """Sin medicion no hay cpu/memory/uptime: ni 0, ni null, ni estimated."""
    returned = _returned_literal_strings(_health_handler())
    assert FORBIDDEN_HEALTH_KEYS.isdisjoint(returned)


def test_health_identity_is_derived_not_hardcoded() -> None:
    """`service` sale de os.getenv, no de un literal fijo."""
    source = MAIN_PY.read_text(encoding="utf-8")
    segment = ast.get_source_segment(source, _health_handler())
    assert segment is not None
    assert "os.getenv" in segment


@pytest.mark.parametrize("name", sorted(LAUNCHERS))
def test_launcher_targets_the_entrypoint_that_exists(name: str) -> None:
    text = LAUNCHERS[name].read_text(encoding="utf-8", errors="replace")
    # En batch comentan `::` y `REM`. Una mencion historica del modulo muerto
    # dentro de un comentario no es un comando, asi que no invalida el launcher;
    # lo que importa es que ninguna linea ejecutable lo invoque.
    executed = "\n".join(
        line
        for line in text.splitlines()
        if not line.strip().lower().startswith(("::", "rem "))
    )
    assert "ame_backend.src.main" not in executed
    assert "app:app" in text
    assert "ARIA_APP\\backend" in text


@pytest.mark.parametrize("name", sorted(LAUNCHERS))
def test_launcher_aborts_loudly_when_target_is_missing(name: str) -> None:
    text = LAUNCHERS[name].read_text(encoding="utf-8", errors="replace")
    assert "if not exist" in text
    assert "app.py" in text
    assert "exit /b 1" in text


def test_launcher_entrypoint_is_present() -> None:
    assert (ARIA_APP_BACKEND / "app.py").is_file()


def test_ame_backend_contains_no_python_module() -> None:
    """Documenta por que el target antiguo no podia funcionar."""
    ame = REPO_ROOT / "ame_backend"
    if not ame.is_dir():
        pytest.skip("ame_backend/ no existe: el target antiguo ya no aplica")
    modules = sorted(p.name for p in ame.rglob("*.py"))
    assert modules == [], (
        f"ame_backend/ contiene {modules}; los launchers ya no apuntan ahi"
    )


# -- (b) registro unico de /health ----------------------------------------------


def _get_paths_by_handler() -> dict[str, list[str]]:
    tree = ast.parse(MAIN_PY.read_text(encoding="utf-8"), filename=str(MAIN_PY))
    out: dict[str, list[str]] = {}
    for node in tree.body:
        if not isinstance(node, ast.AsyncFunctionDef):
            continue
        paths = _decorated_get_paths(node)
        if paths:
            out[node.name] = sorted(paths)
    return out


def test_no_health_path_is_registered_by_two_handlers() -> None:
    """`/health` estaba registrado por `health()` y por `detailed_health`.

    Starlette resuelve en orden de registro, asi que la sonda real de DB/Redis era
    codigo muerto: `detailed_health` ahora se expone en `/health/detailed` y
    `/health` sigue siendo la respuesta honesta sin dependencias.

    El alcance son las rutas de health. Hay OTRO par duplicado que este test no
    pretende arbitrar: `/api/orchestrator` lo registran `orchestrator_status`
    (`Depends(require_api_key)`, linea ~1854) y `get_orchestrator_protected`
    (`Depends(get_current_user)`, linea ~2500). Gana el primero, asi que el
    segundo es codigo muerto, pero ambos exigen credenciales: no hay bypass, y
    elegir un ganador cambia comportamiento, asi que queda reportado.
    """
    seen: dict[str, str] = {}
    collisions = []

    for handler, paths in _get_paths_by_handler().items():
        for path in paths:
            if path != "/health" and not path.startswith("/health/"):
                continue
            if path in seen:
                collisions.append(f"{path}: {seen[path]} y {handler}")
            seen[path] = handler

    assert not collisions, f"rutas de health registradas por dos handlers: {collisions}"


def test_the_dependency_probe_is_reachable() -> None:
    handlers = _get_paths_by_handler()
    assert "detailed_health" in handlers
    assert handlers["detailed_health"] == ["/health/detailed"]
    assert "/health" in handlers["health"]


def test_the_db_probe_executes_a_textclause() -> None:
    """`Session.execute("SELECT 1")` lanza en SQLAlchemy 2.x (exige TextClause),
    asi que el chequeo de base de datos salia `error` siempre."""
    source = MAIN_PY.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(MAIN_PY))
    detailed = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "detailed_health"
    ]
    assert detailed, "backend/main.py ya no define detailed_health"
    detailed_source = ast.get_source_segment(source, detailed[0])
    assert detailed_source is not None
    assert 'db.execute("SELECT 1")' not in detailed_source
    assert "text(" in detailed_source


# -- (c) el fallback de IA no inventa disponibilidad -----------------------------


def test_the_ai_fallback_does_not_claim_a_provider_is_available() -> None:
    """`ARIA_APP/backend/app.py` arranca un `_FallbackAIManager` si el import de
    `ai_providers` falla. Declaraba `available: True` sin haber sondeado nada y
    `chat()` devolvia un texto fijo con `latency: 0.0`: una IA que finge."""
    app_src = (ARIA_APP_BACKEND / "app.py").read_text(encoding="utf-8", errors="replace")

    start = app_src.find("class _FallbackAIManager")
    assert start != -1, "el fallback de IA ya no existe: reevaluar el contrato"
    body = app_src[start:start + 3000]

    assert '"available": True' not in body
    assert "ARIA funcionando en modo local" not in body
    assert '"latency": 0.0' not in body
    assert '"data_source": "unavailable"' in body
    assert '"available": None' in body


def test_the_ai_fallback_records_why_the_import_failed() -> None:
    """`except Exception:` sin binding se tragaba la causa, y por eso nadie sabia
    por que caia al fallback."""
    app_src = (ARIA_APP_BACKEND / "app.py").read_text(encoding="utf-8", errors="replace")

    assert "except Exception as exc:" in app_src
    assert "AI_UNAVAILABLE_REASON" in app_src


def test_the_mobile_health_check_reports_a_measured_latency() -> None:
    """`/api/mobile/health-check` devolvia `latency_ms: 0` literal: cero latencia
    sin haber cronometrado nada."""
    tree = ast.parse(MAIN_PY.read_text(encoding="utf-8"), filename=str(MAIN_PY))
    handler = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef)
        and node.name == "mobile_health_check"
    ]
    assert handler, "backend/main.py ya no expone mobile_health_check"

    source = MAIN_PY.read_text(encoding="utf-8")
    segment = ast.get_source_segment(source, handler[0])
    assert segment is not None
    assert '"latency_ms": 0' not in segment
    assert "perf_counter" in segment
    assert '"data_source": "measured"' in segment
