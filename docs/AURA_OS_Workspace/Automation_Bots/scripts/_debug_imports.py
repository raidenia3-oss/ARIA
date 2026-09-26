import sys
import os

# Añadir Shadow-Core al path
SHADOW_CORE_DIR = os.path.join(os.path.dirname(__file__), "Shadow-Core")
sys.path.insert(0, SHADOW_CORE_DIR)

# Intentar importar los módulos
try:
    from net_recon_ghost import run_recon
    print("✅ net_recon_ghost importado correctamente")
    print(f"   run_recon: {run_recon}")
except ImportError as e:
    print(f"❌ Error importando net_recon_ghost: {e}")

try:
    from data_exfiltration_layer import exfiltrate_file, prepare_exfil_report
    print("✅ data_exfiltration_layer importado correctamente")
    print(f"   exfiltrate_file: {exfiltrate_file}")
    print(f"   prepare_exfil_report: {prepare_exfil_report}")
except ImportError as e:
    print(f"❌ Error importando data_exfiltration_layer: {e}")

# Verificar si los archivos existen
print("\n📁 Verificando archivos en Shadow-Core/")
for fname in os.listdir(SHADOW_CORE_DIR):
    print(f"   {fname}")

# Verificar contenido de los archivos
print("\n📄 Verificando contenido de net_recon_ghost.py")
try:
    with open(os.path.join(SHADOW_CORE_DIR, "net_recon_ghost.py"), "r") as f:
        lines = f.readlines()
        print(f"   Primeras 5 líneas: {lines[:5]}")
except Exception as e:
    print(f"❌ Error leyendo net_recon_ghost.py: {e}")

print("\n📄 Verificando contenido de data_exfiltration_layer.py")
try:
    with open(os.path.join(SHADOW_CORE_DIR, "data_exfiltration_layer.py"), "r") as f:
        lines = f.readlines()
        print(f"   Primeras 5 líneas: {lines[:5]}")
except Exception as e:
    print(f"❌ Error leyendo data_exfiltration_layer.py: {e}")