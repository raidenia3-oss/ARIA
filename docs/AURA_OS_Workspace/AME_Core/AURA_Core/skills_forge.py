"""
AURA Skills Forge — skills_forge.py v4
Gestiona herramientas del sistema como una cadena de habilidades
ejecutables en secuencia o en segundo plano.
Incluye soporte para:
  - ExifTool, Blackbird/Nexfil, Photon Crawler, PhoneInfoga, Mr. Holmes
  - Subdomain Enum (módulo Python de Venice)
  - CryptoFarmer v2 (RollerCoin, Playwright)
  - Escudo Sentinel (Firebase, detección de puertos)
"""
import os
import sys
import json
import subprocess
import threading
import time
import shutil
import importlib.util
from datetime import datetime
from pathlib import Path

# ── Resolver rutas AURA_Core y AME_Core ──
AURA_CORE_PATH = Path(__file__).parent
AME_CORE_PATH = AURA_CORE_PATH.parent / "AME_Core"
if str(AME_CORE_PATH) not in sys.path:
    sys.path.insert(0, str(AME_CORE_PATH))
if str(AURA_CORE_PATH / "recon") not in sys.path:
    sys.path.insert(0, str(AURA_CORE_PATH / "recon"))

# ── Importar módulos de reconocimiento ──
try:
    from subdomain_permutator import run_subdomain_enum as _run_subdomain_enum
    SUBDOMAIN_ENUM_AVAILABLE = True
except ImportError:
    _run_subdomain_enum = None
    SUBDOMAIN_ENUM_AVAILABLE = False
except Exception:
    _run_subdomain_enum = None
    SUBDOMAIN_ENUM_AVAILABLE = False

BASE_DIR = str(AURA_CORE_PATH)
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
HEALTH_LOG = os.path.join(BASE_DIR, "system_health.log")

# ── Mapa de herramientas ──
TOOL_REGISTRY = {
    "exiftool": {
        "name": "ExifTool",
        "icon": "📸",
        "description": "Lee y escribe metadatos EXIF/IPTC/XMP en imágenes",
        "check_cmd": "exiftool -ver",
        "run_cmd": 'exiftool "{target}"',
        "min_args": 1,
        "arg_help": "Ruta a imagen (local o descargada)",
        "light_package": "exiftool",
        "type": "forensic"
    },
    "blackbird": {
        "name": "Blackbird / Nexfil",
        "icon": "🐦",
        "description": "Busca nombres de usuario en 300+ plataformas sociales",
        "check_cmd": "blackbird --help 2>/dev/null || nexfil --help 2>/dev/null || echo MISSING",
        "run_cmd": 'blackbird --username "{target}" 2>&1 || nexfil --username "{target}" 2>&1',
        "min_args": 1,
        "arg_help": "Username a buscar",
        "light_package": "nexfil",
        "type": "recon"
    },
    "photon": {
        "name": "Photon Crawler",
        "icon": "🌐",
        "description": "Crawlea un dominio extrayendo URLs, emails, JS, endpoints",
        "check_cmd": "photon --help 2>/dev/null || echo MISSING",
        "run_cmd": 'photon -u "{target}" -o "{output_dir}" --timeout 30 2>&1',
        "min_args": 1,
        "arg_help": "URL/dominio a crawl (ej. https://ejemplo.com)",
        "light_package": "photon",
        "type": "scraper"
    },
    "subdomain_enum": {
        "name": "Subdomain Enum",
        "icon": "🌐",
        "description": "Enumeración de subdominios (subfinder + assetfinder + httpx)",
        "check_cmd": "python -c 'import sys; sys.path.insert(0,\"recon\"); from subdomain_permutator import check_dependencies; import json; print(json.dumps(check_dependencies()))'",
        "run_cmd": 'python -m recon.subdomain_permutator "{target}" --json',
        "min_args": 1,
        "arg_help": "Dominio objetivo (ej. ejemplo.com)",
        "light_package": "go install ...",
        "type": "recon"
    },
    "phoneinfoga": {
        "name": "PhoneInfoga",
        "icon": "📞",
        "description": "Escáner de números telefónicos (OSINT)",
        "check_cmd": "phoneinfoga version 2>/dev/null || echo MISSING",
        "run_cmd": 'phoneinfoga scan -n "{target}" 2>&1',
        "min_args": 1,
        "arg_help": "Número telefónico (ej. +34123456789)",
        "light_package": "phoneinfoga",
        "type": "intel"
    },
    "mrholmes": {
        "name": "Mr. Holmes",
        "icon": "✉️",
        "description": "Análisis de direcciones de email",
        "check_cmd": "mrholmes --help 2>/dev/null || echo MISSING",
        "run_cmd": 'mrholmes "{target}" 2>&1',
        "min_args": 1,
        "arg_help": "Email a analizar",
        "light_package": "mrholmes",
        "type": "intel"
    },
    "crypto_farmer_v2": {
        "name": "RollerCoin Farmer v2",
        "icon": "⛏️",
        "description": "Bot de farming automatizado para RollerCoin con Playwright. Evita validaciones y notifica por WhatsApp.",
        "module_path": "AME_Core/crypto_farmer_v2.py",
        "main_function": "start_session",
        "is_class": True,
        "class_name": "CryptoFarmer",
        "params": {
            "headless": {"type": "bool", "default": True, "description": "Ejecutar en modo sin cabeza."},
            "duration_minutes": {"type": "int", "default": 15, "description": "Duración de la sesión."}
        },
        "category": "Automation"
    },
    "escudo_sentinel": {
        "name": "Escudo Sentinel",
        "icon": "🛡️",
        "description": "Sistema IPS local. Monitoriza puertos sospechosos y alerta a Firebase.",
        "module_path": "AME_Core/escudo_monitor.py",
        "main_function": "check_connections",
        "is_class": False,
        "params": {
            "interval_seconds": {"type": "int", "default": 30, "description": "Intervalo en segundos."}
        },
        "category": "Defense"
    },
    "blue_financial_node": {
        "name": "B.L.U.E. Financial Report",
        "icon": "💹",
        "description": "Nodo analítico que calcula rentabilidad, uptime y proyecciones del ecosistema autónomo.",
        "module_path": "tools/BLUE_Financial_Node.py",
        "main_function": "generar_reporte_blue",
        "is_class_method": True,
        "class_name": "BLUEFinancialNode",
        "params": {},
        "category": "Analytics"
    }
}


