"""
colab/conectar_ame.py
Script que guarda las URLs de los servidores IA en ame_nube.json
automaticamente cuando los servidores de Colab estan listos.

Uso:
    python colab/conectar_ame.py

Las URLs se leen de server_url.txt y server_url_general.txt
(generados automaticamente por servidor_ia.ipynb en Colab).

Modelos: Rocinante 12B + Mistral Nemo Abliterated (sin censura)
"""

import json
import os
import sys

# Nombre del archivo de configuracion de salida
AME_CONFIG = "ame_nube.json"


def leer_url(path):
    """Lee una URL desde un archivo de texto."""
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        url = f.read().strip()
    if not url or url == "PENDIENTE":
        return None
    return url


def actualizar_config_ame(url_codigo, url_general):
    """
    Genera el archivo de configuracion AME con las URLs de los servidores.
    Tambien intenta notificar a AURA si esta corriendo localmente.
    """
    config = {
        "servidor_codigo": url_codigo,
        "servidor_general": url_general,
        "model_codigo": "rocinante-12b-uncensored",
        "model_general": "mistral-nemo-abliterated",
        "sin_censura": True,
        "activo": True,
    }

    # Guardar configuracion localmente
    with open(AME_CONFIG, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"Config guardada en {AME_CONFIG}")
    print(f"   Codigo:  {url_codigo}")
    print(f"   General: {url_general}")
    print(f"   Modelos: Rocinante 12B + Mistral Nemo (sin censura)")

    # Intentar notificar a AURA Core si esta corriendo en el puerto local
    try:
        import requests

        requests.post(
            "http://localhost:8765",
            json={"node": "NUBE_IA", "event": "SERVIDORES_LISTOS", "payload": config},
            timeout=3,
        )
        print("AURA Core notificado del evento SERVIDORES_LISTOS")
    except ImportError:
        print("requests no instalado, omitiendo notificacion a AURA")
    except Exception:
        print("AURA Core no esta corriendo localmente, config guardada sin notificar")


def mostrar_instrucciones():
    """Muestra instrucciones de uso al usuario."""
    print("=" * 60)
    print("  AURA Cloud IA — Conectar servidores de Colab con AME")
    print("=" * 60)
    print()
    print("Este script lee las URLs generadas por servidor_ia.ipynb")
    print("y crea ame_nube.json para que AME Chat se conecte.")
    print("Modelos: Rocinante 12B + Mistral Nemo Abliterated (sin censura)")
    print()
    print("Archivos esperados:")
    print("  - server_url.txt           (URL del servidor de codigo)")
    print("  - server_url_general.txt   (URL del servidor general)")
    print()
    print("Coloca estos archivos en el mismo directorio que este script.")
    print("O ejecuta este script dentro de Google Colab despues de las celdas.")
    print("=" * 60)


def main():
    """Funcion principal del script."""
    mostrar_instrucciones()
    print()

    # Buscar archivos de URL en varias ubicaciones
    posibles_rutas = [
        ("server_url.txt", "server_url_general.txt"),
        ("/content/server_url.txt", "/content/server_url_general.txt"),
    ]

    url_codigo = None
    url_general = None

    for ruta_codigo, ruta_general in posibles_rutas:
        url_codigo = leer_url(ruta_codigo)
        url_general = leer_url(ruta_general)
        if url_codigo and url_general:
            print(f"Archivos encontrados en: {os.path.dirname(ruta_codigo) or '.'}")
            break

    if not url_codigo:
        print("No se encontro server_url.txt")
        print("Asegurate de haber ejecutado las celdas del notebook en Colab.")
        print("O crea manualmente server_url.txt con la URL del servidor.")
        sys.exit(1)

    if not url_general:
        print("server_url_general.txt no encontrado o pendiente.")
        print("Usando la misma URL para ambos servidores.")
        url_general = url_codigo

    print()
    actualizar_config_ame(url_codigo, url_general)
    print()
    print("Siguiente paso: Abre AME Chat y selecciona 'Nube IA' como proveedor.")


if __name__ == "__main__":
    main()
