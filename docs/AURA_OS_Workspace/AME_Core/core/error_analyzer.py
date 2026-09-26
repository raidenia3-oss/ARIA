#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════
# ERROR ANALYZER — Intercepta errores de Gradle/Python/Node
# y envía el log a Hugging Face para análisis y corrección
# automática mediante el modelo Qwen.
# ══════════════════════════════════════════════════════════════

import subprocess
import json
import sys
import os
import urllib.request
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
HF_SERVER = "https://raiden456-slut.hf.space"
ERROR_LOG = BASE_DIR / "error_analysis_log.json"

ANALYSIS_PROMPT_TEMPLATE = """Eres un ingeniero de software senior experto en debugging.
Analiza el siguiente error y proporciona:
1. DIAGNÓSTICO: Qué causó el error (1-2 oraciones)
2. SOLUCIÓN: Código corregido listo para usar
3. PREVENCIÓN: Qué hacer para evitarlo en el futuro

ERROR CAPTURADO:
---
{error_text}
---

Contexto: Proyecto AME/AURA, backend Python/FastAPI, frontend Android/Gradle.
Responde en español técnico, conciso y accionable."""


def send_to_huggingface(error_text):
    """Envía el error a Hugging Face para análisis."""
    prompt = ANALYSIS_PROMPT_TEMPLATE.format(error_text=error_text[:3000])

    payload = json.dumps(
        {
            "messages": [
                {"role": "system", "content": "Eres un experto en debugging de software."},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 1500,
        }
    ).encode("utf-8")

    try:
        req = urllib.request.Request(
            f"{HF_SERVER}/v1/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=60)
        result = json.loads(resp.read().decode("utf-8"))

        choices = result.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "Sin respuesta")
        return "No se pudo analizar el error."
    except Exception as e:
        return f"Error al conectar con Hugging Face: {e}"


def capture_gradle_build(project_path):
    """Captura la salida de un build de Gradle y analiza errores."""
    print("🔨 Ejecutando build de Gradle...")
    try:
        result = subprocess.run(
            ["./gradlew", "assembleDebug", "--stacktrace"],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode != 0:
            error_output = result.stderr or result.stdout
            # Filtrar solo las líneas relevantes del error
            lines = error_output.split("\n")
            error_lines = [
                l
                for l in lines
                if "error" in l.lower() or "exception" in l.lower() or "failed" in l.lower()
            ]
            error_text = "\n".join(error_lines[:50]) or error_output[-2000:]

            print(f"❌ Build falló. Analizando error con IA...")
            analysis = send_to_huggingface(error_text)
            log_error("GRADLE_BUILD", error_text, analysis)
            return {"success": False, "error": error_text, "analysis": analysis}
        else:
            print("✅ Build exitoso!")
            return {"success": True, "output": "BUILD SUCCESSFUL"}
    except subprocess.TimeoutExpired:
        print("⏰ Build excedió el tiempo límite (5 min)")
        return {"success": False, "error": "Timeout", "analysis": "El build tardó demasiado."}
    except FileNotFoundError:
        print("❌ No se encontró gradlew")
        return {
            "success": False,
            "error": "gradlew not found",
            "analysis": "Verifica que gradlew exista.",
        }


def capture_command(command, cwd=None):
    """Captura la salida de un comando arbitrario y analiza errores."""
    print(f"🔧 Ejecutando: {command}")
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            error_text = result.stderr or result.stdout
            error_text = error_text[-3000:] if len(error_text) > 3000 else error_text

            print(f"❌ Comando falló. Analizando con IA...")
            analysis = send_to_huggingface(error_text)
            log_error("COMMAND", f"Command: {command}\n{error_text}", analysis)
            return {"success": False, "error": error_text, "analysis": analysis}
        else:
            print("✅ Comando exitoso!")
            return {"success": True, "output": result.stdout}
    except Exception as e:
        print(f"❌ Error ejecutando comando: {e}")
        return {"success": False, "error": str(e), "analysis": str(e)}


def analyze_error_text(error_text):
    """Analiza un texto de error directamente (sin ejecutar nada)."""
    print(f"🔍 Analizando error ({len(error_text)} chars)...")
    analysis = send_to_huggingface(error_text)
    log_error("MANUAL", error_text, analysis)
    return analysis


def log_error(source, error_text, analysis):
    """Registra el error y su análisis en un archivo JSON."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "source": source,
        "error_preview": error_text[:500],
        "analysis": analysis,
    }

    # Leer log existente
    log_data = []
    if ERROR_LOG.exists():
        try:
            log_data = json.loads(ERROR_LOG.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, Exception):
            log_data = []

    log_data.append(entry)

    # Mantener solo los últimos 50 registros
    if len(log_data) > 50:
        log_data = log_data[-50:]

    ERROR_LOG.write_text(json.dumps(log_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"💾 Análisis guardado en {ERROR_LOG}")


def interactive_analyzer():
    """Modo interactivo: pega un error y recibe la solución."""
    print("=" * 60)
    print("🤖 AURA ERROR ANALYZER — Modo Interactivo")
    print("=" * 60)
    print("Pega el texto del error (presiona Enter dos veces para analizar):")
    print()

    lines = []
    empty_count = 0
    while True:
        try:
            line = input()
            if line == "":
                empty_count += 1
                if empty_count >= 2:
                    break
                lines.append(line)
            else:
                empty_count = 0
                lines.append(line)
        except EOFError:
            break

    error_text = "\n".join(lines).strip()
    if not error_text:
        print("⚠️ No se proporcionó ningún error.")
        return

    analysis = analyze_error_text(error_text)
    print()
    print("=" * 60)
    print("📋 ANÁLISIS DEL MODELO QWEN:")
    print("=" * 60)
    print(analysis)
    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Modo batch: analizar un archivo de errores
        error_file = sys.argv[1]
        if os.path.exists(error_file):
            with open(error_file, "r", encoding="utf-8") as f:
                error_text = f.read()
            analysis = analyze_error_text(error_text)
            print(analysis)
        else:
            print(f"❌ Archivo no encontrado: {error_file}")
    else:
        # Modo interactivo
        interactive_analyzer()