def log_health(component, status, detail=""):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{ts}] {component}: {status}"
    if detail:
        entry += f" — {detail}"
    with open(HEALTH_LOG, "a", encoding="utf-8") as f:
        f.write(entry + "\n")
    print(entry)


def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {}
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def is_tool_available(tool_name):
    """Verifica si una herramienta está instalada en el sistema."""
    if tool_name not in TOOL_REGISTRY:
        return False
    entry = TOOL_REGISTRY[tool_name]
    # Herramientas Python (crypto_farmer, escudo, subdomain) siempre disponibles si el archivo existe
    if "module_path" in entry:
        module_file = AURA_CORE_PATH.parent / entry["module_path"]
        return module_file.exists()
    check_cmd = entry.get("check_cmd", "")
    if not check_cmd:
        return shutil.which(tool_name) is not None
    try:
        result = subprocess.run(
            check_cmd, shell=True, capture_output=True, text=True, timeout=10
        )
        available = result.returncode == 0 and "MISSING" not in result.stdout
        return available
    except Exception:
        return shutil.which(tool_name) is not None


def get_tool_info(tool_name):
    """Devuelve la info registrada de una herramienta, o None."""
    return TOOL_REGISTRY.get(tool_name)


def execute_single_tool(tool_name, target=None, output_dir=None, timeout=120, params=None, run_in_background=True):
    """
    Ejecuta una sola herramienta y devuelve dict con resultado.
    Soporta:
      - Herramientas CLI (subprocess)
      - Módulos Python (subdomain_enum, crypto_farmer_v2, escudo_sentinel)
      - Ejecución en segundo plano (threading.Thread)
    """
    if tool_name not in TOOL_REGISTRY:
        return {"tool": tool_name, "status": "error", "error": f"Herramienta desconocida: {tool_name}"}

    entry = TOOL_REGISTRY[tool_name]

    # ── Caso especial: subdomain_enum usa el módulo Python de Venice ──
    if tool_name == "subdomain_enum" and SUBDOMAIN_ENUM_AVAILABLE and _run_subdomain_enum:
        print(f"  ⚡ Ejecutando {entry['icon']} {entry['name']}: {target}")
        log_health("SKILLS_FORGE", "RUNNING", f"{entry['name']} → {target}")
        try:
            result = _run_subdomain_enum(target)
            log_health("SKILLS_FORGE", "OK", f"{entry['name']} completado: {result.get('live_hosts_count', 0)} hosts")
            return {
                "tool": tool_name,
                "status": "ok",
                "output": json.dumps(result, indent=2),
                "returncode": 0,
                "parsed": result
            }
        except Exception as e:
            log_health("SKILLS_FORGE", "ERROR", f"{entry['name']}: {str(e)}")
            return {"tool": tool_name, "status": "exception", "error": str(e)}
    elif tool_name == "subdomain_enum":
        return {"tool": tool_name, "status": "unavailable",
                "error": f"{entry['icon']} {entry['name']}: módulo Python no disponible. Verifica AURA_Core/recon/subdomain_permutator.py"}

    # ── Herramientas con módulo Python (crypto_farmer, escudo) ──
    if "module_path" in entry:
        module_file = AURA_CORE_PATH.parent / entry["module_path"]
        function_name = entry["main_function"]

        if not module_file.exists():
            return {"tool": tool_name, "status": "unavailable",
                    "error": f"Módulo no encontrado: {module_file}"}

        try:
            spec = importlib.util.spec_from_file_location(function_name, str(module_file))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception as e:
            return {"tool": tool_name, "status": "error", "error": f"Error cargando módulo: {e}"}

        # ── Caso: clase (CryptoFarmer, BLUEFinancialNode) ──
        # Soporta is_class=True (crypto_farmer) e is_class_method=True (blue_financial_node)
        if entry.get("is_class") or entry.get("is_class_method"):
            class_name = entry.get("class_name")
            if not class_name:
                return {"tool": tool_name, "status": "error", "error": "Falta class_name en TOOL_REGISTRY"}
            Cls = getattr(module, class_name, None)
            if Cls is None:
                return {"tool": tool_name, "status": "error", "error": f"Clase '{class_name}' no encontrada en el módulo"}
            # Construir kwargs para la clase desde params
            kwargs = {}
            if params:
                kwargs.update(params)
            # Importar CONFIG del módulo o usar defaults
            default_config = getattr(module, "CONFIG", {})
            instance = Cls(default_config)

            tool_func = getattr(instance, function_name, None)
            if tool_func is None:
                return {"tool": tool_name, "status": "error", "error": f"Método '{function_name}' no encontrado en clase '{class_name}'"}

            print(f"  ⚡ Ejecutando {entry['icon']} {entry['name']} en {('2º plano' if run_in_background else '1er plano')}")
            log_health("SKILLS_FORGE", "RUNNING", f"{entry['name']} (clase)")

            # Variable compartida para capturar el return value en ejecución síncrona
            _sync_result = [None]

            def run_class_tool():
                try:
                    ret = tool_func(**kwargs)
                    _sync_result[0] = ret
                except Exception as e:
                    print(f"[Skills Forge] Error en '{entry['name']}': {e}")
                    log_health("SKILLS_FORGE", "ERROR", f"{entry['name']}: {e}")

            if run_in_background:
                thread = threading.Thread(target=run_class_tool, daemon=True)
                thread.start()
                return {"tool": tool_name, "status": "ok", "message": f"{entry['icon']} {entry['name']} iniciado en 2º plano"}
            else:
                run_class_tool()
                result_val = _sync_result[0]
                if result_val is not None:
                    return {"tool": tool_name, "status": "ok", "result": result_val}
                return {"tool": tool_name, "status": "ok", "message": f"{entry['icon']} {entry['name']} completado"}

        # ── Caso: función directa (check_connections) ──
        else:
            tool_func = getattr(module, function_name, None)
            if tool_func is None:
                return {"tool": tool_name, "status": "error", "error": f"Función '{function_name}' no encontrada en el módulo"}

            print(f"  ⚡ Ejecutando {entry['icon']} {entry['name']} en {('2º plano' if run_in_background else '1er plano')}")
            log_health("SKILLS_FORGE", "RUNNING", f"{entry['name']} (función)")

            # Para escudo_sentinel: si hay interval_seconds, ejecutar en bucle
            interval = (params or {}).get("interval_seconds", 30)

            def run_function_tool():
                try:
                    if function_name == "check_connections":
                        # Bucle de monitoreo con intervalo
                        while True:
                            tool_func()
                            time.sleep(interval)
                    else:
                        tool_func(**params) if params else tool_func()
                except Exception as e:
                    print(f"[Skills Forge] Error en '{entry['name']}': {e}")
                    log_health("SKILLS_FORGE", "ERROR", f"{entry['name']}: {e}")

            if run_in_background:
                thread = threading.Thread(target=run_function_tool, daemon=True)
                thread.start()
                return {"tool": tool_name, "status": "ok", "message": f"{entry['icon']} {entry['name']} iniciado en 2º plano (intervalo: {interval}s)"}
            else:
                run_function_tool()
                return {"tool": tool_name, "status": "ok", "message": f"{entry['icon']} {entry['name']} completado"}

    # ── Herramientas CLI (exiftool, blackbird, photon, phoneinfoga, mrholmes) ──
    if not is_tool_available(tool_name):
        msg = f"{entry['icon']} {entry['name']} no instalada. Usa install_manager.py"
        log_health("SKILLS_FORGE", "ERROR", msg)
        return {"tool": tool_name, "status": "unavailable", "error": msg}

    cmd_template = entry["run_cmd"]
    cmd = cmd_template.replace("{target}", target or "").replace("{output_dir}", output_dir or os.path.join(BASE_DIR, "forge_output"))

    print(f"  ⚡ Ejecutando {entry['icon']} {entry['name']}: {cmd}")
    log_health("SKILLS_FORGE", "RUNNING", f"{entry['name']} → {target or 'sin target'}")

    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        output = result.stdout[:2000] + ("\n..." if len(result.stdout) > 2000 else "")
        stderr = result.stderr[:500]

        if result.returncode == 0:
            log_health("SKILLS_FORGE", "OK", f"{entry['name']} completado")
            return {"tool": tool_name, "status": "ok", "output": output, "returncode": 0}
        else:
            log_health("SKILLS_FORGE", "ERROR", f"{entry['name']} falló: {stderr[:200]}")
            return {"tool": tool_name, "status": "error", "output": output, "stderr": stderr, "returncode": result.returncode}

    except subprocess.TimeoutExpired:
        log_health("SKILLS_FORGE", "ERROR", f"{entry['name']} timeout ({timeout}s)")
        return {"tool": tool_name, "status": "timeout", "error": f"Excedió {timeout}s"}
    except Exception as e:
        log_health("SKILLS_FORGE", "ERROR", f"{entry['name']}: {str(e)}")
        return {"tool": tool_name, "status": "exception", "error": str(e)}


