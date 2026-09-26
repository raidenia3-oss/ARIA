"""
Script para depurar el router de FastAPI.
"""

from backend.core.ws_routes import router


def debug_router():
    """Depura el router de FastAPI."""
    print("Rutas definidas en el router:")
    for route in router.routes:
        print(f"- Método: {route.methods}, Ruta: {route.path}")


if __name__ == "__main__":
    debug_router()