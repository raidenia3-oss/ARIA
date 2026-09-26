# -*- coding: utf-8 -*-
"""AURA OS — tests for cloud sync."""

import asyncio
import os
import sys

import pytest
from fastapi import FastAPI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.mark.asyncio
async def test_firebase_sync_init():
    from backend.cloud.firebase_manager import FirebaseSync

    fs = FirebaseSync(project_id="test-aura")
    result = await fs.init_firebase()
    assert result["status"] in ("connected", "simulated")
    assert fs.initialized is True


@pytest.mark.asyncio
async def test_firebase_sync_device_roundtrip():
    from backend.cloud.firebase_manager import FirebaseSync

    fs = FirebaseSync(project_id="test-aura")
    await fs.init_firebase()

    await fs.push_to_cloud("test_pc", {"key1": "value1"})
    devices = await fs.get_device_list()
    assert any(d["device_id"] == "test_pc" for d in devices)

    result = await fs.pull_from_cloud("test_pc", since_version=0)
    assert result["version"] >= 0
    assert "key1" in result["delta"]

    deleted = await fs.delete_device("test_pc")
    assert deleted["deleted"] is True


@pytest.mark.asyncio
async def test_offline_queue_basic():
    import tempfile

    from backend.cloud.offline_queue import OfflineQueue

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    try:
        oq = OfflineQueue(db_path=tmp)
        action_id = await oq.queue_action(
            {
                "device_id": "pc_001",
                "action": "test",
                "data": {"foo": "bar"},
            }
        )
        assert action_id.startswith("off_")

        status = await oq.get_queue_status()
        assert status["pending_actions"] >= 1

        retry = await oq.retry_offline_queue()
        assert retry["retried"] >= 0
    finally:
        os.unlink(tmp)


@pytest.mark.asyncio
async def test_cloud_routes_register():
    from fastapi.testclient import TestClient

    from backend.api.cloud_routes import router as cloud_router

    test_app = FastAPI()
    test_app.include_router(cloud_router)
    client = TestClient(test_app)
    resp = client.post(
        "/api/cloud/device/register",
        json={
            "device_id": "test_device_001",
            "device_type": "desktop",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["token"]
    assert data["sync_enabled"] is True


@pytest.mark.asyncio
async def test_cloud_routes_push_pull():
    from fastapi.testclient import TestClient

    from backend.api.cloud_routes import router as cloud_router

    test_app = FastAPI()
    test_app.include_router(cloud_router)
    client = TestClient(test_app)

    reg = client.post(
        "/api/cloud/device/register",
        json={
            "device_id": "test_dp_001",
            "device_type": "desktop",
        },
    )
    assert reg.status_code == 200

    push = client.post(
        "/api/cloud/sync/push",
        json={
            "device_id": "test_dp_001",
            "data": {"test": "value"},
        },
    )
    assert push.status_code == 200
    assert push.json()["status"] == "synced"

    pull = client.get(
        "/api/cloud/sync/pull",
        params={
            "device_id": "test_dp_001",
            "since_version": 0,
        },
    )
    assert pull.status_code == 200
    assert "delta" in pull.json()


@pytest.mark.asyncio
async def test_cloud_routes_devices():
    from fastapi.testclient import TestClient

    from backend.api.cloud_routes import router as cloud_router

    test_app = FastAPI()
    test_app.include_router(cloud_router)
    client = TestClient(test_app)

    client.post(
        "/api/cloud/device/register",
        json={
            "device_id": "dev_001",
            "device_type": "desktop",
        },
    )
    client.post(
        "/api/cloud/device/register",
        json={
            "device_id": "dev_002",
            "device_type": "mobile",
        },
    )

    resp = client.get("/api/cloud/devices")
    assert resp.status_code == 200
    devices = resp.json()
    assert len(devices) >= 2


@pytest.mark.asyncio
async def test_cloud_routes_conflict_resolve():
    from fastapi.testclient import TestClient

    from backend.api.cloud_routes import router as cloud_router

    test_app = FastAPI()
    test_app.include_router(cloud_router)
    client = TestClient(test_app)
    client.post(
        "/api/cloud/device/register",
        json={
            "device_id": "pc_001",
            "device_type": "desktop",
        },
    )
    resp = client.post(
        "/api/cloud/conflict/resolve",
        json={
            "device_id": "pc_001",
            "conflict_id": "conf_test_001",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["resolved"] is True
    assert data["winner"] == "pc_001"


@pytest.mark.asyncio
async def test_migration_manager():
    from backend.migration.migrate_to_cloud import MigrationManager

    mm = MigrationManager()
    result = await mm.migrate_sqlite_to_postgres()
    assert "migrated" in result
    assert "failed" in result
    assert result["failed"] == 0


@pytest.mark.asyncio
async def test_daemon_cloud_status():
    from backend.daemon.aura_daemon_cloud import aura_daemon_cloud

    status = aura_daemon_cloud.get_cloud_status()
    assert status is not None
    assert "connected" in status
    assert "cloud_active" in status


@pytest.mark.asyncio
async def test_railway_deploy_config():
    from railway_deploy import RAILWAY_ENV_VARS, deploy_to_railway

    assert len(RAILWAY_ENV_VARS) > 0
    assert "DATABASE_URL" in RAILWAY_ENV_VARS
    result = await deploy_to_railway()
    assert result["success"] is True


def test_offline_queue_sqlite_paths():
    from backend.cloud.offline_queue import OfflineQueue

    oq = OfflineQueue()
    assert oq._buffer_limit == 100
