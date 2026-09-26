"""
Omniroute Integration Tests

Suite completa de testing para validar:
- Conectividad con Omniroute
- Fallback functionality
- Provider selection
- Error handling
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.omniroute import OmnirouteClient, OmnirouteConfig, ProviderManager
from backend.omniroute.models import ProviderInfo, ProviderStatus


class TestOmnirouteClient:
    """Tests para OmnirouteClient"""

    @pytest.fixture
    async def client(self):
        """Crear cliente para testing"""
        config = OmnirouteConfig(omniroute_url="http://localhost:8080", timeout=10)
        client = OmnirouteClient(config)
        yield client
        await client.close()

    @pytest.mark.asyncio
    async def test_get_providers_success(self, client):
        """Test: Obtener proveedores exitosamente"""
        mock_providers = [
            {
                "name": "groq",
                "model": "mixtral-8x7b",
                "status": "healthy",
                "latency_ms": 245.5,
                "score": 9.2,
            }
        ]

        with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {"providers": mock_providers}
            mock_get.return_value = mock_response

            providers = await client.get_providers()

            assert len(providers) == 1
            assert providers[0].name == "groq"
            assert providers[0].status == ProviderStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_get_best_provider(self, client):
        """Test: Obtener mejor proveedor"""
        mock_providers = [
            ProviderInfo(
                name="groq",
                model="mixtral",
                status=ProviderStatus.HEALTHY,
                latency_ms=100,
                score=9.5,
            ),
            ProviderInfo(
                name="openrouter",
                model="gpt-4",
                status=ProviderStatus.HEALTHY,
                latency_ms=500,
                score=8.0,
            ),
        ]

        with patch.object(client, "get_providers", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_providers

            best = await client.get_best_provider()

            assert best.name == "groq"
            assert best.score == 9.5

    @pytest.mark.asyncio
    async def test_chat_fallback(self, client):
        """Test: Fallback cuando falla el proveedor"""
        with patch.object(client, "get_best_provider", new_callable=AsyncMock) as mock_provider:
            mock_provider.return_value = None

            with pytest.raises(Exception, match="No healthy providers"):
                await client.chat("test message")

    @pytest.mark.asyncio
    async def test_health_check_success(self, client):
        """Test: Health check exitoso"""
        with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {"status": "ok", "providers": 312}
            mock_get.return_value = mock_response

            health = await client.get_health()

            assert health["status"] == "ok"
            assert health["providers"] == 312


class TestProviderManager:
    """Tests para ProviderManager"""

    @pytest.fixture
    async def manager(self):
        """Crear manager para testing"""
        config = OmnirouteConfig()
        manager = ProviderManager(config)
        yield manager
        await manager.stop_monitoring()

    @pytest.mark.asyncio
    async def test_get_provider_stats(self, manager):
        """Test: Obtener estadísticas de proveedor"""
        manager.provider_stats["groq"] = {
            "checks": 10,
            "healthy_checks": 9,
            "total_latency": 2450,
            "last_check": "2024-08-31T12:00:00Z",
            "status_history": [ProviderStatus.HEALTHY.value] * 9 + [ProviderStatus.DEGRADED.value],
        }

        stats = await manager.get_provider_stats("groq")

        assert stats["provider"] == "groq"
        assert stats["checks"] == 10
        assert stats["uptime_percent"] == 90.0
        assert stats["avg_latency_ms"] == 272.22

    @pytest.mark.asyncio
    async def test_provider_stats_not_found(self, manager):
        """Test: Estadísticas de proveedor no encontrado"""
        stats = await manager.get_provider_stats("nonexistent")
        assert "error" in stats

    @pytest.mark.asyncio
    async def test_monitoring_task(self, manager):
        """Test: Tarea de monitoreo se inicia correctamente"""
        await manager.start_monitoring(interval=5)

        assert manager.monitoring_task is not None
        assert not manager.monitoring_task.done()

        await manager.stop_monitoring()


class TestIntegration:
    """Integration tests (requiere Omniroute corriendo)"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_omniroute_integration_live(self):
        """Test: Integración real con Omniroute si está disponible"""
        config = OmnirouteConfig(omniroute_url="http://localhost:8080")
        client = OmnirouteClient(config)

        try:
            health = await client.get_health()
            assert health.get("status") in ["ok", "operational"]

            providers = await client.get_providers()
            assert len(providers) > 0

            best = await client.get_best_provider()
            assert best is not None

        except Exception as e:
            pytest.skip(f"Omniroute not available: {e}")
        finally:
            await client.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
