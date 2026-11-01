"""HUECO 1C: tests de cierre para el motor de permisos.

Cubre los huecos que quedaban abiertos tras HUECO 1B:
  4. HTTP: approve/pending/audit sin token = 401; token incorrecto = 401;
     sin token configurado = 503 (fail-closed); replay = rechazado.
  5. Token: solo de env (ARIA_APPROVAL_TOKEN), nunca se imprime, nunca en
     logs ni repo, y no está en ninguna ruta que read_file permita.
  6. read_file/list_dir: raíces por env (ARIA_FS_ROOTS, default = solo la
     carpeta de datos de ARIA). Normaliza con realpath (.., symlinks) ANTES
     de comprobar. Siempre deny: .env*, *.pem, *.key, rclone.conf, .ssh,
     .git/config, .kilo. Fuera de raíces = ask.
  7. Gates: collect-only, suite COMPLETA, escaneo de secretos del diff
     staged, git status --short. NO git add -A.
"""
import hashlib
import importlib
import importlib.util as _ilu
import os
import secrets
import sys
import types as _types
from pathlib import Path
from typing import Optional

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("PYTHONPATH", str(PROJECT_ROOT))
os.environ.setdefault("AURA_SKIP_BACKGROUND_SERVICES", "1")

from backend.permissions import (
    PermissionConfig,
    PermissionEngine,
    get_permission_engine,
    reset_permission_engine,
)
from fastapi.testclient import TestClient

# Cargamos ARIA_APP/backend/app.py como un modulo suelo (importlib). app.py
# inserta ARIA_APP/backend en sys.path y sus imports internos son ``backend.*``
# (ARIA_APP/backend es la raiz del paquete ``backend``). Pero el proyecto tambien
# tiene backend/ (project-root) con modulos que ARIA_APP/backend/agents/base.py
# re-exporta (backend.agents.react_loop, backend.permissions, etc.). Por eso
# usamos un finder de meta-path que busca en AMBAS rutas: ARIA_APP/backend
# primero (asi backend.agent.core resuelve a ARIA_APP) y project-root/backend
# como fallback. El motor de permisos real (unico) queda en
# backend.permissions y se carga antes de tocar el paquete.
_real_perm = importlib.import_module("backend.permissions")

ARIA_APP_BACKEND = str(PROJECT_ROOT / "ARIA_APP" / "backend")
_PROJECT_BACKEND = str(PROJECT_ROOT / "backend")

# Quitar PROJECT_ROOT del path para que ``backend`` no resuelva directamente a
# project-root/backend (el finder de meta-path decide por ruta).
while str(PROJECT_ROOT) in sys.path:
    sys.path.remove(str(PROJECT_ROOT))
if ARIA_APP_BACKEND not in sys.path:
    sys.path.insert(0, ARIA_APP_BACKEND)


class _DualBackendFinder:
    """Importa backend.* de ARIA_APP/backend (prioridad) o project-root/backend.

    ARIA_APP/backend/agents/base.py re-exporta modulos del project-root
    (backend.agents.react_loop, backend.permissions, ...), asi que el paquete
    ``backend`` se busca en ambas rutas: ARIA_APP primero (asi backend.agent.core
    resuelve a ARIA_APP) y project-root como fallback. El motor de permisos real
    (unico) se inyecta en backend.permissions antes de cualquier import.
    """

    _search = [_PROJECT_BACKEND, ARIA_APP_BACKEND]

    def find_spec(self, fullname, path=None, target=None):
        if fullname != "backend" and not fullname.startswith("backend."):
            return None
        parts = fullname.split(".")
        # ``backend`` is the package name itself, so its contents live directly
        # under each search root; drop the leading "backend" when joining.
        rel_parts = parts[1:] if parts[0] == "backend" else parts
        for base in self._search:
            if not rel_parts:
                if os.path.isdir(base):
                    init = os.path.join(base, "__init__.py")
                    if os.path.exists(init):
                        return importlib.util.spec_from_file_location(
                            fullname, init, submodule_search_locations=[base],
                        )
                    return importlib.util.spec_from_file_location(
                        fullname, None, submodule_search_locations=[base],
                    )
                continue
            pkg_dir = os.path.join(base, *rel_parts)
            if os.path.isdir(pkg_dir):
                init = os.path.join(pkg_dir, "__init__.py")
                if os.path.exists(init):
                    return importlib.util.spec_from_file_location(
                        fullname, init, submodule_search_locations=[pkg_dir],
                    )
                # namespace package (no __init__.py) - still searchable
                return importlib.util.spec_from_file_location(
                    fullname, None, submodule_search_locations=[pkg_dir],
                )
            mod_file = os.path.join(base, *rel_parts) + ".py"
            if os.path.isfile(mod_file):
                return importlib.util.spec_from_file_location(fullname, mod_file)
        return None


