#!/usr/bin/env python3
"""
Servidor MCP para Terminal.
Permite ejecutar comandos en el sistema.
"""

from flask import Flask, request, jsonify
import subprocess

app = Flask(__name__)

@app.route('/api/terminal/execute', methods=['POST'])
def execute_command():
    """Ejecuta un comando en el terminal."""
    data = request.get_json()
    if not data or 'command' not in data:
        return jsonify({"status": "error", "message": "Comando requerido"}), 400
    command = data['command']
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return jsonify({
            "status": "ok",
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        })
    except subprocess.CalledProcessError as e:
        return jsonify({
            "status": "error",
            "stdout": e.stdout,
            "stderr": e.stderr,
            "returncode": e.returncode
        }), e.returncode
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5006, debug=False)