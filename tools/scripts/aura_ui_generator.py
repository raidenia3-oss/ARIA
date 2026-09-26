#!/usr/bin/env python3
"""
AURA UI Generator — Usa el modelo entrenado para generar interfaces web (HTML/CSS/JS)
y las conecta con las apps del PC vía api_puente.py o el servidor de modelo (serve_model.py).

El modelo puede:
  - Generar código HTML completo desde una descripción
  - Generar componentes CSS específicos
  - Generar código JavaScript para interactividad
  - Guardar interfaces generadas como archivos .html
  - Lanzar el navegador para previsualizar

Integración con infraestructura PC:
  - Si serve_model.py está corriendo (puerto 8001), usa su API OpenAI-compatible
  - Si api_puente.py está corriendo (puerto 5000), envía comandos para abrir navegador
  - Si el modelo está fine-tuneado localmente, carga y usa directamente

Uso:
  # Generar interfaz usando el servidor de modelo
  python scripts/aura_ui_generator.py --prompt "Crea un dashboard de monitoreo con tema cyberpunk"

  # Generar interfaz usando el modelo local directamente
  python scripts/aura_ui_generator.py --prompt "Crea una app móvil de chat" --local-model fine-tuned-ame/

  # Generar y abrir en navegador automáticamente
  python scripts/aura_ui_generator.py --prompt "..." --open

  # Servir como API para que la mobile app genere interfaces
  python scripts/aura_ui_generator.py --serve
"""

from __future__ import annotations

import os
import sys
import json
import time
import uuid
import argparse
import logging
import requests
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any, Tuple

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("AuraUIGenerator")

REPO_ROOT = Path(__file__).resolve().parent.parent
GENERATED_DIR = REPO_ROOT / "generated_interfaces"
GENERATED_DIR.mkdir(exist_ok=True)

DEFAULT_MODEL_API = "http://localhost:8001/v1/chat/completions"
DEFAULT_API_PUENTE = "http://localhost:5000/ejecutar"

UI_SYSTEM_PROMPT = """Eres AURA UI Generator, un especialista en crear interfaces web modernas y funcionales.

Instrucciones:
- Generas código HTML5 completo con CSS integrado y JavaScript funcional
- Usas temas modernos: cyberpunk (cyan/magenta/neón), dark professional, gradient, mobile-first
- Las interfaces son responsive, con tipografía monoespaciada y efectos visuales
- Siempre incluyes: <!DOCTYPE html>, <html>, <head> con <meta charset>, <title>, <style>, y <body>
- Los colores primarios típicos: #00d4ff (cian), #7b2ff7 (magenta), #00ff88 (verde)
- Fondos oscuros: #0a0a1a, #0d1117, #1a1a2e
- Usas CSS variables, flexbox, grid, transiciones y efectos de hover
- El JavaScript es inline y funcional (botones, toggle, animaciones simples)
- NO incluyes comentarios innecesarios ni explicaciones fuera del código

Responde SOLO con código HTML/CSS/JS válido, sin texto adicional."""


def call_model_api(prompt: str, model_path: str = None,
                   temperature: float = 0.7,
                   max_tokens: int = 2048,
                   stream: bool = False) -> str:
    """Llama al servidor de modelo (serve_model.py) para generación."""
    api_url = os.getenv("MODEL_API_URL", DEFAULT_MODEL_API)
    headers = {"Content-Type": "application/json"}

    messages = [
        {"role": "system", "content": UI_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    payload = {
        "model": model_path or os.getenv("MODEL_NAME", "aura-ui"),
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": stream,
    }

    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()

        if stream:
            return data.get("choices", [{}])[0].get("delta", {}).get("content", "")

        return data.get("choices", [{}])[0].get("message", {}).get("content", "")
    except requests.ConnectionError:
        logger.warning(f"Model API not reachable at {api_url}, falling back to local model")
        return ""
    except Exception as e:
        logger.error(f"Model API error: {e}")
        return ""


def call_local_model(prompt: str, model_path: str,
                     temperature: float = 0.7,
                     max_tokens: int = 2048) -> str:
    """Carga y usa el modelo fine-tuneado localmente."""
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM

    logger.info(f"Loading local model: {model_path}")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=torch.float16 if device.type == "cuda" else torch.float32,
        device_map="auto",
        trust_remote_code=True,
    )
    model.eval()

    prompt_full = f"User: {prompt}\nAssistant: "
    inputs = tokenizer(prompt_full, return_tensors="pt", truncation=True, max_length=2048)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            temperature=temperature,
            do_sample=True,
            pad_token_id=tokenizer.pad_token_id,
        )

    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    # Strip the prompt
    response = response.replace(prompt_full, "").strip()
    return response