sys.meta_path.insert(0, _DualBackendFinder())

# ``backend`` package itself: ARIA_APP/backend is the root, so the package
# __init__ lives there. Submodules are resolved by the finder.
_backend_spec = importlib.util.spec_from_file_location(
    "backend",
    os.path.join(ARIA_APP_BACKEND, "__init__.py"),
    submodule_search_locations=[ARIA_APP_BACKEND, _PROJECT_BACKEND],
)
sys.modules["backend"] = importlib.util.module_from_spec(_backend_spec)
_backend_spec.loader.exec_module(sys.modules["backend"])
# project-root/backend has namespace subpackages (services, agent, ...) without
# __init__.py; expose them via the package __path__ too.
sys.modules["backend"].__path__.append(_PROJECT_BACKEND)
sys.modules["backend.permissions"] = _real_perm  # unico motor real

_app_spec = _ilu.spec_from_file_location(
    "aria_app_under_test",
    str(PROJECT_ROOT / "ARIA_APP" / "backend" / "app.py"),
)
aria_app_module = _ilu.module_from_spec(_app_spec)
assert _app_spec.loader is not None
_app_spec.loader.exec_module(aria_app_module)

# Approval token for the module-scoped TestClient. Kept in a module global (never
# the literal "hueco1c-..." string in the repo) so function-scoped engine resets
# can re-apply it without losing the shared client's auth state.
_MODULE_TOKEN: Optional[str] = None


@pytest.fixture(scope="module")
def client():
    """Shared TestClient over ARIA_APP/backend/app.py.

    Import time is ~16 s because the full v4 stack wires up; that is why the
    client is module-scoped instead of function-scoped. The approval token is
    generated at runtime so its literal never lands in the repo.
    """
    token = "hueco1c-" + secrets.token_hex(16)
    reset_permission_engine()
    engine = get_permission_engine()
    engine.set_auth_token(token)
    global _MODULE_TOKEN
    _MODULE_TOKEN = token
    with TestClient(aria_app_module.app) as c:
        yield c, token
    _MODULE_TOKEN = None
    reset_permission_engine()


@pytest.fixture(scope="module")
def _module_token():
    """The approval token for this module, kept out of the repo literal."""
    return _MODULE_TOKEN


@pytest.fixture(autouse=True)
def _clean_engine():
    """Each test starts from a fresh engine (no leftover ask requests).

    The approval token set by ``client`` is re-applied after the reset so the
    module-scoped TestClient keeps working across function-scoped resets.
    """
    reset_permission_engine()
    if _MODULE_TOKEN:
        get_permission_engine().set_auth_token(_MODULE_TOKEN)
    yield
    reset_permission_engine()


@pytest.fixture(autouse=True)
def _instant_ask(monkeypatch):
    """Ask-mode tests never wait for a real human: the wait returns at once."""
    monkeypatch.setenv("AURA_ASK_TIMEOUT", "0")

# ============================================================ 4. HTTP auth gate

def _post_approve(client, request_id, token=None, approve=True):
    body = {"request_id": request_id, "approve": approve}
    if token is not None:
        body["token"] = token
    return client.post("/api/permissions/approve", json=body)


def test_approve_no_token_returns_401(client):
    c, _ = client
    r = _post_approve(c, "any-req", token=None)
    assert r.status_code == 401


def test_approve_wrong_token_returns_401(client):
    c, _ = client
    r = _post_approve(c, "any-req", token="wrong")
    assert r.status_code == 401


def test_approve_unknown_request_with_valid_token_returns_400(client):
    c, token = client
    r = _post_approve(c, "does-not-exist", token=token)
    assert r.status_code == 400


def test_pending_no_token_returns_401(client):
    c, _ = client
    assert c.get("/api/permissions/pending").status_code == 401


