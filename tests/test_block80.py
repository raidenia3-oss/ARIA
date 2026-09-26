"""BLOQUE 80 - Unit tests for Sovereign Bootstrapper & Permanent Daemon."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from backend.daemon.bootstrapper import (
    Bootstrapper,
    DaemonConfig,
    DaemonStore,
    get_daemon_controller,
    reset_daemon_engine,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_daemon_engine()
    yield
    reset_daemon_engine()


def _mk(tmpdir, strategy="windows_task", execute=False, **cfgkw):
    cfg = DaemonConfig(service_name="aura-test", strategy=strategy, **cfgkw)
    store = DaemonStore(store_dir=tmpdir)
    return Bootstrapper(config=cfg, store=store, execute=execute)


# ---------- artefactos de instalacion ----------
def test_windows_task_artifacts(tmp_path):
    b = _mk(str(tmp_path), strategy="windows_task")
    arts = b.generate_all()
    assert "bootstrap.bat" in arts and "schtasks_plan.txt" in arts
    bat = arts["bootstrap.bat"]
    plan = arts["schtasks_plan.txt"]
    assert "aura-test" in plan and "/SC ONSTART" in plan
    assert b.config.entrypoint in bat


def test_systemd_unit_artifacts(tmp_path):
    b = _mk(str(tmp_path), strategy="systemd")
    arts = b.generate_all()
    assert "aura-test.service" in arts
    unit = arts["aura-test.service"]
    assert "ExecStart=" in unit and "Restart=always" in unit


def test_systemd_restart_disabled(tmp_path):
    b = _mk(str(tmp_path), strategy="systemd", restart_on_failure=False)
    arts = b.generate_all()
    assert "Restart=no" in arts["aura-test.service"]


def test_artifacts_written_to_disk(tmp_path):
    b = _mk(str(tmp_path), strategy="windows_task")
    b.generate_all()
    for p in b.artifacts():
        assert os.path.exists(p)


# ---------- instalacion (dry-run por defecto) ----------
def test_install_dry_run_does_not_touch_os(tmp_path):
    b = _mk(str(tmp_path), strategy="windows_task", execute=False)
    res = b.install()  # execute=None -> False
    assert res["installed"] is True and res["executed"] is False
    assert res["artifacts"]


def test_install_persists_autostart(tmp_path):
    b = _mk(str(tmp_path), strategy="windows_task")
    b.install()
    persisted = b.store.load_config()
    assert persisted is not None and persisted.autostart_enabled is True


def test_install_strategy_windows_on_host(tmp_path):
    b = _mk(str(tmp_path), strategy="windows_task")
    res = b.install()
    assert res["strategy"] == "windows_task"
    assert res["autostart"] is True


# ---------- configuracion persistente ----------
def test_configure_toggle_autostart(tmp_path):
    b = _mk(str(tmp_path))
    b.configure(autostart_enabled=False)
    assert b.status()["autostart_enabled"] is False
    b.configure(autostart_enabled=True)
    assert b.status()["autostart_enabled"] is True


def test_configure_max_restarts_clamped(tmp_path):
    b = _mk(str(tmp_path))
    cfg = b.configure(max_restarts=-7)
    assert cfg.max_restarts == 0


def test_store_config_roundtrip(tmp_path):
    store = DaemonStore(store_dir=tmp_path)
    cfg = DaemonConfig(service_name="custom", max_restarts=9)
    store.save_config(cfg)
    loaded = store.load_config()
    assert loaded.service_name == "custom" and loaded.max_restarts == 9


# ---------- desinstalacion ----------
def test_uninstall_removes_artifacts(tmp_path):
    b = _mk(str(tmp_path), strategy="windows_task")
    b.install()
    res = b.uninstall()
    assert res["uninstalled"] is True and res["artifacts_removed"] > 0
    assert b.artifacts() == []
    assert b.store.load_config().autostart_enabled is False


# ---------- ciclo de vida del daemon ----------
def test_controller_start_stop(tmp_path):
    b = _mk(str(tmp_path))
    from backend.daemon.bootstrapper import DaemonController

    ctl = DaemonController(bootstrapper=b)
    assert ctl.start()["ok"] is True
    assert ctl.state()["status"] == "running"
    assert ctl.stop()["ok"] is True
    assert ctl.state()["status"] == "stopped"


def test_controller_restart_counts(tmp_path):
    b = _mk(str(tmp_path))
    from backend.daemon.bootstrapper import DaemonController

    ctl = DaemonController(bootstrapper=b)
    ctl.start()
    res = ctl.restart()
    assert res["ok"] is True
    assert res["restart_count"] == 1
    kinds = [s["kind"] for s in ctl.state()["signals"]]
    assert "restarted" in kinds


def test_controller_start_idempotent(tmp_path):
    b = _mk(str(tmp_path))
    from backend.daemon.bootstrapper import DaemonController

    ctl = DaemonController(bootstrapper=b)
    assert ctl.start()["ok"] is True
    assert ctl.start()["ok"] is False  # ya running


def test_controller_health(tmp_path):
    b = _mk(str(tmp_path))
    from backend.daemon.bootstrapper import DaemonController

    ctl = DaemonController(bootstrapper=b)
    ctl.start()
    h = ctl.health()
    assert h["ok"] is True and h["status"] == "running"


# ---------- persistencia de estado ----------
def test_state_persisted(tmp_path):
    b = _mk(str(tmp_path))
    from backend.daemon.bootstrapper import DaemonController

    ctl = DaemonController(bootstrapper=b)
    ctl.start()
    loaded = b.store.load_state()
    assert loaded is not None and loaded.status == "running"


# ---------- singleton ----------
def test_singleton_isolation(tmp_path):
    reset_daemon_engine()
    e1 = get_daemon_controller()
    e2 = get_daemon_controller()
    assert e1 is e2
    reset_daemon_engine()
    e3 = get_daemon_controller()
    assert e3 is not e1