def resolve_skill_chain(skills_list, targets=None):
    """
    Convierte una lista de nombres de herramientas en una cadena de ejecución
    ordenada. Si detecta combinaciones conocidas, resuelve targets intermedios.
    """
    if targets is None:
        targets = {}

    COMBINED_FLOWS = {
        ("blackbird", "phoneinfoga"): {
            "label": "username → phone",
            "description": "Busca usuario con Blackbird, extrae teléfono asociado y lo pasa a PhoneInfoga",
            "chain": True
        },
        ("blackbird", "photon"): {
            "label": "username → domain",
            "description": "Encuentra perfiles del usuario, crawlea los dominios encontrados",
            "chain": True
        },
        ("photon", "exiftool"): {
            "label": "domain → images",
            "description": "Crawlea el dominio, encuentra imágenes y extrae su EXIF",
            "chain": True
        },
        ("exiftool", "phoneinfoga"): {
            "label": "image → phone",
            "description": "Extrae metadatos de imagen, busca teléfonos/emails encontrados",
            "chain": True
        }
    }

    resolved = []
    for i, skill in enumerate(skills_list):
        entry = get_tool_info(skill)
        target = targets.get(skill, targets.get("_default", None))

        if i > 0:
            prev_skill = skills_list[i - 1]
            pair = (prev_skill, skill)
            if pair in COMBINED_FLOWS:
                resolved.append({
                    "step": i,
                    "flow": COMBINED_FLOWS[pair]["label"],
                    "description": COMBINED_FLOWS[pair]["description"],
                    "tool": skill,
                    "target": target,
                    "tool_info": entry
                })
                continue

        resolved.append({
            "step": i,
            "tool": skill,
            "target": target,
            "tool_info": entry
        })

    return resolved