def test_pending_wrong_token_returns_401(client):
    c, _ = client
    r = c.get("/api/permissions/pending", params={"token": "wrong"})
    assert r.status_code == 401


def test_pending_valid_token_returns_list(client):
    c, token = client
    r = c.get("/api/permissions/pending", params={"token": token})
    assert r.status_code == 200
    body = r.json()
    assert "pending" in body and "count" in body


def test_audit_no_token_returns_401(client):
    c, _ = client
    assert c.get("/api/permissions/audit").status_code == 401


def test_audit_wrong_token_returns_401(client):
    c, _ = client
    r = c.get("/api/permissions/audit", params={"token": "wrong"})
    assert r.status_code == 401


def test_audit_valid_token_returns_log(client):
    c, token = client
    r = c.get("/api/permissions/audit", params={"token": token})
    assert r.status_code == 200
    body = r.json()
    assert "recent_decisions" in body or "events" in body


def test_no_auth_token_configured_returns_503(client, monkeypatch):
    """With no token configured the endpoints fail-closed with 503."""
    c, _ = client
    reset_permission_engine()
    engine = get_permission_engine()
    engine.config.auth_token_hash = None
    engine.save_config()
    assert c.get("/api/permissions/pending", params={"token": "x"}).status_code == 503


def test_approve_replay_rejected(client):
    """A request approved once cannot be approved again (single-use)."""
    import asyncio

    c, token = client
    reset_permission_engine()
    engine = get_permission_engine()
    engine.set_auth_token(token)

    from backend.agents.orchestrator import ToolConnector

    tc = ToolConnector()
    result = asyncio.run(tc.execute("browser", {"url": "https://example.com"}))
    ask_id = result.metadata.get("ask_request_id")
    assert ask_id is not None

    r1 = _post_approve(c, ask_id, token=token, approve=True)
    assert r1.status_code == 200

    r2 = _post_approve(c, ask_id, token=token, approve=True)
    assert r2.status_code == 400
    assert "already decided" in r2.json().get("message", "").lower()

# ============================================================ 5. Token hygiene

def test_token_literal_not_in_repo():
    """The approval token literal must not exist anywhere in the repo."""
    import subprocess

    token = "hueco1c-"
    res = subprocess.run(
        ["git", "grep", "--fixed-strings", token],
        cwd=str(PROJECT_ROOT), capture_output=True, text=True,
    )
    assert res.returncode != 0, "token literal found in tracked files"


def test_token_only_from_env():
    """ARIA_APPROVAL_TOKEN is read from env; the plaintext is never stored,
    only the sha256 hash."""
    monkey_token = "env-token-9f3a"
    old = os.environ.get("ARIA_APPROVAL_TOKEN")
    os.environ["ARIA_APPROVAL_TOKEN"] = monkey_token
    try:
        reset_permission_engine()
        cfg = PermissionConfig(tools={})
        engine = PermissionEngine(config=cfg)
        assert engine.config.auth_token_hash is not None
        assert engine.config.auth_token_hash == hashlib.sha256(
            monkey_token.encode()).hexdigest()
        assert engine.config.auth_token_hash != monkey_token
    finally:
        if old is None:
            os.environ.pop("ARIA_APPROVAL_TOKEN", None)
        else:
            os.environ["ARIA_APPROVAL_TOKEN"] = old
        reset_permission_engine()


def test_token_not_in_audit_log():
    """The audit log never contains the plaintext token."""
    reset_permission_engine()
    engine = get_permission_engine()
    engine.set_auth_token("super-secret-token-xyz")
    engine.allow_tool("t.audit", "safe")
    engine.check("t.audit", "safe", {"a": "super-secret-token-xyz"})
    blob = __import__("json").dumps(engine.audit())
    assert "super-secret-token-xyz" not in blob
    reset_permission_engine()


def test_token_not_in_canonical_args():
    """_canonical_args redacts token-like keys so the args hash + audit never
    leak the plaintext."""
    reset_permission_engine()
    engine = get_permission_engine()
    engine.set_auth_token("super-secret-token-xyz")
    canon = engine._canonical_args({"config_token": "super-secret-token-xyz"})
    assert "super-secret-token-xyz" not in canon
    reset_permission_engine()

# ============================================================ 6. read_file/list_dir
#    path policy (roots by env, realpath first, always-deny secrets)

