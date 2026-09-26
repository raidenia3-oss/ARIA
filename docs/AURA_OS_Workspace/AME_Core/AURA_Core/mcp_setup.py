#!/usr/bin/env python3
"""
Script para configurar MCP (Model Context Protocol) en AURA.
Permite acceso a archivos, terminal y base de datos con contexto real.
"""

import os
import subprocess
import json
from pathlib import Path

class MCPSetup:
    def __init__(self):
        self.mcp_config_dir = Path("~/.mcp").expanduser()
        self.mcp_config_dir.mkdir(exist_ok=True)

    def install_mcp(self):
        """
        Instala MCP si no está disponible.
        """
        try:
            print("🔧 Configurando MCP (Model Context Protocol)...")

            # Verificar si MCP ya está instalado
            if not self.mcp_config_dir.exists():
                print("⚠️ MCP no encontrado. Creando configuración...")

                # Crear archivo de configuración de MCP
                mcp_config = {
                    "version": "1.0",
                    "servers": {
                        "vscode": {
                            "enabled": True,
                            "port": 5005,
                            "description": "Contexto de VS Code para AURA"
                        },
                        "terminal": {
                            "enabled": True,
                            "port": 5006,
                            "description": "Terminal integrado para ejecución de comandos"
                        },
                        "database": {
                            "enabled": True,
                            "port": 5007,
                            "description": "Conexión a la base de datos de AURA"
                        }
                    },
                    "auth": {
                        "enabled": True,
                        "token": "SECRET_MCP_TOKEN_12345"  # Cambia esto por un token seguro
                    }
                }

                # Guardar configuración
                config_path = self.mcp_config_dir / "config.json"
                with open(config_path, "w") as f:
                    json.dump(mcp_config, f, indent=2)

                print("✅ Configuración de MCP guardada en ~/.mcp/config.json")

                # Crear scripts de inicio para los servidores MCP
                self._create_mcp_servers()

                return True
            else:
                print("✅ MCP ya está configurado.")
                return True
        except Exception as e:
            print(f"❌ Error al configurar MCP: {e}")
            return False

    def _create_mcp_servers(self):
        """
        Crea scripts para iniciar los servidores MCP.
        """
        try:
            # Crear script para el servidor de VS Code
            vscode_server_script = self.mcp_config_dir / "start_vscode_server.py"
            with open(vscode_server_script, "w") as f:
                f.write("#!/usr/bin/env python3\n")
                f.write("# Servidor MCP para VS Code.\n")
                f.write("# Proporciona contexto de archivos y proyectos en VS Code.\n")
                f.write("\n")
                f.write("""
from flask import Flask, request, jsonify
import os
import json

app = Flask(__name__)

@app.route('/api/vscode/files', methods=['GET'])
def list_vscode_files():
    \"\"\"Lista archivos en el workspace de VS Code.\"\"\"
    try:
        # Obtener la ruta del workspace de VS Code
        workspace_path = os.getenv('VSCODE_WORKSPACE_PATH', os.getcwd())

        # Listar archivos en el directorio
        files = []
        for root, dirs, filenames in os.walk(workspace_path):
            for filename in filenames:
                files.append(os.path.join(root, filename))

        return jsonify({"status": "ok", "files": files})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/vscode/file_content', methods=['GET'])
def get_file_content():
    \"\"\"Obtiene el contenido de un archivo.\"\"\"
    file_path = request.args.get('path')
    if not file_path:
        return jsonify({"status": "error", "message": "Ruta del archivo requerida"}), 400

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return jsonify({"status": "ok", "content": content})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5005, debug=False)
""")

            # Crear script para el servidor de Terminal
            terminal_server_script = self.mcp_config_dir / "start_terminal_server.py"
            with open(terminal_server_script, "w") as f:
                f.write("#!/usr/bin/env python3\n")
                f.write("# Servidor MCP para Terminal.\n")
                f.write("# Permite ejecutar comandos en el sistema.\n")
                f.write("\n")
                f.write("""
from flask import Flask, request, jsonify
import subprocess
import json

app = Flask(__name__)

@app.route('/api/terminal/execute', methods=['POST'])
def execute_command():
    \"\"\"Ejecuta un comando en el terminal.\"\"\"
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
""")

            # Crear script para el servidor de Base de Datos
            database_server_script = self.mcp_config_dir / "start_database_server.py"
            with open(database_server_script, "w") as f:
                f.write("#!/usr/bin/env python3\n")
                f.write("# Servidor MCP para Base de Datos.\n")
                f.write("# Proporciona acceso a la base de datos de AURA.\n")
                f.write("\n")
                f.write("""
from flask import Flask, request, jsonify
from AURA_Core.memory_manager import MemoryManager
import json

app = Flask(__name__)
memory_manager = MemoryManager()

@app.route('/api/database/query', methods=['POST'])
def query_database():
    \"\"\"Consulta la base de datos vectorial.\"\"\"
    data = request.get_json()
    if not data or 'query' not in data:
        return jsonify({"status": "error", "message": "Consulta requerida"}), 400

    query = data['query']
    try:
        results = memory_manager.query_memory(query)
        return jsonify({
            "status": "ok",
            "results": [
                {"document": doc, "metadata": meta, "score": 1 - score}
                for doc, meta, score in zip(results['documents'], results['metadatas'], results['distances'])
            ]
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/database/add', methods=['POST'])
def add_to_database():
    \"\"\"Añade información a la base de datos vectorial.\"\"\"
    data = request.get_json()
    if not data or 'content' not in data:
        return jsonify({"status": "error", "message": "Contenido requerido"}), 400

    content = data['content']
    metadata = data.get('metadata', {})

    try:
        memory_manager.add_memory(content, metadata)
        return jsonify({"status": "ok", "message": "Información añadida a la base de datos"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5007, debug=False)
""")

            print("✅ Scripts de servidores MCP creados en ~/.mcp/")

        except Exception as e:
            print(f"❌ Error al crear scripts MCP: {e}")

    def start_mcp_servers(self):
        """
        Inicia los servidores MCP.
        """
        try:
            print("🚀 Iniciando servidores MCP...")

            # Iniciar servidores en segundo plano
            subprocess.Popen(["python", str(self.mcp_config_dir / "start_vscode_server.py")], shell=False)
            subprocess.Popen(["python", str(self.mcp_config_dir / "start_terminal_server.py")], shell=False)
            subprocess.Popen(["python", str(self.mcp_config_dir / "start_database_server.py")], shell=False)

            print("✅ Servidores MCP iniciados.")
            return True
        except Exception as e:
            print(f"❌ Error al iniciar servidores MCP: {e}")
            return False

def main():
    """Función principal para configurar MCP."""
    print("=" * 50)
    print("🔧 Configurando MCP (Model Context Protocol)")
    print("=" * 50)

    mcp_setup = MCPSetup()

    # Instalar MCP
    if not mcp_setup.install_mcp():
        print("⚠️  No se pudo instalar MCP.")

    # Iniciar servidores MCP
    if not mcp_setup.start_mcp_servers():
        print("⚠️  No se pudieron iniciar los servidores MCP.")

    print("\n🔧 Configuración de MCP completada.")
    print("📌 Instrucciones:")
    print("   1. Los servidores MCP están disponibles en:")
    print("      - VS Code: http://localhost:5005")
    print("      - Terminal: http://localhost:5006")
    print("      - Base de Datos: http://localhost:5007")
    print("   2. Usa el token de autenticación para acceder a los endpoints.")
    print("=" * 50)

if __name__ == "__main__":
    main()