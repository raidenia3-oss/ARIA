import asyncio
import os
import sys
import tempfile

sys.path.insert(0, ".")

from backend.cloud.firebase_manager import FirebaseSync


async def test_fs():
    fs = FirebaseSync(project_id="test-aura")
    r = await fs.init_firebase()
    assert r["status"] in ("connected", "simulated")
    r2 = await fs.push_to_cloud("pc_001", {"hello": "world", "num": 42})
    assert r2["status"] == "pushed"
    r3 = await fs.sync_device("pc_001", {"key1": "val1"})
    assert r3["status"] == "synced"
    devices = await fs.get_device_list()
    assert any(d["device_id"] == "pc_001" for d in devices)
    r4 = await fs.pull_from_cloud("pc_001", since_version=0)
    assert r4["version"] >= 0
    r5 = await fs.delete_device("pc_001")
    assert r5["deleted"] is True
    print("  FirebaseSync: All OK")


asyncio.run(test_fs())

from backend.cloud.offline_queue import OfflineQueue


async def test_oq():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    try:
        oq = OfflineQueue(db_path=tmp)
        aid = await oq.queue_action({"device_id": "pc_001", "action": "test", "data": {"x": 1}})
        assert aid.startswith("off_")
        status = await oq.get_queue_status()
        assert status["pending_actions"] >= 1
        retry = await oq.retry_offline_queue()
        assert "retried" in retry
        print("  OfflineQueue: All OK")
    finally:
        os.unlink(tmp)


asyncio.run(test_oq())

from backend.daemon.aura_daemon_cloud import aura_daemon_cloud

s = aura_daemon_cloud.get_cloud_status()
assert s is not None
assert "connected" in s
assert "cloud_active" in s
print("  DaemonCloud: All OK")

from backend.migration.migrate_to_cloud import MigrationManager

mm = MigrationManager()
result = asyncio.run(mm.migrate_sqlite_to_postgres())
assert "migrated" in result
assert "failed" in result
mval = result.get("migrated", 0)
print("  Migration: OK (simulated, " + str(mval) + " rows)")


async def test_device_sync():
    fs = FirebaseSync(project_id="test-sync")
    await fs.init_firebase()
    await fs.push_to_cloud("device_A", {"msg": "hello"})
    await fs.push_to_cloud("device_B", {"msg": "world"})
    devices = await fs.get_device_list()
    ids = [d["device_id"] for d in devices]
    assert "device_A" in ids
    assert "device_B" in ids
    print("  Multi-device sync: OK")


asyncio.run(test_device_sync())

print("")
print("All integration tests passed!")
