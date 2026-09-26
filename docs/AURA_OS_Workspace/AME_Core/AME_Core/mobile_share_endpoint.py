"""
mobile_share_endpoint.py — Endpoint unificado para archivos compartidos desde Android Share Target.

Recibe archivos (PDF, TXT, JPG/PNG) desde el frontend mobile vía file_handler.js,
los guarda en vision_pool / knowledge_base, y los envía al Cortex (Shadow-Core)
para análisis RAG o de Visión.

Flujo:
  Android Share → ShareTargetHandler.java → file_handler.js → POST /api/mobile/share/analyze → este endpoint
"""

import os
import sys
import json
import time
import base64
import logging
import tempfile
from datetime import datetime
from pathlib import Path
from flask import request, jsonify

try:
    import requests
except ImportError:
    requests = None

logger = logging.getLogger('ame_server')

# ─── Config ────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
VISION_POOL_DIR = BASE_DIR / 'vision_pool'
KNOWLEDGE_DIR = BASE_DIR / 'knowledge_base' / 'shared_files'
SHADOW_CORE_URL = 'http://localhost:5001'  # Shadow-Core default port
CORTEX_ANALYZE_URL = f'{SHADOW_CORE_URL}/api/analyze'

# ─── Asegurar directorios ──────────────────────────────────────────────────
def ensure_directories():
    """Crea los directorios necesarios si no existen."""
    VISION_POOL_DIR.mkdir(parents=True, exist_ok=True)
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)


# ─── Análisis vía Shadow-Core / Ollama ─────────────────────────────────────
def analyze_with_ollama(prompt, model='dolphin-llama3'):
    """Envía un prompt a Ollama para obtener análisis."""
    if not requests:
        return {"error": "requests module not available"}

    try:
        url = "http://localhost:11434/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 1024}
        }
        resp = requests.post(url, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        return {"response": data.get("response", ""), "model": model}
    except requests.exceptions.ConnectionError:
        logger.warning("⚠️  Ollama no disponible en localhost:11434")
        return {"error": "Ollama no disponible"}
    except Exception as e:
        logger.error(f"❌ Error en Ollama: {e}")
        return {"error": str(e)}


def save_shared_file(content, file_name, mime_type):
    """
    Guarda el archivo compartido en el sistema de archivos.
    Para imágenes y PDFs (base64) decodifica y guarda en vision_pool.
    Para texto plano guarda en knowledge_base/shared_files.
    """
    ensure_directories()
    timestamp = int(time.time())
    safe_name = f"{timestamp}_{file_name}"

    if mime_type and mime_type.startswith('text/'):
        # Texto plano → knowledge_base
        file_path = KNOWLEDGE_DIR / safe_name
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f"📝 Texto guardado: {file_path}")
        return {
            "path": str(file_path),
            "type": "text",
            "size": len(content)
        }

    else:
        # Base64 (PDF o imagen) → decodificar y guardar en vision_pool
        try:
            # Limpiar prefijo data:image/...;base64, si existe
            if content.startswith('data:'):
                content = content.split(',', 1)[1]

            file_bytes = base64.b64decode(content)
            file_path = VISION_POOL_DIR / safe_name
            with open(file_path, 'wb') as f:
                f.write(file_bytes)
            logger.info(f"📦 Archivo binario guardado: {file_path} ({len(file_bytes)} bytes)")
            return {
                "path": str(file_path),
                "type": "binary",
                "size": len(file_bytes)
            }
        except Exception as e:
            logger.error(f"❌ Error decodificando base64: {e}")
            return {"error": str(e)}


