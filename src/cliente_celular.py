#!/usr/bin/env python3
import requests
import sys

SERVER_URL = "http://100.64.0.1:5000"

def query_server(comando):
    try:
        r = requests.post(
            f"{SERVER_URL}/ejecutar",
            json={"comando": comando},
            timeout=1,
        )
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException:
        return None

def modo_local(comando):
    try:
        result = __import__("subprocess").run(
            comando, shell=True, capture_output=True, text=True, timeout=30
        )
        return {
            "output": result.stdout,
            "error": result.stderr,
            "returncode": result.returncode,
        }
    except Exception as e:
        return {"error": str(e)}

def main():
    if len(sys.argv) < 2:
        print("Uso: python cliente_celular.py <comando>")
        sys.exit(1)
    comando = sys.argv[1]
    print(f"[INFO] Enviando comando al servidor: {comando}")
    respuesta = query_server(comando)
    if respuesta is None:
        print("[WARN] Servidor no responde. PC apagada. Cambiando a modo local.")
        respuesta = modo_local(comando)
    print(respuesta.get("output", ""))
    if respuesta.get("error"):
        print(f"[ERROR] {respuesta['error']}", file=sys.stderr)

if __name__ == "__main__":
    main()