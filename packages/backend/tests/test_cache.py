import pytest


@pytest.mark.asyncio
async def test_redis_cache_set_get():
    from backend.cache.redis_client import redis_cache
    await redis_cache.connect()
    if redis_cache.client is None:
        pytest.skip("Redis no disponible en este entorno")
    await redis_cache.set("test_key", {"a": 1}, ttl=5)
    value = await redis_cache.get("test_key")
    assert value == {"a": 1}
    await redis_cache.delete("test_key")
    assert await redis_cache.get("test_key") is None
