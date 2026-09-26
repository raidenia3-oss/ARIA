from __future__ import annotations

from backend.omniroute.client import OmnirouteClient
from backend.omniroute.models import OmnirouteConfig, ProviderInfo, ProviderStatus
from typing import Optional, List, Dict
import asyncio
from datetime import datetime


class ProviderManager:
    """Gestor de proveedores con monitoreo"""

    def __init__(self, config: OmnirouteConfig):
        self.config = config
        self.client = OmnirouteClient(config)
        self.provider_stats: Dict[str, Dict] = {}
        self.monitoring_task: Optional[asyncio.Task] = None

    async def start_monitoring(self, interval: int = 300):
        """Iniciar monitoreo de proveedores (cada 5 min por defecto)"""
        self.monitoring_task = asyncio.create_task(
            self._monitor_providers(interval)
        )
        print(f"[ProviderManager] Monitoring started (interval: {interval}s)")

    async def stop_monitoring(self):
        """Parar monitoreo"""
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
            print("[ProviderManager] Monitoring stopped")

    async def _monitor_providers(self, interval: int):
        """Monitoreo continuo de providers"""
        while True:
            try:
                providers = await self.client.get_providers(force_refresh=True)

                for provider in providers:
                    if provider.name not in self.provider_stats:
                        self.provider_stats[provider.name] = {
                            "checks": 0,
                            "healthy_checks": 0,
                            "total_latency": 0.0,
                            "last_check": None,
                            "status_history": [],
                        }

                    stats = self.provider_stats[provider.name]
                    stats["checks"] += 1

                    if provider.status == ProviderStatus.HEALTHY:
                        stats["healthy_checks"] += 1

                    if provider.latency_ms:
                        stats["total_latency"] += provider.latency_ms

                    stats["last_check"] = datetime.utcnow().isoformat()
                    stats["status_history"].append(provider.status.value)

                    if len(stats["status_history"]) > 100:
                        stats["status_history"] = stats["status_history"][-100:]

                print(f"[ProviderManager] Health check completed ({len(providers)} providers)")

            except Exception as e:
                print(f"[ProviderManager] Monitoring error: {e}")

            await asyncio.sleep(interval)

    async def get_provider_stats(self, provider_name: str) -> Dict:
        """Obtener estadisticas de un proveedor"""
        if provider_name not in self.provider_stats:
            return {"error": "Provider not found"}

        stats = self.provider_stats[provider_name]
        uptime_percent = (stats["healthy_checks"] / stats["checks"] * 100) if stats["checks"] > 0 else 0
        avg_latency = (stats["total_latency"] / stats["healthy_checks"]) if stats["healthy_checks"] > 0 else None

        return {
            "provider": provider_name,
            "checks": stats["checks"],
            "uptime_percent": round(uptime_percent, 2),
            "avg_latency_ms": round(avg_latency, 2) if avg_latency else None,
            "last_check": stats["last_check"],
            "status_history": stats["status_history"][-20:],
        }

    async def get_all_stats(self) -> Dict[str, Dict]:
        """Obtener estadisticas de todos los proveedores"""
        return {
            name: await self.get_provider_stats(name)
            for name in self.provider_stats.keys()
        }

    async def get_recommendations(self) -> Dict:
        """Recomendaciones basadas en estadisticas"""
        providers = await self.client.get_providers()
        all_stats = await self.get_all_stats()

        healthy = [p for p in providers if p.status == ProviderStatus.HEALTHY]
        degraded = [p for p in providers if p.status == ProviderStatus.DEGRADED]
        unavailable = [p for p in providers if p.status == ProviderStatus.UNAVAILABLE]

        best = await self.client.get_best_provider()

        return {
            "total_providers": len(providers),
            "healthy": len(healthy),
            "degraded": len(degraded),
            "unavailable": len(unavailable),
            "recommended_provider": {
                "name": best.name,
                "model": best.model,
                "score": best.score,
                "latency_ms": best.latency_ms,
            } if best else None,
            "timestamp": datetime.utcnow().isoformat(),
        }
