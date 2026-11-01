"""Gate del guard de procesos de ARIA OS.

Contexto: el 2026-10-19 ARIA ejecuto `taskkill /F /IM chrome.exe` para
intentar leer la base de cookies del navegador y cerro las ~28 ventanas de
Chrome que el usuario tenia abiertas. Ese incidente no puede repetirse, asi
que se verifica con gate, no con buena voluntad.

Lo que se verifica aqui, y por que:

- la politica base se cumple: ARIA solo termina procesos que ella creo
- un proceso del usuario con ventana abierta SIEMPRE se niego
- un navegador abierto por el usuario SIEMPRE se niego (incluso sin ventana)
- un proceso del sistema (explorer, lsass...) se niega siempre
- terminar por nombre esta prohibido: "taskkill /IM" mata cosas no vistas
- el filtro de seguridad bloquea los comandos de kill masivo
- el codigo del runtime no vuelve a introducir kills por nombre de imagen

El modulo se carga por ruta (importlib) y no por paquete: `backend` existe
tambien en la raiz del repo y en ARIA_APP, y meter ARIA_APP en sys.path
romperia el resto de la suite. Por eso el modulo se registra en sys.modules
con su nombre completo para que `safety_filter` lo encuentre.
"""

from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ARIA_APP = ROOT / "ARIA_APP"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


guard_mod = _load("backend.process_guard", ARIA_APP / "backend" / "process_guard.py")
ProcessGuard = guard_mod.ProcessGuard

safety_mod = _load("backend.safety_filter", ARIA_APP / "backend" / "safety_filter.py")


# ─── Dobles de proceso ──────────────────────────────────────────────────────


class _FakeProc:
    """Proceso simulado con nombre, padre y ejecutable controlados."""

    def __init__(self, name: str, pid: int = 4242, parent=None, exe: str = ""):
        self._name = name
        self.pid = pid
        self._parent = parent
        self._exe = exe

    def name(self) -> str:
        return self._name

    def parent(self):
        return self._parent

    def exe(self) -> str:
        return self._exe


def _guard_with(fake_procs: dict, windows: dict | None = None) -> ProcessGuard:
    """Guard con procesos simulados y sin ventanas visibles."""
    guard = ProcessGuard(root_pid=999999)
    guard._proc = lambda pid: fake_procs.get(pid)
    guard._visible_windows = lambda max_age=None: windows or {}
    guard.is_aria_artifact = lambda pid: False
    return guard


# ─── Politica de decision ───────────────────────────────────────────────────


def test_no_se_puede_terminar_el_propio_proceso():
    guard = ProcessGuard(root_pid=os.getpid())
    verdict = guard.check(os.getpid())
    assert not verdict.allowed
    assert verdict.code == "self"


def test_navegador_del_usuario_se_niega_incluso_sin_ventana():
    """El caso del incidente: chrome.exe abierto por el usuario."""
    guard = _guard_with({100: _FakeProc("chrome.exe", pid=100)})
    verdict = guard.check(100)
    assert not verdict.allowed
    assert verdict.code == "user_process"
    assert "sesion del usuario" in verdict.reason


def test_proceso_con_ventana_visible_se_niega():
    """Un proceso cualquiera con ventana del usuario nunca se toca."""
    guard = _guard_with(
        {200: _FakeProc("miapp.exe", pid=200)},
        windows={200: {"pid": 200, "title": "Documento sin guardar"}},
    )
    verdict = guard.check(200)
    assert not verdict.allowed
    assert verdict.code == "user_window"
    assert verdict.visible_window is True
    assert "Documento sin guardar" in verdict.reason


def test_procesos_criticos_del_sistema_se_niegan_siempre():
    for name in ("explorer.exe", "lsass.exe", "winlogon.exe", "dwm.exe"):
        guard = _guard_with({300: _FakeProc(name, pid=300)})
        verdict = guard.check(300)
        assert not verdict.allowed, name
        assert verdict.code == "hard_protected", name


def test_proceso_no_lanzado_por_aria_se_niega():
    guard = _guard_with({400: _FakeProc("procesoajeno.exe", pid=400)})
    verdict = guard.check(400)
    assert not verdict.allowed
    assert verdict.code == "not_owned"


def test_propio_hijo_de_aria_si_se_puede_terminar():
    """Lo unico que ARIA puede terminar: lo que ella lanzo."""
    guard = _guard_with({500: _FakeProc("python.exe", pid=500)})
    guard.is_aria_owned = lambda pid: pid == 500
    verdict = guard.check(500)
    assert verdict.allowed
    assert verdict.code == "owned"


def test_terminar_por_nombre_esta_prohibido():
    guard = ProcessGuard(root_pid=os.getpid())
    result = guard.safe_terminate_by_name("chrome.exe")
    assert result["status"] == "denied"
    assert result["terminated"] is False
    assert result["code"] == "name_kill_forbidden"


# ─── Comportamiento con procesos reales ─────────────────────────────────────


def _spawn_sleeper() -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def test_proceso_real_ajeno_se_niega_y_propio_hijo_se_permite():
    child = _spawn_sleeper()
    try:
        # Guard ajeno: el hijo existe pero no es de este ARIA.
        guard_ajeno = ProcessGuard(root_pid=999999)
        guard_ajeno.is_aria_artifact = lambda pid: False
        verdict = guard_ajeno.check(child.pid)
        assert not verdict.allowed
        assert verdict.code == "not_owned"

        # Guard propio: el hijo es descendiente de este proceso.
        guard_propio = ProcessGuard(root_pid=os.getpid())
        guard_propio.is_aria_artifact = lambda pid: False
        verdict_propio = guard_propio.check(child.pid)
        assert verdict_propio.allowed
        assert verdict_propio.owned is True
    finally:
        try:
            child.terminate()
        except Exception:
            pass
        child.wait(timeout=10)


