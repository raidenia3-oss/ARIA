import asyncio
import json
import os
import sys
import tempfile

sys.path.insert(0, ".")

from fastapi import FastAPI
from fastapi.testclient import TestClient

# Create a minimal app with just cloud routes
test_app = FastAPI()
from backend.api.cloud_routes import router as cloud_router

test_app.include_router(cloud_router)

client = TestClient(test_app)

print("Testing Cloud Routes via FastAPI TestClient...")

# Test device registration
resp = client.post(
    "/api/cloud/device/register",
    json={
        "device_id": "pc_001",
        "device_type": "desktop",
    },
)
assert resp.status_code == 200
data = resp.json()
assert data["token"]
assert data["sync_enabled"] is True
assert data["device_id"] == "pc_001"
print("  Device register: OK")

# Test sync push
resp = client.post(
    "/api/cloud/sync/push",
    json={
        "device_id": "pc_001",
        "data": {"message": "hello from PC"},
    },
)
assert resp.status_code == 200
data = resp.json()
assert data["status"] == "synced"
print("  Sync push: OK")

# Test sync pull
resp = client.get(
    "/api/cloud/sync/pull",
    params={
        "device_id": "pc_001",
        "since_version": 0,
    },
)
assert resp.status_code == 200
data = resp.json()
assert "delta" in data
assert "version" in data
print("  Sync pull: OK")

# Test get devices
resp = client.get("/api/cloud/devices")
assert resp.status_code == 200
devices = resp.json()
assert len(devices) >= 1
assert devices[0]["device_id"] == "pc_001"
print("  Get devices: OK")

# Test conflict resolution
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
print("  Conflict resolve: OK")

# Test error handling - missing device_id
resp = client.post("/api/cloud/device/register", json={"device_type": "desktop"})
assert resp.status_code == 422
print("  Error handling: OK")

# Test multiple devices
client.post("/api/cloud/device/register", json={"device_id": "mobile_001", "device_type": "mobile"})
client.post("/api/cloud/device/register", json={"device_id": "web_001", "device_type": "web"})

resp = client.get("/api/cloud/devices")
devices = resp.json()
device_ids = [d["device_id"] for d in devices]
assert "pc_001" in device_ids
assert "mobile_001" in device_ids
assert "web_001" in device_ids
print("  Multi-device: OK (3 devices)")

print("")
print("All cloud route tests passed!")