def execute_skill_chain(skills_list, targets=None, output_dir=None):
    """
    Recibe un array de herramientas (ej. ['blackbird', 'phoneinfoga'])
    y las ejecuta en secuencia. Retorna un dict con el resultado de cada paso.
    """
    print(f"\n{'='*50}")
    print(f"🔨 SKILL FORGE — Ejecutando cadena: {skills_list}")
    print(f"{'='*50}")

    chain = resolve_skill_chain(skills_list, targets)
    results = []
    all_ok = True

    for step in chain:
        tool = step["tool"]
        target = step.get("target")
        tool_info = step.get("tool_info")

        print(f"\n  📍 Paso {step['step']+1}: {tool_info['icon'] if tool_info else '❓'} {tool}")
        if "flow" in step:
            print(f"     🌊 Flujo combinado: {step['flow']} — {step['description']}")

        # Para crypto_farmer y escudo: ejecutar en background siempre
        run_bg = tool in ("crypto_farmer_v2", "escudo_sentinel")

        result = execute_single_tool(
            tool,
            target=target,
            output_dir=output_dir,
            run_in_background=run_bg
        )
        result["step"] = step["step"]
        result["flow"] = step.get("flow")
        results.append(result)

        if result["status"] != "ok":
            all_ok = False
            if result["status"] == "unavailable":
                print(f"     ⛔ Cadena detenida: {tool} no disponible")
                break

        time.sleep(1)

    summary = {
        "chain": chain,
        "results": results,
        "total_steps": len(chain),
        "completed": len(results),
        "all_ok": all_ok,
        "status": "completed" if all_ok else "partial_failure"
    }

    log_health("SKILLS_FORGE", summary["status"].upper(),
               f"Cadena {skills_list}: {len(results)}/{len(chain)} pasos")

    print(f"\n{'='*50}")
    print(f"  ✅ Cadena completada: {summary['completed']}/{summary['total_steps']} pasos")
    print(f"{'='*50}")

    return summary