def test_safe_terminate_termina_un_hijo_propio():
    child = _spawn_sleeper()
    guard = ProcessGuard(root_pid=os.getpid())
    guard.is_aria_artifact = lambda pid: False
    result = guard.safe_terminate(child.pid, reason="test")
    assert result["terminated"] is True
    assert result["status"] == "ok"
    assert child.wait(timeout=10) is not None


# ─── Guard de comandos ──────────────────────────────────────────────────────


@pytest.mark.parametrize("command", [
    "taskkill /F /IM chrome.exe",
    "taskkill /F /IM msedge.exe /T",
    "TASKKILL /F /IM FIREFOX.EXE",
    "Stop-Process -Name chrome -Force",
    "killall chrome",
    "pkill -f chrome",
    "wmic process where name='chrome.exe' delete",
])
def test_comandos_de_kill_masivo_se_bloquean(command):
    guard = ProcessGuard(root_pid=os.getpid())
    denial = guard.guard_command(command)
    assert denial is not None, command
    assert denial["allowed"] is False


def test_comandos_inofensivos_pasan():
    guard = ProcessGuard(root_pid=os.getpid())
    for command in ("echo hola", "git status", "npm run build", "dir"):
        assert guard.guard_command(command) is None, command


def test_safety_filter_bloquea_el_comando_del_incidente():
    violation = safety_mod.safety_check("taskkill /F /IM chrome.exe")
    assert violation is not None
    assert violation.to_dict()["blocked"] is True


def test_safety_filter_deja_pasar_comandos_normales():
    assert safety_mod.safety_check("echo hola") is None


# ─── Gate estatico: el runtime no reintroduce kills por nombre ─────────────

RUNTIME_TREES = [
    "ARIA_APP", "backend", "packages", "AME", "scripts", "tools",
    "aria_autoconfig", "aria_snapshot", "aria_release", "aura-os",
    "LongMemory/apps",
]

#: Modulos que contienen los patrones de deteccion (no son offenders).
GUARD_FILES = {
    Path("ARIA_APP/backend/process_guard.py"),
    Path("ARIA_APP/backend/safety_filter.py"),
    Path("scripts/gatekeeper.py"),
}

#: Kill por nombre de imagen: mata procesos que nadie eligio.
NAME_KILL_PATTERNS = [
    (re.compile(r"taskkill[^\n]{0,80}?/im\b", re.IGNORECASE), "taskkill /IM"),
    (re.compile(r"stop-process[^\n]{0,80}?-name\b", re.IGNORECASE), "Stop-Process -Name"),
    (re.compile(r"\bkillall\b", re.IGNORECASE), "killall"),
    (re.compile(r"pkill[^\n]{0,40}?-f\s+['\"]?(python|node|cmd|python3)['\"]?\s*($|\||;|&)",
                re.IGNORECASE), "pkill -f <lenguaje>"),
]


def _strip_py_comments(text: str) -> str:
    """Quita los comentarios de Python dejando el codigo y los strings."""
    import io
    import tokenize

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
        # Si el archivo no tokeniza, se ignoran las lineas de comment entero.
        out = [
            line for line in out
            if not line.lstrip().startswith("#")
        ]
    return "\n".join(out)


def _strip_shell_comments(text: str, suffix: str) -> str:
    """Quita comentarios de .sh/.bat/.ps1/.cmd."""
    kept = []
    for line in text.splitlines():
        stripped = line.strip()
        if suffix == ".bat" or suffix == ".cmd":
            if stripped.startswith("REM ") or stripped.startswith("::"):
                continue
        elif stripped.startswith("#") or stripped.startswith("::"):
            continue
        kept.append(line)
    return "\n".join(kept)


def _code_only(path: Path, text: str) -> str:
    if path.suffix.lower() == ".py":
        return _strip_py_comments(text)
    return _strip_shell_comments(text, path.suffix.lower())


def _runtime_files():
    for tree in RUNTIME_TREES:
        base = ROOT / tree
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".py", ".ps1", ".bat", ".cmd", ".sh", ".ts", ".js"}:
                continue
            if any(part in {"node_modules", ".venv", "venv", "__pycache__", "dist", "build",
                            "release", "target", ".git"} for part in path.parts):
                continue
            yield path


def test_no_hay_kills_por_nombre_en_el_runtime():
    offenders = []
    for path in _runtime_files():
        rel = path.relative_to(ROOT)
        if rel in GUARD_FILES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        code = _code_only(path, text)
        for pattern, label in NAME_KILL_PATTERNS:
            for match in pattern.finditer(code):
                line_no = code[:match.start()].count("\n") + 1
                offenders.append(f"{rel}:{line_no} -> {label}")
    assert not offenders, (
        "Kills por nombre de imagen encontrados en el runtime. "
        "Usa PID explicito o el ProcessGuard:\n  " + "\n  ".join(offenders)
    )


def test_el_guard_existe_y_declara_la_politica():
    assert (ARIA_APP / "backend" / "process_guard.py").exists()
    policy = guard_mod.get_guard().describe()
    assert policy["name_kill_allowed"] is False
    assert "procesos" in policy["policy"].lower()