def _tmp_under_data():
    """A scratch file inside the default AURA data root."""
    import tempfile
    data_root = Path(os.environ.get("AURA_DATA_DIR", "data")).resolve()
    fd, path = tempfile.mkstemp(suffix=".txt", dir=str(data_root))
    os.close(fd)
    Path(path).write_text("hello")
    return path


def test_path_inside_default_root_is_allowed():
    reset_permission_engine()
    engine = get_permission_engine()
    p = _tmp_under_data()
    try:
        decision, reason, _ = engine.check_path(p)
        assert decision == "allow", reason
    finally:
        os.unlink(p)
    reset_permission_engine()


def test_path_outside_root_is_ask():
    reset_permission_engine()
    engine = get_permission_engine()
    decision, reason, _ = engine.check_path(os.path.expanduser("~/.bashrc"))
    assert decision == "ask", reason
    reset_permission_engine()


def test_path_dotenv_always_denied():
    reset_permission_engine()
    engine = get_permission_engine()
    decision, reason, _ = engine.check_path(os.path.expanduser("~/.env"))
    assert decision == "deny"
    assert "always-denied" in reason.lower() or "secret" in reason.lower()
    reset_permission_engine()


def test_path_pem_always_denied():
    reset_permission_engine()
    engine = get_permission_engine()
    decision, reason, _ = engine.check_path(os.path.expanduser("~/.ssh/id_ed25519.pem"))
    assert decision == "deny"
    reset_permission_engine()


def test_path_dotgit_config_always_denied():
    reset_permission_engine()
    engine = get_permission_engine()
    decision, reason, _ = engine.check_path(os.path.expanduser("~/.git/config"))
    assert decision == "deny"
    reset_permission_engine()


def test_path_kilo_always_denied():
    reset_permission_engine()
    engine = get_permission_engine()
    decision, reason, _ = engine.check_path(os.path.expanduser("~/.kilo/state.json"))
    assert decision == "deny"
    reset_permission_engine()


def test_path_parent_traversal_blocked():
    """'..' cannot escape the data root: realpath is applied first."""
    reset_permission_engine()
    engine = get_permission_engine()
    data_root = Path(os.environ.get("AURA_DATA_DIR", "data")).resolve()
    traversal = str(data_root / ".." / ".." / ".env")
    decision, reason, _ = engine.check_path(traversal)
    assert decision == "deny", (decision, reason)
    reset_permission_engine()


