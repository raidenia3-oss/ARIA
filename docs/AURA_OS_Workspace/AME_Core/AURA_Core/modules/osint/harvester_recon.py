import subprocess
import json
import logging

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_command(command):
    """
    Ejecuta un comando del sistema y captura su salida.
    """
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=300)  # 5 minutos de timeout
        return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}
    except subprocess.CalledProcessError as e:
        logger.error(f"Comando fallido: {e.cmd}, Error: {e.stderr}")
        return {"stdout": e.stdout, "stderr": e.stderr, "returncode": e.returncode}
    except subprocess.TimeoutExpired as e:
        logger.error(f"Comando excedió el tiempo de espera: {e.cmd}, Timeout: {e.timeout}")
        return {"stdout": e.stdout.decode(), "stderr": e.stderr.decode() + "\nError: Tiempo de espera excedido.", "returncode": -1}
    except FileNotFoundError:
        logger.error(f"Comando no encontrado. Asegúrate de que las herramientas estén instaladas y en el PATH.")
        return {"stdout": "", "stderr": "Error: Herramienta no encontrada. Instala theHarvester/recon-ng.", "returncode": 127}
    except Exception as e:
        logger.error(f"Error inesperado al ejecutar comando: {e}")
        return {"stdout": "", "stderr": f"Error inesperado: {e}", "returncode": 1}

def run_theharvester(domain, limit=50):
    """
    Ejecuta theHarvester para el dominio especificado.
    Requiere que theHarvester esté instalado y accesible en el PATH.
    """
    logger.info(f"Ejecutando theHarvester para el dominio: {domain} con límite: {limit}")
    command = ["theHarvester", "-d", domain, "-l", str(limit), "-b", "all"]
    return run_command(command)

def run_recon_ng(workspace, commands):
    """
    Ejecuta recon-ng con una serie de comandos en un workspace específico.
    Requiere que recon-ng esté instalado y accesible en el PATH.
    `commands` debe ser una lista de strings con los comandos a ejecutar dentro de recon-ng.
    """
    logger.info(f"Ejecutando recon-ng en workspace: {workspace}")
    recon_ng_commands = [f"workspaces select {workspace}"] + commands + ["exit"]
    # Construir el comando para ejecutar recon-ng con comandos de entrada
    # Nota: recon-ng típicamente interactúa de forma interactiva. Esto es un intento de automatizarlo.
    # Podría requerir el uso de un archivo de recursos (.rc) o un enfoque más sofisticado para comandos complejos.
    command = ["recon-ng", "-r", "\n".join(recon_ng_commands)]
    return run_command(command)

# Ejemplo de uso (para pruebas)
if __name__ == "__main__":
    print("--- Probando theHarvester ---")
    harvester_result = run_theharvester("example.com")
    print(json.dumps(harvester_result, indent=2))

    print("\n--- Probando recon-ng (simulado) ---")
    # Para un uso real de recon-ng, se necesitan comandos específicos y puede ser interactivo.
    # Este es un ejemplo básico que probablemente fallará si recon-ng espera interacción real.
    recon_ng_result = run_recon_ng("test_workspace", ["add domains example.com", "show domains"])
    print(json.dumps(recon_ng_result, indent=2))
