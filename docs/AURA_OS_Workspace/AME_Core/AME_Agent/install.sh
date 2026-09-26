#!/data/data/com.termux/files/usr/bin/bash
# Instalador de AME Agent para Termux
# Ejecutar en Termux: bash install.sh

echo "Instalando AME Agent..."

# Actualizar paquetes
pkg update -y && pkg upgrade -y

# Instalar dependencias del sistema
pkg install -y python git openssh curl wget

# Instalar dependencias Python
pip install websockets requests --break-system-packages -q

# Crear workspace
mkdir -p /sdcard/AURA_workspace

# Crear comando global 'ame'
cat > /data/data/com.termux/files/usr/bin/ame << 'ENDSCRIPT'
#!/data/data/com.termux/files/usr/bin/python
import sys
sys.path.insert(0, '/sdcard/AURA_workspace/AME_Agent')
from agent import AMEAgent
import asyncio

agent = AMEAgent()
task = ' '.join(sys.argv[1:]) if len(sys.argv) > 1 else None
asyncio.run(agent.run(task))
ENDSCRIPT

chmod +x /data/data/com.termux/files/usr/bin/ame

echo ""
echo "AME Agent instalado correctamente"
echo ""
echo "USO:"
echo "  ame                    -> modo interactivo"
echo "  ame 'instala numpy'    -> tarea directa"
echo "  ame 'actualiza AURA'   -> sincroniza con PC"
echo "  ame 'abre godot'       -> controla Godot"
echo ""
echo "Configura tu API key en /sdcard/ame_config.json:"
echo '  {"api_key": "TU_GEMINI_KEY", "aura_url": "ws://IP_PC:8765"}'