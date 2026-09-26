"""
patch_injector.py - MODO INYECTOR
Monitoriza incoming_patches/ y analiza parches contra shadow_core.py
Espera señal 'APLICAR PARCHE' antes de fusionar.
"""

import os
import sys
import time
import hashlib
import importlib.util
import ast
from typing import Dict, Any, Optional, List

# Configuración
INCOMING_DIR = os.path.join(os.path.dirname(__file__), "incoming_patches")
SHADOW_CORE_PATH = os.path.join(os.path.dirname(__file__), "AME_Core", "shadow_core.py")
PROCESSED_DIR = os.path.join(INCOMING_DIR, "processed")
REJECTED_DIR = os.path.join(INCOMING_DIR, "rejected")

# Ensure directories exist
for d in [INCOMING_DIR, PROCESSED_DIR, REJECTED_DIR]:
    os.makedirs(d, exist_ok=True)


def sha256_file(path: str) -> str:
    """SHA-256 checksum de un archivo."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(4096), b""):
            h.update(block)
    return h.hexdigest()


def load_shadow_core_structure() -> Dict[str, Any]:
    """
    Analiza shadow_core.py y retorna su estructura:
    - funciones exportadas
    - clases con métodos
    - imports
    - endpoints (decoradores @app)
    """
    if not os.path.exists(SHADOW_CORE_PATH):
        return {"error": "shadow_core.py no encontrado"}

    with open(SHADOW_CORE_PATH, "r", encoding="utf-8") as f:
        source = f.read()

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return {"error": f"Error de sintaxis: {e}"}

    structure = {
        "imports": [],
        "classes": {},
        "functions": [],
        "endpoints": [],
        "version": "unknown"
    }

    for node in ast.walk(tree):
        # Imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                structure["imports"].append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                structure["imports"].append(f"{module}.{alias.name}")

        # Clases
        if isinstance(node, ast.ClassDef):
            methods = []
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    methods.append(item.name)
            structure["classes"][node.name] = methods

        # Funciones nivel módulo
        if isinstance(node, ast.FunctionDef):
            structure["functions"].append(node.name)

        # Decoradores @app.route / @app.post / @app.get
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call):
                    if hasattr(dec.func, 'attr') and dec.func.attr in ('route', 'post', 'get', 'put', 'delete'):
                        if dec.args:
                            try:
                                path = dec.args[0].value if hasattr(dec.args[0], 'value') else str(dec.args[0])
                                structure["endpoints"].append({
                                    "method": dec.func.attr.upper(),
                                    "path": path,
                                    "handler": node.name
                                })
                            except Exception:
                                pass

    # Versión desde el docstring o variable
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "SHADOW_CORE_PORT":
                    try:
                        structure["port"] = node.value.value
                    except Exception:
                        pass

    return structure


def analyze_patch(patch_path: str) -> Dict[str, Any]:
    """
    Analiza un archivo .py como posible parche.
    Retorna:
    - nombre
    - funciones/classes que define
    - qué endpoints expone
    - dependecias
    - compatibilidad con shadow_core
    """
    result = {
        "filename": os.path.basename(patch_path),
        "sha256": sha256_file(patch_path),
        "size": os.path.getsize(patch_path),
        "status": "pending",
        "functions": [],
        "classes": [],
        "imports": [],
        "endpoints": [],
        "compatibility": {
            "compatible": True,
            "warnings": []
        },
        "integration_plan": {}
    }

    with open(patch_path, "r", encoding="utf-8") as f:
        source = f.read()

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        result["status"] = "rejected"
        result["compatibility"]["compatible"] = False
        result["compatibility"]["warnings"].append(f"SyntaxError: {e}")
        return result

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            methods = [m.name for m in node.body if isinstance(m, ast.FunctionDef)]
            result["classes"].append({"name": node.name, "methods": methods})
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result["functions"].append(node.name)
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in (node.names if hasattr(node, 'names') else []):
                result["imports"].append(alias.name if hasattr(alias, 'name') else str(alias))

    # Verificar compatibilidad
    core_structure = load_shadow_core_structure()
    
    # Buscar conflictos de nombres
    if "error" not in core_structure:
        for fn in result["functions"]:
            if fn in core_structure.get("functions", []):
                result["compatibility"]["warnings"].append(
                    f"Función '{fn}' ya existe en shadow_core.py - podría sobrescribirse"
                )

        for cls_name in [c["name"] for c in result["classes"]]:
            if cls_name in core_structure.get("classes", {}):
                result["compatibility"]["warnings"].append(
                    f"Clase '{cls_name}' ya existe en shadow_core.py - podría sobrescribirse"
                )

    # Plan de integración
    result["integration_plan"] = {
        "file": patch_path,
        "target": SHADOW_CORE_PATH,
        "actions": []
    }

    if result["classes"]:
        result["integration_plan"]["actions"].append(
            f"Insertar clase(es): {', '.join(c['name'] for c in result['classes'])}"
        )
    if result["functions"]:
        result["integration_plan"]["actions"].append(
            f"Insertar función(es): {', '.join(result['functions'])}"
        )
    if result["endpoints"]:
        result["integration_plan"]["actions"].append(
            f"Registrar endpoint(s): {', '.join(e['path'] for e in result['endpoints'])}"
        )

    result["integration_plan"]["actions"].append(
        "AGUARDANDO SEÑAL: 'APLICAR PARCHE' para fusionar en shadow_core.py"
    )

    return result


def scan_incoming() -> List[Dict[str, Any]]:
    """Escanea incoming_patches/ y analiza cada .py no procesado."""
    patches = []
    for fname in os.listdir(INCOMING_DIR):
        if not fname.endswith(".py"):
            continue
        fpath = os.path.join(INCOMING_DIR, fname)
        if os.path.isfile(fpath):
            analysis = analyze_patch(fpath)
            patches.append(analysis)
    return patches


def generate_report_html(patches: List[Dict[str, Any]]) -> str:
    """Genera un reporte HTML de los parches encontrados."""
    html = """
    <div style="font-family:'Courier New',monospace;background:#0a0f1e;color:#00d4ff;padding:20px;">
        <h2 style="color:#ff3366;text-shadow:0 0 10px rgba(255,51,102,0.5);">
            🛡️ MODO INYECTOR - REPORTE DE PARCHE
        </h2>
        <hr style="border:1px solid #1f2937;">
    """
    for p in patches:
        status_color = "#00ff88" if p["compatibility"]["compatible"] else "#ff3366"
        html += f"""
        <div style="border:1px solid {status_color};border-radius:8px;padding:12px;margin:10px 0;
                    background:rgba(10,15,26,0.8);">
            <div style="display:flex;justify-content:space-between;">
                <span style="font-weight:bold;">📦 {p['filename']}</span>
                <span style="color:{status_color};">{'✅ COMPATIBLE' if p['compatibility']['compatible'] else '❌ RECHAZADO'}</span>
            </div>
            <div style="margin-top:8px;font-size:12px;color:#ccc;">
                <div>🔑 SHA256: <span style="color:#ffcc00;">{p['sha256'][:16]}...</span></div>
                <div>📏 Tamaño: {p['size']} bytes</div>
                <div>🧩 Clases: {', '.join(c['name'] for c in p['classes']) or 'ninguna'}</div>
                <div>⚙️ Funciones: {', '.join(p['functions']) or 'ninguna'}</div>
        """
        if p["compatibility"]["warnings"]:
            html += '<div style="color:#ffcc00;margin-top:5px;">⚠️ Advertencias:<ul>'
            for w in p["compatibility"]["warnings"]:
                html += f"<li>{w}</li>"
            html += "</ul></div>"
        html += """
            <div style="margin-top:8px;border-top:1px solid #1f2937;padding-top:8px;">
                <strong>🔧 Plan de integración:</strong>
                <ul style="color:#ffcc00;font-size:11px;">
        """
        for action in p["integration_plan"]["actions"]:
            html += f"<li>{action}</li>"
        html += """
                </ul>
            </div>
        </div>
        """
    html += "</div>"
    return html


def watch_loop(interval: int = 5):
    """
    Bucle principal del Modo Inyector.
    Monitorea incoming_patches/ cada N segundos.
    """
    print("🛡️  MODO INYECTOR ACTIVADO")
    print(f"📁 Monitorizando: {INCOMING_DIR}")
    print(f"🎯 Referencia: shadow_core.py")
    print(f"⏱️  Intervalo: {interval}s")
    print("-" * 50)

    known_files: Dict[str, str] = {}  # filename -> sha256

    while True:
        current_files = {}
        for fname in os.listdir(INCOMING_DIR):
            if not fname.endswith(".py"):
                continue
            fpath = os.path.join(INCOMING_DIR, fname)
            if os.path.isfile(fpath):
                current_files[fname] = sha256_file(fpath)

        for fname, sha in current_files.items():
            if fname not in known_files or known_files[fname] != sha:
                # Nuevo parche o modificado
                print(f"\n🔍 NUEVO PARCHE DETECTADO: {fname}")
                fpath = os.path.join(INCOMING_DIR, fname)
                analysis = analyze_patch(fpath)

                if analysis["status"] == "rejected":
                    print(f"❌ PARCHE RECHAZADO: {analysis['compatibility']['warnings'][0]}")
                    # Mover a rejected
                    dst = os.path.join(REJECTED_DIR, fname)
                    os.rename(fpath, dst)
                    print(f"   Movido a: {dst}")
                    continue

                print(f"✅ PARCHE ANALIZADO: {fname}")
                print(f"   SHA256: {sha[:16]}...")
                print(f"   Clases: {', '.join(c['name'] for c in analysis['classes']) or 'ninguna'}")
                print(f"   Funciones: {', '.join(analysis['functions']) or 'ninguna'}")
                if analysis["compatibility"]["warnings"]:
                    print(f"   ⚠️  Advertencias:")
                    for w in analysis["compatibility"]["warnings"]:
                        print(f"        - {w}")
                print()
                print("   ⏳ AGUARDANDO SEÑAL: 'APLICAR PARCHE'")
                print("   Envía 'APLICAR PARCHE' para fusionar en shadow_core.py")
                print("-" * 50)

        known_files = current_files
        time.sleep(interval)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        # Escaneo único
        patches = scan_incoming()
        if patches:
            print(generate_report_html(patches))
        else:
            print("📭 No hay parches pendientes en incoming_patches/")
    else:
        # Modo watch continuo
        watch_loop()