def test_env_roots_override_default(monkeypatch):
    """ARIA_FS_ROOTS replaces the default single-root policy."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        monkeypatch.setenv("ARIA_FS_ROOTS", td)
        # Force re-read of the module-level FS_ROOTS by reloading the engine
        # module constants through a fresh engine.
        import importlib
        import backend.permissions.engine as eng_mod
        importlib.reload(eng_mod)
        try:
            e = eng_mod.PermissionEngine()
            inside = Path(td) / "ok.txt"
            inside.write_text("x")
            assert e.check_path(str(inside))[0] == "allow"
            assert e.check_path(os.path.expanduser("~/.bashrc"))[0] == "ask"
        finally:
            inside.unlink(missing_ok=True)
            monkeypatch.delenv("ARIA_FS_ROOTS", raising=False)
            importlib.reload(eng_mod)
    reset_permission_engine()


def test_read_file_handler_respects_path_policy():
    """The real _read_file handler denies always-denied paths even though the
    tool itself is allow=True in the default policy."""
    import asyncio
    from backend.agents.orchestrator import ToolConnector, ToolResultStatus

    reset_permission_engine()
    tc = ToolConnector()
    result = asyncio.run(tc.execute("read_file", {"path": os.path.expanduser("~/.env")}))
    assert result.status == ToolResultStatus.FAILED
    assert "permission denied" in result.error.lower()
    reset_permission_engine()


def test_list_dir_handler_respects_path_policy():
    import asyncio
    from backend.agents.orchestrator import ToolConnector, ToolResultStatus

    reset_permission_engine()
    tc = ToolConnector()
    result = asyncio.run(tc.execute("list_dir", {"path": os.path.expanduser("~/.ssh")}))
    assert result.status == ToolResultStatus.FAILED
    assert "permission denied" in result.error.lower()
    reset_permission_engine()


def test_read_file_inside_root_executes():
    import asyncio
    from backend.agents.orchestrator import ToolConnector, ToolResultStatus

    reset_permission_engine()
    p = _tmp_under_data()
    try:
        tc = ToolConnector()
        result = asyncio.run(tc.execute("read_file", {"path": str(p)}))
        assert result.status == ToolResultStatus.SUCCESS
        assert "hello" in result.output
    finally:
        os.unlink(p)
    reset_permission_engine()


def test_read_file_outside_root_asks():
    import asyncio
    from backend.agents.orchestrator import ToolConnector, ToolResultStatus

    reset_permission_engine()
    tc = ToolConnector()
    result = asyncio.run(tc.execute("read_file", {"path": os.path.expanduser("~/.bashrc")}))
    assert result.status == ToolResultStatus.FAILED
    assert result.metadata.get("ask_request_id") is not None
    reset_permission_engine()

class TestExecutionLevelApproval:
    """Sin aprobacion el callable real NO se llama. Con aprobacion exacta se
    llama UNA vez. Reuso o args distintos -> no se llama."""

    @pytest.mark.asyncio
    async def test_ask_tool_creates_pending_and_does_not_execute(self):
        from backend.agents.orchestrator import ToolConnector, ToolResultStatus

        reset_permission_engine()
        calls = []

        async def fake_browser(params):
            calls.append(dict(params))
            return "opened"

        tc = ToolConnector()
        tc._browser_action = fake_browser

        result = await tc.execute("browser", {"url": "https://example.com"})
        assert result.status == ToolResultStatus.FAILED
        assert "permission" in result.error.lower()
        assert calls == []
        assert result.metadata.get("ask_request_id") is not None
        reset_permission_engine()

    @pytest.mark.asyncio
    async def test_exact_approval_calls_handler_once(self):
        from backend.agents.orchestrator import ToolConnector, ToolResultStatus
        from backend.permissions import get_permission_engine

        reset_permission_engine()
        engine = get_permission_engine()
        engine.set_auth_token("test-token")

        calls = []

        def fake_write_file(params):
            calls.append(dict(params))
            from backend.agents.orchestrator import ToolResult
            return ToolResult(tool="write_file",
                              status=ToolResultStatus.SUCCESS, output="OK")

        tc = ToolConnector()
        tc._write_file = fake_write_file
        args = {"path": "/tmp/hueco1c.txt", "content": "hello world"}

        # 1) Without approval the handler is never called.
        result = await tc.execute("write_file", args)
        assert result.status == ToolResultStatus.FAILED
        assert calls == []
        ask_id = result.metadata.get("ask_request_id")
        assert ask_id is not None

        # 2) Approve, then re-run with EXACT same args -> handler called once.
        success, _ = engine.approve_request(ask_id, "test-token", approve=True)
        assert success is True

        result2 = await tc.execute("write_file", args)
        assert result2.status == ToolResultStatus.SUCCESS, result2.error
        assert len(calls) == 1
        assert calls[0] == args

        # 3) Different args -> handler NOT called again.
        calls.clear()
        result3 = await tc.execute("write_file",
                                   {"path": "/tmp/hueco1c.txt", "content": "different"})
        assert result3.status == ToolResultStatus.FAILED
        assert "permission" in result3.error.lower()
        assert calls == []

        if os.path.exists("/tmp/hueco1c.txt"):
            os.unlink("/tmp/hueco1c.txt")
        reset_permission_engine()

    @pytest.mark.asyncio
    async def test_require_confirm_enforced_by_registry(self):
        """DynamicToolRegistry.execute_tool also honours require_confirm."""
        from backend.agents.tools_registry import DynamicToolRegistry
        from backend.permissions import get_permission_engine

        reset_permission_engine()
        engine = get_permission_engine()
        assert engine.config.tools["write_file"].require_confirm is True

        reg = DynamicToolRegistry(scripts_dir=None, auto_scan=False)
        reg.register_callable(
            "write_file",
            lambda **kw: "wrote",
            "write",
            {"type": "object",
             "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
             "required": ["path", "content"]},
        )
        out = await reg.execute_tool("write_file",
                                     {"path": "/tmp/x.txt", "content": "x"})
        assert out["success"] is False
        assert "permission" in out["error"].lower()
        reset_permission_engine()
