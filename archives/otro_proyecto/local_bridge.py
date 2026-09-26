import os
import time
import random
import requests
from pyngrok import ngrok, conf

LOCAL_HOST = "http://localhost:1234/v1"
MODEL_NAME = "Qwen 3.5 9B"


def try_ngrok(port: int, proto: str = "http") -> str:
    for i in range(2):
        try:
            tunnel = ngrok.connect(port, proto)
            return tunnel.public_url
        except Exception as exc:
            if i == 0:
                wait = random.uniform(1, 3)
                print(f" ngrok intento {i+1} fallo: {exc}. Reintentando en {wait:.1f}s...")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("No se pudo iniciar ngrok tras 2 intentos.")


def _check_lm_studio(base_url: str) -> tuple[bool, str]:
    candidates = ["/models", "", "/health"]
    for suffix in candidates:
        url = base_url.rstrip("/") + suffix
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            return True, url
        except requests.RequestException:
            continue
    return False, f"No se pudo conectar a LM Studio en {base_url}."


def main() -> int:
    print("Iniciando puente local para LM Studio...")
    success, info = _check_lm_studio(LOCAL_HOST)
    if not success:
        print("Error: LM Studio no está disponible.")
        print(info)
        print("Asegúrate de que LM Studio esté iniciado en http://localhost:1234 y que la ruta /v1 esté disponible.")
        return 1

    print(f"LM Studio parece estar funcionando en: {info}")
    print("Usando modelo objetivo:", MODEL_NAME)

    auth_token = os.getenv("NGROK_AUTHTOKEN")
    if auth_token:
        print("Usando NGROK_AUTHTOKEN de entorno.")
        conf.get_default().auth_token = auth_token

    try:
        print("Abriendo túnel ngrok sobre el puerto 1234...")
        public_url = try_ngrok(1234, "http")
    except Exception as exc:
        print("Error al iniciar ngrok:", exc)
        print("Instala pyngrok y asegúrate de que ngrok esté disponible.")
        return 1

    print("Túnel público creado:")
    print(public_url)
    print("Copia esta URL en tu configuración de Vercel.")
    print("Mantén este script ejecutándose mientras uses la URL pública.")

    try:
        input("Presiona ENTER para cerrar el túnel y salir...\n")
    finally:
        try:
            ngrok.disconnect(public_url)
        except Exception:
            pass
        try:
            ngrok.kill()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