def generate_ui(prompt: str, model_path: str = None,
                temperature: float = 0.7, max_tokens: int = 2048) -> str:
    """Genera código HTML usando el modelo (API o local)."""
    # Intentar API primero, luego modelo local
    html = call_model_api(prompt, temperature=temperature, max_tokens=max_tokens)

    if not html and model_path:
        html = call_local_model(prompt, model_path, temperature=temperature, max_tokens=max_tokens)

    if not html:
        logger.warning("No model available — generando template base")
        html = generate_template_fallback(prompt)

    return html


def generate_template_fallback(prompt: str) -> str:
    """Template básico cuando no hay modelo disponible."""
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>AURA Generated — {prompt[:50]}</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{{background:#0a0a1a;color:#e0e0e0;font-family:monospace;min-height:100vh;padding:2rem}}
.container{{max-width:640px;margin:0 auto}}
h1{{background:linear-gradient(135deg,#00d4ff,#7b2ff7);-webkit-background-clip:text;-webkit-text-fill-color:transparent;font-size:2rem}}
.card{{background:#12122a;border:1px solid #2a2a4e;border-radius:16px;padding:1.5rem;margin:1rem 0}}
p{{line-height:1.6;color:#aaa}}
</style>
</head>
<body>
<div class="container">
<h1>AURA UI Generator</h1>
<div class="card">
<h2>Prompt: {prompt[:80]}</h2>
<p>Generated interface placeholder. Conecta con el servidor de modelo en puerto 8001 para generacion completa.</p>
</div>
</div>
</body>
</html>
"""


def clean_html_response(html: str) -> str:
    """Limpia la respuesta del modelo para asegurar HTML válido."""
    # Strip markdown code fences if present
    html = html.strip()
    if html.startswith("```html"):
        html = html[7:]
    elif html.startswith("```"):
        html = html[3:]
    if html.endswith("```"):
        html = html[:-3]
    html = html.strip()

    # Ensure it starts with <!DOCTYPE or <html
    if not html.lower().startswith("<!doctype") and not html.lower().startswith("<html"):
        html = "<!DOCTYPE html>\n" + html

    return html


def save_interface(prompt: str, html: str, title: str = None) -> Path:
    """Guarda la interfaz generada como archivo .html."""
    safe_title = title or f"interface-{uuid.uuid4().hex[:8]}"
    safe_title = re.sub(r"[^a-zA-Z0-9_-]", "_", safe_title)

    filename = f"{safe_title}.html"
    filepath = GENERATED_DIR / filename

    # Agregar metadata
    metadata = f"<!-- Generated by AURA UI Generator on {datetime.now().isoformat()}\nPrompt: {prompt}\n-->\n"

    content = metadata + html
    filepath.write_text(content, encoding="utf-8")
    logger.info(f"Interface saved: {filepath}")
    return filepath


def open_in_browser(filepath: Path) -> bool:
    """Abre la interfaz generada en el navegador del PC vía api_puente.py."""
    api_puente_url = os.getenv("API_PUENTE_URL", DEFAULT_API_PUENTE)

    try:
        # Try api_puente.py first
        cmd = f"start chrome {filepath}"
        response = requests.post(
            api_puente_url,
            data={"comando": cmd},
            timeout=5,
        )
        if response.status_code == 200:
            logger.info(f"Opened via api_puente.py: {response.text[:100]}")
            return True
    except Exception:
        pass

    # Fallback: abrir directamente
    try:
        if sys.platform == "win32":
            os.startfile(str(filepath))
        else:
            subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", str(filepath)])
        logger.info(f"Opened browser directly: {filepath}")
        return True
    except Exception as e:
        logger.error(f"Failed to open browser: {e}")
        return False


def get_existing_interfaces() -> List[Dict[str, Any]]:
    """Lista las interfaces generadas previamente."""
    interfaces = []
    for f in sorted(GENERATED_DIR.glob("*.html")):
        interfaces.append({
            "name": f.stem,
            "path": str(f.relative_to(REPO_ROOT)),
            "size": f.stat().st_size,
            "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
        })
    return interfaces


def create_app_from_template(template_path: Path, customizations: Dict[str, Any] = None) -> Path:
    """Crea una app a partir de una plantilla existente con personalizaciones."""
    content = template_path.read_text(encoding="utf-8")

    if customizations:
        replacements = customizations.get("replacements", {})
        for old, new in replacements.items():
            content = content.replace(old, new)

    new_name = customizations.get("name", f"customized-{template_path.stem}")
    new_path = save_interface(f"Customized from {template_path.stem}", content, new_name)
    return new_path


import re


def run_cli():
    parser = argparse.ArgumentParser(description="AURA UI Generator")
    parser.add_argument("--prompt", "-p", type=str, required=False,
                        help="Descripción de la interfaz a generar")
    parser.add_argument("--model", "-m", type=str, default=None,
                        help="Ruta del modelo local (fine-tuneado) o usar API")
    parser.add_argument("--temperature", "-t", type=float, default=0.7,
                        help="Temperatura de generación")
    parser.add_argument("--max-tokens", type=int, default=2048,
                        help="Tokens máximos de salida")
    parser.add_argument("--open", action="store_true",
                        help="Abrir en navegador después de generar")
    parser.add_argument("--serve", action="store_true",
                        help="Iniciar servidor API para generación de interfaces")
    parser.add_argument("--list", action="store_true",
                        help="Listar interfaces generadas")
    parser.add_argument("--from-template", type=str, default=None,
                        help="Crear interfaz a partir de plantilla existente")
    args = parser.parse_args()

    if args.list:
        interfaces = get_existing_interfaces()
        print(f"\n{'Name':<30} {'Size':>8} {'Modified'}")
        print("-" * 70)
        for iface in interfaces:
            print(f"{iface['name']:<30} {iface['size']:>8}  {iface['modified']}")
        return

    if args.serve:
        from flask import Flask, request, jsonify

        app = Flask(__name__)

        @app.route("/generate", methods=["POST"])
        def api_generate():
            data = request.json
            prompt = data.get("prompt", "")
            temperature = data.get("temperature", 0.7)
            max_tokens = data.get("max_tokens", 2048)

            html = generate_ui(prompt, args.model, temperature, max_tokens)
            html = clean_html_response(html)

            save_path = save_interface(prompt, html)
            return jsonify({
                "html": html,
                "file": str(save_path.relative_to(REPO_ROOT)),
                "filename": save_path.name,
            })

        @app.route("/list", methods=["GET"])
        def api_list():
            interfaces = get_existing_interfaces()
            return jsonify({"interfaces": interfaces})

        @app.route("/health", methods=["GET"])
        def health():
            return jsonify({"status": "ok", "service": "aura-ui-generator"})

        print("AURA UI Generator API server on :8002")
        print("  POST /generate  — {prompt, temperature, max_tokens}")
        print("  GET  /list      — list generated interfaces")
        print("  GET  /health    — health check")
        app.run(host="0.0.0.0", port=8002)
        return

    if args.from_template:
        template_path = REPO_ROOT / args.from_template
        if not template_path.exists():
            logger.error(f"Template not found: {template_path}")
            sys.exit(1)

        new_path = create_app_from_template(template_path)
        print(f"Created from template: {new_path}")
        if args.open:
            open_in_browser(new_path)
        return

    if not args.prompt:
        print("Specify --prompt or --list or --serve")
        sys.exit(1)

    logger.info(f"Generating UI for: {args.prompt}")
    html = generate_ui(args.prompt, args.model, args.temperature, args.max_tokens)
    html = clean_html_response(html)

    # Determinar título desde el prompt
    title = args.prompt[:40].replace(" ", "_")
    save_path = save_interface(args.prompt, html, title)

    print(f"\n{'='*50}")
    print(f"  UI GENERATED")
    print(f"{'='*50}")
    print(f"  Prompt:  {args.prompt}")
    print(f"  File:    {save_path}")
    print(f"  Size:    {len(html)} chars")
    print(f"{'='*50}")

    if args.open:
        open_in_browser(save_path)


if __name__ == "__main__":
    run_cli()