def list_available_tools():
    """Lista todas las herramientas registradas y su estado de instalación."""
    available = []
    for tool_id, info in TOOL_REGISTRY.items():
        avail = is_tool_available(tool_id)
        available.append({
            "id": tool_id,
            "name": info["name"],
            "icon": info["icon"],
            "description": info["description"],
            "available": avail,
            "type": info.get("type", info.get("category", "other")),
            "light_package": info.get("light_package", "N/A")
        })
    return available


# ────────────── CLI ──────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="AURA Skills Forge")
    parser.add_argument("action", choices=["run", "list", "check"],
                        help="run=ejecutar cadena, list=listar herramientas, check=verificar disponibilidad")
    parser.add_argument("--skills", "-s", nargs="+",
                        help="Lista de herramientas a ejecutar (ej. -s blackbird phoneinfoga)")
    parser.add_argument("--target", "-t", help="Target por defecto para todas las herramientas")
    parser.add_argument("--targets", "-T", help="JSON con targets específicos por herramienta")
    parser.add_argument("--background", "-b", action="store_true", help="Ejecutar en segundo plano")
    args = parser.parse_args()

    if args.action == "list":
        tools = list_available_tools()
        print(f"\n{'='*50}")
        print("  🔨 SKILL FORGE — Herramientas Registradas")
        print(f"{'='*50}")
        for t in tools:
            status = "✅" if t["available"] else "❌"
            print(f"  {status} {t['icon']} {t['name']:<20} ({t['id']})")
            print(f"     {t['description']}")
        print()

    elif args.action == "check":
        tools = list_available_tools()
        for t in tools:
            status = "✅ DISPONIBLE" if t["available"] else "❌ NO INSTALADA"
            print(f"  {t['icon']} {t['name']:<20} → {status}")

    elif args.action == "run":
        if not args.skills:
            print("❌ Especifica --skills (ej. --skills blackbird phoneinfoga)")
            sys.exit(1)

        targets = {}
        if args.targets:
            try:
                targets = json.loads(args.targets)
            except json.JSONDecodeError:
                print("❌ --targets debe ser JSON válido")
                sys.exit(1)
        if args.target:
            targets["_default"] = args.target

        print(f"\n🔨 Ejecutando cadena: {args.skills}")
        print(f"   Targets: {targets}")
        result = execute_skill_chain(args.skills, targets=targets)
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))