def analyze_shared_file(payload):
    """
    Analiza el archivo recibido según su tipo:
      - text    → análisis de texto vía Ollama
      - image   → guardar en vision_pool para Vision Engine
      - pdf     → guardar para RAG, extraer texto si es posible
    """
    file_name = payload.get('fileName', 'unknown')
    mime_type = payload.get('mimeType', 'application/octet-stream')
    content = payload.get('content', '')
    analysis_mode = payload.get('analysis_mode', 'text')

    # 1. Guardar el archivo
    saved = save_shared_file(content, file_name, mime_type)
    if 'error' in saved:
        return {
            "status": "error",
            "message": saved['error'],
            "fileName": file_name
        }

    # 2. Analizar según modo
    result = {
        "status": "ok",
        "fileName": file_name,
        "mimeType": mime_type,
        "saved_at": saved.get('path'),
        "size": saved.get('size', 0),
        "timestamp": datetime.utcnow().isoformat() + 'Z',
        "analysis": {},
        "summary": ""
    }

    if analysis_mode == 'text':
        # Análisis de texto vía Ollama
        truncated = content[:8000] if len(content) > 8000 else content
        prompt = f"""Resume y analiza el siguiente texto. Extrae:
1. Tema principal (máx. 10 palabras)
2. Puntos clave (máx. 3)
3. Si contiene datos sensibles o información de seguridad

TEXTO:
{truncated}

Responde en español, formato conciso."""
        llm_result = analyze_with_ollama(prompt)
        result['analysis']['mode'] = 'text'
        result['analysis']['llm'] = llm_result
        result['summary'] = llm_result.get('response', '')[:500] if 'response' in llm_result else 'Texto recibido y almacenado.'

    elif analysis_mode == 'vision':
        # Imagen → guardar en vision_pool, devolver info
        result['analysis']['mode'] = 'vision'
        result['analysis']['ready_for_vision'] = True
        result['analysis']['pool_path'] = saved.get('path', '')
        result['summary'] = f"Imagen recibida y almacenada en pool de visión: {file_name}"

        # Intentar análisis con Ollama vision si tiene capacidad
        try:
            img_prompt = f"Describe brevemente el contenido de esta imagen. Archivo: {file_name}. Extrae texto visible y contexto."
            llm_result = analyze_with_ollama(img_prompt)
            if 'response' in llm_result:
                result['analysis']['vision_llm'] = llm_result['response'][:500]
        except:
            pass

    elif analysis_mode == 'rag':
        # PDF → guardado para RAG
        result['analysis']['mode'] = 'rag'
        result['analysis']['document_path'] = saved.get('path', '')
        result['analysis']['ready_for_rag'] = True
        result['summary'] = f"Documento PDF recibido y almacenado para análisis RAG: {file_name}"

        # Extraer texto del PDF si es posible (fallback a metadatos)
        try:
            content_preview = content[:200] if len(content) > 200 else content
            prompt = f"""Analiza el nombre de archivo y contexto de este PDF:
Nombre: {file_name}
Contenido (base64) tamaño: {len(content)} chars
Previsualización de contenido: {content_preview[:100]}

Proporciona una clasificación del documento y posibles temas de análisis.
Responde en español, conciso."""
            llm_result = analyze_with_ollama(prompt)
            if 'response' in llm_result:
                result['analysis']['classification'] = llm_result['response'][:300]
        except:
            pass

    else:
        result['analysis']['mode'] = 'unknown'
        result['summary'] = f"Archivo recibido: {file_name} ({mime_type})"

    # 3. Injectar alerta en ticker
    try:
        _inject_ticker_alert_safe(
            "info",
            f"📤 Android Share: {file_name} ({saved.get('size', 0)} bytes) — {result['summary'][:60]}",
            "mobile_share"
        )
    except Exception as e:
        logger.warning(f"⚠️  No se pudo inyectar alerta ticker: {e}")

    return result


def _inject_ticker_alert_safe(alert_type, message, source="mobile_share"):
    """Inyecta alerta en el ticker global del servidor."""
    try:
        ticker_path = BASE_DIR / 'AME_Core' / 'alerts.json'
        if ticker_path.exists():
            with open(ticker_path, 'r', encoding='utf-8') as f:
                alerts = json.load(f)
        else:
            alerts = []

        alerts.append({
            "type": alert_type,
            "message": message,
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S'),
            "source": source
        })

        # Mantener máximo 100
        if len(alerts) > 100:
            alerts = alerts[-100:]

        with open(ticker_path, 'w', encoding='utf-8') as f:
            json.dump(alerts, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"⚠️  Error inyectando alerta ticker: {e}")


# ─── Registro del endpoint en Flask ────────────────────────────────────────
def register_mobile_share_endpoint(app):
    """
    Registra los endpoints relacionados con Android Share Target en la app Flask.

    Endpoints:
      POST /api/mobile/share/analyze → Recibe archivos compartidos y los analiza
      GET  /api/mobile/share/status   → Estado del módulo de share
    """

    @app.route('/api/mobile/share/analyze', methods=['POST'])
    def api_mobile_share_analyze():
        """
        Endpoint principal para recibir archivos compartidos desde Android.
        Body JSON con la estructura:
        {
            "fileName": "documento.pdf",
            "mimeType": "application/pdf",
            "type": "pdf|image|text",
            "content": "base64_string_or_text",
            "analysis_mode": "rag|vision|text",
            "timestamp": 1234567890,
            "source": "android_share_target",
            "device": "Mozilla/5.0 ..."
        }
        """
        try:
            data = request.get_json(force=True)

            if not data:
                return jsonify({
                    "status": "error",
                    "message": "Body JSON requerido"
                }), 400

            # Validar campos mínimos
            if not data.get('fileName') or not data.get('content'):
                return jsonify({
                    "status": "error",
                    "message": "Campos requeridos: fileName, content"
                }), 400

            logger.info(f"📱 Android Share recibido: {data.get('fileName')} ({data.get('mimeType')})")

            # Procesar y analizar
            result = analyze_shared_file(data)

            # Logging
            log_msg = f"Share analyzed: {result.get('fileName')} — {result.get('summary', '')[:100]}"
            logger.info(f"✅ {log_msg}")

            return jsonify(result)

        except Exception as e:
            logger.error(f"❌ Error en mobile share analyze: {e}")
            return jsonify({
                "status": "error",
                "message": f"Error interno: {str(e)}"
            }), 500

    @app.route('/api/mobile/share/status', methods=['GET'])
    def api_mobile_share_status():
        """
        Estado del módulo de Android Share Target.
        """
        ensure_directories()
        vision_count = len(list(VISION_POOL_DIR.glob('*'))) if VISION_POOL_DIR.exists() else 0
        knowledge_count = len(list(KNOWLEDGE_DIR.glob('*'))) if KNOWLEDGE_DIR.exists() else 0

        return jsonify({
            "status": "ok",
            "module": "native_share_target",
            "active": True,
            "vision_pool_files": vision_count,
            "knowledge_shared_files": knowledge_count,
            "supported_types": [
                "application/pdf",
                "text/plain",
                "text/html",
                "image/jpeg",
                "image/png"
            ],
            "endpoint": "/api/mobile/share/analyze",
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S')
        })

    logger.info("✅ Módulo Native Share Target registrado en servidor Flask")
    return app