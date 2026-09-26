"""
OMNIROUTE USAGE EXAMPLES

Demostraciones prácticas de integración Omniroute en AURA OS
"""

import asyncio
import httpx
from datetime import datetime


class OmnirouteExamples:
    """Ejemplos de uso de Omniroute"""

    BASE_URL = "http://localhost:8000"

    @staticmethod
    async def example_1_simple_chat():
        """Ejemplo 1: Chat simple con selección automática de proveedor"""
        print("\n" + "=" * 60)
        print("EJEMPLO 1: Chat Simple (Auto Provider Selection)")
        print("=" * 60)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{OmnirouteExamples.BASE_URL}/api/chat/omniroute",
                json={"message": "¿Cuál es la capital de Francia?"},
            )

            data = response.json()
            print(f"\nMensaje: ¿Cuál es la capital de Francia?")
            print(f"Respuesta: {data['response']}")
            print(f"Fuente: {data['source']}")

    @staticmethod
    async def example_2_list_providers():
        """Ejemplo 2: Listar todos los proveedores disponibles"""
        print("\n" + "=" * 60)
        print("EJEMPLO 2: Listar Proveedores")
        print("=" * 60)

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{OmnirouteExamples.BASE_URL}/api/providers"
            )

            data = response.json()
            print(f"\nTotal de proveedores: {data['total']}")
            print("\nPrimeros 5 proveedores:")

            for i, provider in enumerate(data["providers"][:5], 1):
                print(f"\n  {i}. {provider['name']}")
                print(f"     Modelo: {provider['model']}")
                print(f"     Estado: {provider['status']}")
                print(f"     Latencia: {provider['latency_ms']}ms")
                print(f"     Score: {provider['score']}")

    @staticmethod
    async def example_3_best_provider():
        """Ejemplo 3: Obtener mejor proveedor actual"""
        print("\n" + "=" * 60)
        print("EJEMPLO 3: Mejor Proveedor Actual")
        print("=" * 60)

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{OmnirouteExamples.BASE_URL}/api/providers/best"
            )

            data = response.json()
            print(f"\nMejor proveedor según scoring de 12 factores:")
            print(f"  Nombre: {data['name']}")
            print(f"  Modelo: {data['model']}")
            print(f"  Estado: {data['status']}")
            print(f"  Latencia: {data['latency_ms']}ms")
            print(f"  Score: {data['score']}")

    @staticmethod
    async def example_4_provider_stats():
        """Ejemplo 4: Ver estadísticas de un proveedor"""
        print("\n" + "=" * 60)
        print("EJEMPLO 4: Estadísticas de Proveedor")
        print("=" * 60)

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{OmnirouteExamples.BASE_URL}/api/providers/stats"
            )

            data = response.json()
            print(f"\nEstadísticas globales de proveedores:")

            for name, stats in list(data.items())[:3]:
                print(f"\n  {name}:")
                print(f"    Checks: {stats['checks']}")
                print(f"    Uptime: {stats['uptime_percent']}%")
                print(f"    Latencia promedio: {stats['avg_latency_ms']}ms")

    @staticmethod
    async def example_5_recommendations():
        """Ejemplo 5: Obtener recomendaciones"""
        print("\n" + "=" * 60)
        print("EJEMPLO 5: Recomendaciones")
        print("=" * 60)

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{OmnirouteExamples.BASE_URL}/api/providers/recommendations"
            )

            data = response.json()
            print(f"\nRecomendaciones basadas en estado actual:")
            print(f"  Total de proveedores: {data['total_providers']}")
            print(f"  Saludables: {data['healthy']}")
            print(f"  Degradados: {data['degraded']}")
            print(f"  No disponibles: {data['unavailable']}")

            if data["recommended_provider"]:
                rec = data["recommended_provider"]
                print(f"\n  Proveedor recomendado:")
                print(f"    Nombre: {rec['name']}")
                print(f"    Modelo: {rec['model']}")
                print(f"    Score: {rec['score']}")

    @staticmethod
    async def example_6_health_check():
        """Ejemplo 6: Verificar health de Omniroute"""
        print("\n" + "=" * 60)
        print("EJEMPLO 6: Health Check")
        print("=" * 60)

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{OmnirouteExamples.BASE_URL}/api/omniroute/health"
            )

            data = response.json()
            print(f"\nOmniroute Health Status:")
            print(f"  Status: {data.get('status', 'unknown')}")

            for key, value in data.items():
                if key != "status":
                    print(f"  {key}: {value}")


async def main():
    """Ejecutar todos los ejemplos"""
    print("\n" + "=" * 60)
    print("OMNIROUTE INTEGRATION EXAMPLES")
    print("AURA OS v2.1 with Multi-Provider AI")
    print("=" * 60)

    try:
        async with httpx.AsyncClient() as client:
            health = await client.get(f"{OmnirouteExamples.BASE_URL}/health")
            health.raise_for_status()
    except Exception:
        print("\n❌ Error: AURA is not running at http://localhost:8000")
        print("   Start AURA: python backend/main.py")
        return

    try:
        await OmnirouteExamples.example_1_simple_chat()
        await OmnirouteExamples.example_2_list_providers()
        await OmnirouteExamples.example_3_best_provider()
        await OmnirouteExamples.example_4_provider_stats()
        await OmnirouteExamples.example_5_recommendations()
        await OmnirouteExamples.example_6_health_check()

        print("\n" + "=" * 60)
        print("✅ All examples completed successfully!")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
