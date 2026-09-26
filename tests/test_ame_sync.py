# -*- coding: utf-8 -*-
"""AURA OS - Tests for AME Sync (PC <-> Mobile)."""

from __future__ import annotations

import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.api.ame_sync_routes import router as ame_router
from backend.daemon.aura_daemon import get_daemon
from backend.integrations.ame_sync_manager import AMESyncManager, get_ame_sync
from mobile_client.ame_sync_receiver import AMESyncReceiver, get_ame_receiver


def test_prepare_lora():
    ame = AMESyncManager()
    result = asyncio.run(ame.prepare_lora_for_sync())
    assert "lora_path" in result
    assert "size_mb" in result
    assert "checksum" in result
    assert len(result["checksum"]) == 32
    print("✅ test_prepare_lora PASSED")


def test_send_lora_to_ame():
    ame = AMESyncManager()
    result = asyncio.run(ame.send_lora_to_ame())
    assert result["success"] is True
    assert result["size_mb"] > 0
    assert "checksum" in result
    assert result["ame_improvement"] > 0
    print("✅ test_send_lora_to_ame PASSED")


def test_receive_ame_insights():
    ame = AMESyncManager()
    insights = asyncio.run(ame.receive_ame_insights())
    assert isinstance(insights, list)
    assert len(insights) > 0
    assert all("title" in i for i in insights)
    print("✅ test_receive_ame_insights PASSED")


def test_sync_bidirectional():
    ame = AMESyncManager()
    result = asyncio.run(ame.sync_bidirectional())
    assert result["lora_sent_mb"] > 0
    assert result["insights_received"] > 0
    assert "timestamp" in result
    assert ame.lora_version == 1
    print("✅ test_sync_bidirectional PASSED")


def test_ame_sync_endpoints():
    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    r = client.get("/api/ame/sync/status")
    assert r.status_code == 200
    data = r.json()
    assert "ame_connected" in data
    assert "lora_version" in data
    r2 = client.post("/api/ame/sync/now")
    assert r2.status_code == 200
    assert r2.json()["success"] is True
    r3 = client.get("/api/ame/sync/log")
    assert r3.status_code == 200
    assert "sync_log" in r3.json()
    print("✅ test_ame_sync_endpoints PASSED")


def test_ame_mobile_receiver():
    receiver = AMESyncReceiver()
    lora_ok = asyncio.run(receiver.receive_lora_from_pc())
    assert lora_ok is True
    training = asyncio.run(receiver.train_ame_local())
    assert training["improvement_percent"] > 0
    insights_ok = asyncio.run(receiver.send_insights_to_pc())
    assert insights_ok is True
    cycle = asyncio.run(receiver.ame_sync_cycle())
    assert cycle["lora_received"] is True
    assert cycle["insights_sent"] is True
    print("✅ test_ame_mobile_receiver PASSED")


def test_daemon_ame_sync_integration():
    daemon = get_daemon()
    assert hasattr(daemon, "ame_sync")
    assert isinstance(daemon.ame_sync, AMESyncManager)
    assert hasattr(daemon, "_run_ame_sync_agent")
    print("✅ test_daemon_ame_sync_integration PASSED")


if __name__ == "__main__":
    test_prepare_lora()
    test_send_lora_to_ame()
    test_receive_ame_insights()
    test_sync_bidirectional()
    test_ame_sync_endpoints()
    test_ame_mobile_receiver()
    test_daemon_ame_sync_integration()
    print("\n🎉 ALL AME SYNC TESTS PASSED")
