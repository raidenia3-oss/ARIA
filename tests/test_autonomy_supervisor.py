import asyncio

import pytest

from backend.autonomy.supervisor import AutonomousSupervisor, get_supervisor


@pytest.mark.asyncio
async def test_supervisor_restarts_on_failure_then_runs():
    sup = AutonomousSupervisor(backoff_base=0.01, max_backoff=0.05)
    state = {"attempts": 0}

    async def flaky():
        state["attempts"] += 1
        if state["attempts"] < 3:
            raise RuntimeError("fallo simulado")
        # tras el reinicio, se mantiene vivo (bloqueado) hasta ser cancelado
        await asyncio.Event().wait()

    sup.run("flaky", flaky)
    await asyncio.sleep(0.15)
    assert state["attempts"] >= 3
    st = sup.status()
    assert st["flaky"]["running"] is True
    assert st["flaky"]["crashes"] == 2
    assert st["flaky"]["last_error"].startswith("RuntimeError")
    sup.cancel("flaky")
    await asyncio.sleep(0.1)
    assert sup.status()["flaky"]["running"] is False


@pytest.mark.asyncio
async def test_supervisor_status_snapshot_liveness():
    sup = AutonomousSupervisor()

    async def eternal():
        await asyncio.Event().wait()

    sup.run("eternal", eternal)
    await asyncio.sleep(0.01)
    st = sup.status()
    assert "eternal" in st
    assert st["eternal"]["running"] is True
    assert st["eternal"]["crashes"] == 0
    assert st["eternal"]["last_error"] is None
    assert st["eternal"]["started_at"] > 0
    sup.cancel("eternal")
    await asyncio.sleep(0.01)
    assert sup.status()["eternal"]["running"] is False


@pytest.mark.asyncio
async def test_supervisor_crash_only_does_not_restart_when_disabled():
    sup = AutonomousSupervisor(backoff_base=0.01, max_backoff=0.05)
    attempts = {"n": 0}

    async def killer():
        attempts["n"] += 1
        raise ValueError("muere")

    sup.run("killer", killer, restart=False)
    await asyncio.sleep(0.2)
    assert attempts["n"] == 1
    st = sup.status()
    assert st["killer"]["running"] is False
    assert st["killer"]["crashes"] == 1


def test_get_supervisor_singleton():
    a = get_supervisor()
    b = get_supervisor()
    assert a is b


@pytest.mark.asyncio
async def test_get_supervisor_singleton_status_empty():
    # singleton compartido: status() debe ser un dict (posiblemente con otros servicios)
    st = get_supervisor().status()
    assert isinstance(st, dict)
