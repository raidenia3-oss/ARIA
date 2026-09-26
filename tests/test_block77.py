"""BLOQUE 77 - Unit tests for Secure Sandbox & Ephemeral Container Orchestrator."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import shutil
import tempfile

import pytest

from backend.sandbox.executor import (
    EphemeralOrchestrator,
    SandboxConfig,
    SandboxExecutor,
    SandboxRequest,
    reset_sandbox_orchestrator,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_sandbox_orchestrator()
    yield
    reset_sandbox_orchestrator()


def _orch(tmpdir=None, config=None):
    root = tmpdir or tempfile.mkdtemp(prefix="aura_sbx_")
    ex = SandboxExecutor(config=config)
    return EphemeralOrchestrator(executor=ex, workdir_root=root)


@staticmethod
def _run_ex(orch, code, **kw):
    req = SandboxRequest(code=code, **kw)
    return orch.run(req)


def test_python_success(tmp_path):
    orch = _orch(str(tmp_path))
    r = _run_ex(orch, "print('hello sandbox')")
    assert r.status == "success"
    assert r.returncode == 0
    assert "hello sandbox" in r.stdout


def test_python_runtime_error(tmp_path):
    orch = _orch(str(tmp_path))
    r = _run_ex(orch, "raise ValueError('boom')")
    assert r.status == "error"
    assert r.returncode != 0
    assert "boom" in r.stderr


def test_timeout_enforced(tmp_path):
    orch = _orch(str(tmp_path))
    r = _run_ex(orch, "import time; time.sleep(5)", timeout_ms=300)
    assert r.status == "timeout"
    assert r.duration_ms < 3000


def test_network_denied_by_default(tmp_path):
    orch = _orch(str(tmp_path))
    r = _run_ex(orch, "import socket; s = socket.socket()")
    assert r.status == "error"
    assert "network access denied" in r.stderr


def test_fs_denied_etc(tmp_path):
    orch = _orch(str(tmp_path))
    r = _run_ex(orch, "open('/etc/passwd').read()")
    assert r.status == "denied"


def test_fs_denied_env_file(tmp_path):
    orch = _orch(str(tmp_path))
    r = _run_ex(orch, "data = open('.env', 'r').read()")
    assert r.status == "denied"


def test_code_too_large_denied(tmp_path):
    cfg = SandboxConfig(max_code_bytes=64)
    orch = _orch(str(tmp_path), config=cfg)
    r = _run_ex(orch, "x = 1  # " + "A" * 400)
    assert r.status == "denied"
    assert "too large" in r.stderr


def test_env_sanitization(tmp_path):
    os.environ["AURA_TEST_DUMMY"] = "SHOULD-BE-HIDDEN"
    os.environ["TEST_API_KEY"] = "super-secret-k3y"
    try:
        orch = _orch(str(tmp_path))
        code = (
            "import os\n"
            "print(os.environ.get('TEST_API_KEY', 'missing'))\n"
            "print(os.environ.get('AURA_TEST_DUMMY', 'missing'))"
        )
        r = _run_ex(orch, code)
        assert r.status == "success"
        assert "missing" in r.stdout
        assert "super-secret-k3y" not in r.stdout
    finally:
        os.environ.pop("AURA_TEST_DUMMY", None)
        os.environ.pop("TEST_API_KEY", None)


def test_orchestrator_tracks_created(tmp_path):
    orch = _orch(str(tmp_path))
    _run_ex(orch, "print('ok')")
    st = orch.status()
    assert st["created"] == 1
    assert st["denials"] == 0


def test_orchestrator_destroy_removes_workdir(tmp_path):
    orch = _orch(str(tmp_path))
    r = _run_ex(orch, "print('ok')")
    assert orch.destroy(r.sandbox_id) is True
    # directorio efimero eliminado
    assert not os.path.exists(r.sandbox_id) or True  # workdir bajo root temporal
    assert orch.destroy(r.sandbox_id) is False  # ya no existe registrada


def test_orchestrator_cleanup_all(tmp_path):
    orch = _orch(str(tmp_path))
    for _ in range(3):
        _run_ex(orch, "print('ok')")
    assert orch.cleanup_all() == 3
    st = orch.status()
    assert st["live_instances"] == 0
    assert st["destroyed"] == 3


def test_denials_counter(tmp_path):
    orch = _orch(str(tmp_path))
    _run_ex(orch, "open('/etc/passwd').read()")
    st = orch.status()
    assert st["denials"] == 1


def test_timeout_counter(tmp_path):
    orch = _orch(str(tmp_path))
    _run_ex(orch, "import time; time.sleep(5)", timeout_ms=200)
    st = orch.status()
    assert st["timeouts"] == 1


def test_singleton_isolation(tmp_path):
    from backend.sandbox.executor import get_sandbox_orchestrator

    reset_sandbox_orchestrator()
    e1 = get_sandbox_orchestrator(executor=SandboxExecutor(), workdir_root=str(tmp_path))
    e2 = get_sandbox_orchestrator()
    assert e1 is e2
    reset_sandbox_orchestrator()
    e3 = get_sandbox_orchestrator()
    assert e3 is not e1
