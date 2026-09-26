"""
Script para depurar la importación del router de FastAPI.
"""

from backend.core.ws_routes import router


def debug_import():
    """Depura la importación del router."""
    print("Router importado correctamente.")
    print(f"Rutas en el router: {router.routes}")
    
    for route in router.routes:
        print(f"- Método: {route.methods}, Ruta: {route.path}")


if __name__ == "__main__":
    debug_import()