import pytest


@pytest.mark.asyncio
async def test_telemetry_collection():
    from backend.routers.telemetry import _build_payload
    data = _build_payload()
    assert data is not None
    assert "cpu_percent" in data
    assert "ram_percent" in data
