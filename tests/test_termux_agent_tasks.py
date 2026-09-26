import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

pytest.importorskip(
    "AME_EXPORT_PACKAGE.TERMUX_AGENT.server",
    reason="AME_EXPORT_PACKAGE/TERMUX_AGENT no existe en el repo",
)

from AME_EXPORT_PACKAGE.TERMUX_AGENT import server as termux_server


def test_agent_task_lifecycle():
    termux_server.AGENT_BUFFER["pending_tasks"].clear()

    created = asyncio.run(
        termux_server.create_agent_task(
            termux_server.AgentTaskRequest(
                node_id="termux-test",
                description="ejecutar prueba de integración",
                task_type="healthcheck",
                metadata={"command": "echo ok"},
            )
        )
    )

    assert created["status"] == "ok"
    assert created["pending_tasks"] == 1

    fetched = asyncio.run(termux_server.get_agent_tasks(node_id="termux-test"))
    assert fetched["count"] == 1
    assert fetched["tasks"][0]["description"] == "ejecutar prueba de integración"

    completed = asyncio.run(
        termux_server.complete_agent_task(
            termux_server.AgentTaskCompleteRequest(
                node_id="termux-test",
                task_id=created["task_id"],
            )
        )
    )

    assert completed["status"] == "ok"
    assert completed["pending_tasks"] == 0
