#!/usr/bin/env python3
import subprocess
from flask import Flask, request, jsonify
import socket

app = Flask(__name__)

def get_tailscale_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "0.0.0.0"

@app.route("/ejecutar", methods=["POST"])
def ejecutar():
    comando = request.json.get("comando", "") if request.is_json else request.form.get("comando", "")
    if not comando:
        return jsonify({"error": "No command provided"}), 400
    try:
        result = subprocess.run(
            comando, shell=True, capture_output=True, text=True, timeout=30
        )
        return jsonify({
            "output": result.stdout,
            "error": result.stderr,
            "returncode": result.returncode,
        })
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Command timed out"}), 408
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/", methods=["GET"])
def status():
    return jsonify({"status": "ok", "server": "servidor.py"})

if __name__ == "__main__":
    tailscale_ip = get_tailscale_ip()
    print(f"Servidor escuchando en {tailscale_ip}:5000")
    app.run(host="0.0.0.0", port=5000)