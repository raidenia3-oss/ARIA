"""
Instalador de Mimo Code (agente de codigo gratuito de Xiaomi).
"""

import subprocess, sys

print("Instalando Mimo Code (agente de codigo gratuito)...")
print("Repo oficial: github.com/XiaomiMiMo/MiMo-Code")
print()

result = subprocess.run(["node", "--version"], capture_output=True, text=True)
if result.returncode == 0:
    print(f"Node.js disponible: {result.stdout.strip()}")
    subprocess.run(["npm", "install", "-g", "@xiaomi/mimo-code"])
    print("Mimo Code instalado")
    print("Configurar con HF Space:")
    print("  OPENAI_BASE_URL=https://raiden456-slut.hf.space/v1")
    print("  OPENAI_API_KEY=no-key")
else:
    print("Node.js no encontrado - descarga desde nodejs.org")
