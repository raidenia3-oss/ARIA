#!/usr/bin/env python3
"""
AURA Forensics & Intelligence Service v1
=========================================
FASE 1: Ingeniería Inversa Android (MobSF API bridge + scripts Frida/JADX/Drozer)
FASE 2: Forense Digital (ExifTool metadata + Volatility 3 memory analysis)

Endpoints:
  POST /api/forensics/exif             — Extraer metadatos EXIF de imágenes
  POST /api/forensics/memory-analysis   — Analizar volcados de RAM con Volatility 3
  POST /api/forensics/mobsf/upload      — Subir APK a MobSF para análisis
  GET  /api/forensics/mobsf/report/{hash} — Obtener reporte JSON de MobSF
"""

import os
import json
import asyncio
import logging
import tempfile
import subprocess
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from io import BytesIO

# ─── Logging ───
logger = logging.getLogger(__name__)

# ─── Constantes ───
MOBSF_URL = os.getenv("MOBSF_URL", "http://localhost:8000")
MOBSF_API_KEY = os.getenv("MOBSF_API_KEY", "")
VOLATILITY_PATH = "volatility3"  # asumimos en PATH tras pip install volatility3

# ─── FASE 1: MOBSF API BRIDGE ─────────────────────────────────────


class MobSFBridge:
    """Bridge para interactuar con la API de MobSF (Docker)."""

    @staticmethod
    async def upload_apk(apk_path: str) -> Dict[str, Any]:
        """
        Subir APK a MobSF para análisis estático.

        Args:
            apk_path: Ruta local al archivo APK

        Returns:
            Dict con hash del análisis y URL del reporte
        """
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                with open(apk_path, "rb") as f:
                    files = {
                        "file": (Path(apk_path).name, f, "application/vnd.android.package-archive")
                    }
                    headers = {"Authorization": MOBSF_API_KEY} if MOBSF_API_KEY else {}

                    resp = await client.post(
                        f"{MOBSF_URL}/api/v1/upload", files=files, headers=headers, timeout=120
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        logger.info(f"APK subido a MobSF. Hash: {data.get('hash', 'N/A')}")
                        return {
                            "status": "ok",
                            "hash": data.get("hash"),
                            "filename": data.get("file_name"),
                        }
                    else:
                        return {
                            "status": "error",
                            "detail": f"HTTP {resp.status_code}: {resp.text[:200]}",
                        }

        except ImportError:
            return {"status": "error", "detail": "httpx no instalado"}
        except Exception as e:
            logger.error(f"Error subiendo APK a MobSF: {e}")
            return {"status": "error", "detail": str(e)[:300]}

    @staticmethod
    async def start_scan(file_hash: str, scan_type: str = "static") -> Dict[str, Any]:
        """
        Iniciar escaneo en MobSF.

        Args:
            file_hash: Hash devuelto por upload_apk
            scan_type: 'static' | 'dynamic'

        Returns:
            Resultado del escaneo
        """
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                headers = {"Authorization": MOBSF_API_KEY} if MOBSF_API_KEY else {}
                resp = await client.post(
                    f"{MOBSF_URL}/api/v1/scan",
                    data={"hash": file_hash, "scan_type": scan_type},
                    headers=headers,
                    timeout=300,
                )
                if resp.status_code == 200:
                    return {"status": "ok", "scan_type": scan_type, "data": resp.json()}
                else:
                    return {
                        "status": "error",
                        "detail": f"HTTP {resp.status_code}: {resp.text[:200]}",
                    }
        except Exception as e:
            return {"status": "error", "detail": str(e)[:300]}

    @staticmethod
    async def get_report(file_hash: str) -> Dict[str, Any]:
        """Obtener el reporte JSON del análisis de MobSF."""
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                headers = {"Authorization": MOBSF_API_KEY} if MOBSF_API_KEY else {}
                resp = await client.get(
                    f"{MOBSF_URL}/api/v1/report_json",
                    params={"hash": file_hash},
                    headers=headers,
                    timeout=30,
                )
                if resp.status_code == 200:
                    return {"status": "ok", "report": resp.json()}
                else:
                    return {
                        "status": "error",
                        "detail": f"HTTP {resp.status_code}: {resp.text[:200]}",
                    }
        except Exception as e:
            return {"status": "error", "detail": str(e)[:300]}

    @staticmethod
    async def health_check() -> Dict[str, Any]:
        """Verificar si MobSF está corriendo."""
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{MOBSF_URL}/api/v1/health", timeout=5)
                return {
                    "status": "ok" if resp.status_code == 200 else "error",
                    "code": resp.status_code,
                }
        except Exception as e:
            return {"status": "unreachable", "detail": str(e)[:200]}


# ─── FASE 1: SCRIPTS DE FRIDA/JADX/DROZER ────────────────────────

FRIDA_TEMPLATE = """\
// AUTO-GENERATED FRIDA HOOK — AURA Forensics
// Uso: frida -U com.ame.ecosystem -l {script_name}

'use strict';

Java.perform(function () {{
    console.log("[AURA] Hook cargado correctamente");

    // Hook a clase de red para interceptar tráfico
    var OkHttpClient = Java.use('okhttp3.OkHttpClient');
    OkHttpClient.newCall.overload('okhttp3.Request').implementation = function (request) {{
        console.log("[NET] URL: " + request.url());
        console.log("[NET] Method: " + request.method());
        console.log("[NET] Headers: " + JSON.stringify(request.headers().toMultimap()));
        return this.newCall(request);
    }};

    // Hook a funciones de logging
    var Log = Java.use('android.util.Log');
    Log.d.overload('java.lang.String', 'java.lang.String').implementation = function (tag, msg) {{
        console.log("[LOG] " + tag + ": " + msg);
        return this.d(tag, msg);
    }};

    // Hook a crypto
    var Cipher = Java.use('javax.crypto.Cipher');
    Cipher.doFinal.overload('[B').implementation = function (input) {{
        console.log("[CRYPTO] Cipher.doFinal llamado, len=" + input.length);
        return this.doFinal(input);
    }};
}});
"""


def generate_frida_script(
    package: str = "com.ame.ecosystem", output_dir: str = "security-tools/frida-scripts"
) -> str:
    """Generar un script de Frida para hooking automático."""
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    script_path = path / f"aura_hook_{package.replace('.', '_')}.js"
    script_path.write_text(FRIDA_TEMPLATE.format(script_name=script_path.name))
    logger.info(f"Script Frida generado: {script_path}")
    return str(script_path)


def run_jadx(apk_path: str, output_dir: str = None) -> Dict[str, Any]:
    """
    Ejecutar JADX para descompilar un APK.

    Args:
        apk_path: Ruta al archivo APK
        output_dir: Directorio de salida (opcional)

    Returns:
        Dict con resultado
    """
    # Buscar JADX en rutas conocidas
    jadx_paths = [
        Path("security-tools/jadx/bin/jadx"),
        Path("security-tools/jadx/bin/jadx.bat"),
        Path.home() / "security-tools" / "jadx" / "bin" / "jadx",
        Path.home() / "security-tools" / "jadx" / "bin" / "jadx.bat",
    ]

    jadx = None
    for p in jadx_paths:
        if p.exists():
            jadx = str(p)
            break

    if not jadx:
        # Buscar en PATH
        try:
            import shutil

            jadx = shutil.which("jadx")
        except:
            pass

    if not jadx:
        return {
            "status": "error",
            "detail": "JADX no encontrado. Descarga desde https://github.com/skylot/jadx/releases",
        }

    if not output_dir:
        output_dir = str(Path(apk_path).parent / f"{Path(apk_path).stem}_jadx_output")

    try:
        result = subprocess.run(
            [jadx, "--show-bad-code", "-d", output_dir, apk_path],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            return {
                "status": "ok",
                "output_dir": output_dir,
                "message": "Descompilación completada",
            }
        else:
            return {"status": "error", "detail": result.stderr[:500], "output": result.stdout[:500]}

    except subprocess.TimeoutExpired:
        return {"status": "error", "detail": "Timeout: el APK es muy grande o JADX se colgó"}
    except Exception as e:
        return {"status": "error", "detail": str(e)[:300]}


# ─── FASE 2: EXIFTOOL / METADATOS ────────────────────────────────


def extract_exif(file_bytes: bytes, filename: str = "unknown") -> Dict[str, Any]:
    """
    Extraer metadatos EXIF de un archivo de imagen usando Pillow.

    Args:
        file_bytes: Contenido del archivo en bytes
        filename: Nombre original del archivo

    Returns:
        Dict con todos los metadatos encontrados
    """
    result = {
        "filename": filename,
        "timestamp": datetime.now().isoformat(),
        "metadata": {},
        "gps": None,
        "software": None,
        "timestamps": {},
        "warnings": [],
    }

    try:
        from PIL import Image
        from PIL.ExifTags import TAGS, GPSTAGS

        img = Image.open(BytesIO(file_bytes))
        exif_data = img._getexif() if hasattr(img, "_getexif") else None

        if not exif_data:
            result["warnings"].append("No EXIF data found")
            return result

        # Extraer tags estándar
        for tag_id, value in exif_data.items():
            tag_name = TAGS.get(tag_id, str(tag_id))
            result["metadata"][tag_name] = str(value)

            # Capturar timestamps
            if tag_name in ("DateTime", "DateTimeOriginal", "DateTimeDigitized"):
                result["timestamps"][tag_name] = str(value)

            # Capturar software
            if tag_name == "Software":
                result["software"] = str(value)

        # Extraer GPS
        if hasattr(img, "tag"):
            gps_info = exif_data.get(34853)  # GPSInfo tag
            if gps_info:
                gps_data = {}
                for k, v in gps_info.items():
                    gps_tag = GPSTAGS.get(k, str(k))
                    gps_data[gps_tag] = str(v)
                result["gps"] = gps_data

        img.close()

    except ImportError:
        result["warnings"].append("Pillow no instalado. pip install Pillow")
    except Exception as e:
        result["errors"] = str(e)[:200]

    return result


def format_gps_for_map(gps_data: Dict) -> Optional[Dict]:
    """Convertir datos GPS de EXIF a coordenadas decimales."""
    try:

        def _to_decimal(values, ref):
            if not values or len(values) != 3:
                return None
            d, m, s = float(values[0]), float(values[1]), float(values[2])
            decimal = d + (m / 60.0) + (s / 3600.0)
            if ref in ("S", "W"):
                decimal = -decimal
            return decimal

        lat = _to_decimal(gps_data.get("GPSLatitude"), gps_data.get("GPSLatitudeRef"))
        lon = _to_decimal(gps_data.get("GPSLongitude"), gps_data.get("GPSLongitudeRef"))

        if lat and lon:
            return {
                "latitude": lat,
                "longitude": lon,
                "google_maps": f"https://maps.google.com/?q={lat},{lon}",
            }
        return None
    except:
        return None


# ─── FASE 2: VOLATILITY 3 MEMORY ANALYSIS ────────────────────────


class VolatilityAnalyzer:
    """Wrapper para Volatility 3 con análisis de memoria RAM."""

    @staticmethod
    def _run_volatility(memory_file: str, plugin: str, **kwargs) -> Dict[str, Any]:
        """
        Ejecutar un plugin de Volatility 3.

        Args:
            memory_file: Ruta al volcado de memoria (.raw, .vmem, .mem)
            plugin: Nombre del plugin (windows.pslist, windows.netscan, etc.)
            **kwargs: Argumentos adicionales

        Returns:
            Dict con stdout, stderr y exit code
        """
        if not os.path.exists(memory_file):
            return {"status": "error", "detail": f"Archivo no encontrado: {memory_file}"}

        cmd = [VOLATILITY_PATH, "-f", memory_file, plugin]
        for k, v in kwargs.items():
            cmd.extend([f"--{k.replace('_', '-')}", str(v)])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            return {
                "status": "ok" if result.returncode == 0 else "error",
                "plugin": plugin,
                "stdout": result.stdout[:50000],
                "stderr": result.stderr[:5000],
                "exit_code": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"status": "error", "plugin": plugin, "detail": "Timeout (600s)"}
        except FileNotFoundError:
            return {
                "status": "error",
                "detail": "Volatility 3 no encontrado. pip install volatility3",
            }
        except Exception as e:
            return {"status": "error", "detail": str(e)[:300]}

    @staticmethod
    def list_processes(memory_file: str) -> Dict[str, Any]:
        """Listar procesos activos en el momento del dump."""
        result = VolatilityAnalyzer._run_volatility(memory_file, "windows.pslist")
        if result.get("status") == "ok":
            # Parsear tabla de procesos
            processes = []
            lines = result["stdout"].split("\n")
            for line in lines[3:]:  # Saltar header
                parts = line.split()
                if len(parts) >= 6 and parts[0].isdigit():
                    processes.append(
                        {
                            "pid": parts[0],
                            "ppid": parts[1],
                            "name": parts[2],
                            "session": parts[4] if len(parts) > 4 else "?",
                        }
                    )
            result["processes"] = processes
            result["count"] = len(processes)
        return result

    @staticmethod
    def list_connections(memory_file: str) -> Dict[str, Any]:
        """Listar conexiones de red activas en el momento del dump."""
        result = VolatilityAnalyzer._run_volatility(memory_file, "windows.netscan")
        if result.get("status") == "ok":
            connections = []
            lines = result["stdout"].split("\n")
            for line in lines:
                if "TCP" in line or "UDP" in line:
                    parts = line.split()
                    if len(parts) >= 7:
                        connections.append(
                            {
                                "protocol": parts[0],
                                "local": parts[2],
                                "remote": parts[3],
                                "state": parts[4] if len(parts) > 4 else "?",
                                "pid": parts[-1] if parts[-1].isdigit() else "?",
                            }
                        )
            result["connections"] = connections
            result["count"] = len(connections)
        return result

    @staticmethod
    def detect_anomalies(memory_file: str) -> Dict[str, Any]:
        """Detectar anomalías básicas en memoria (procesos ocultos, hooks)."""
        results = {"status": "ok", "anomalies": []}

        # 1. Cross-reference de procesos
        pslist = VolatilityAnalyzer._run_volatility(memory_file, "windows.pslist")
        psscan = VolatilityAnalyzer._run_volatility(memory_file, "windows.psscan")

        if pslist.get("status") == "ok" and psscan.get("status") == "ok":
            pslist_pids = set()
            psscan_pids = set()

            for line in pslist.get("stdout", "").split("\n"):
                parts = line.split()
                if len(parts) >= 1 and parts[0].isdigit():
                    pslist_pids.add(parts[0])

            for line in psscan.get("stdout", "").split("\n"):
                parts = line.split()
                if len(parts) >= 1 and parts[0].isdigit():
                    psscan_pids.add(parts[0])

            hidden = psscan_pids - pslist_pids
            if hidden:
                results["anomalies"].append(
                    {"type": "hidden_processes", "count": len(hidden), "pids": list(hidden)[:20]}
                )

        # 2. DLLs inusuales
        dlllist = VolatilityAnalyzer._run_volatility(memory_file, "windows.dlllist")
        if dlllist.get("status") == "ok":
            suspicious_dlls = []
            for line in dlllist.get("stdout", "").split("\n"):
                if any(x in line.lower() for x in ["inject", "packer", "unknown", "hook"]):
                    suspicious_dlls.append(line.strip()[:150])
            if suspicious_dlls:
                results["anomalies"].append(
                    {
                        "type": "suspicious_dlls",
                        "count": len(suspicious_dlls),
                        "details": suspicious_dlls[:10],
                    }
                )

        results["anomaly_count"] = len(results["anomalies"])
        return results


# ─── FUNCIÓN PRINCIPAL DE ANÁLISIS COMPLETO ──────────────────────


async def full_memory_analysis(memory_file: str) -> Dict[str, Any]:
    """Ejecutar análisis completo de memoria con Volatility 3."""
    loop = asyncio.get_event_loop()
    results = {
        "timestamp": datetime.now().isoformat(),
        "file": Path(memory_file).name,
        "size_mb": (
            round(os.path.getsize(memory_file) / (1024 * 1024), 1)
            if os.path.exists(memory_file)
            else 0
        ),
    }

    # Ejecutar en paralelo usando ThreadPoolExecutor
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            "processes": loop.run_in_executor(pool, VolatilityAnalyzer.list_processes, memory_file),
            "connections": loop.run_in_executor(
                pool, VolatilityAnalyzer.list_connections, memory_file
            ),
            "anomalies": loop.run_in_executor(
                pool, VolatilityAnalyzer.detect_anomalies, memory_file
            ),
        }
        for key, future in futures.items():
            try:
                results[key] = await future
            except Exception as e:
                results[key] = {"status": "error", "detail": str(e)[:200]}

    return results
