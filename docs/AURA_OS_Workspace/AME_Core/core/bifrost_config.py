#!/usr/bin/env python3
"""
Bifrost Gateway — Configuración y Gestión del Gateway Antilímites
===================================================================
FASE 3: Infraestructura de Agentes de Código y Gateway Antilímites.

Este módulo configura Bifrost Gateway (http://localhost:880) con una
cadena de fallback jerárquica para evadir Rate Limits:

Cadena de Contingencia:
  1. Cerebras (Inferencia sub-segundo, GLM 4.7 / GPT OSS 120B)
  2. Groq (Llama 4 Scout 17B / Llama 70B)
  3. OpenRouter (Modelos comunitarios gratuitos)

Los agentes CLI (claude-code, gemini-cli, open-code) apuntan a localhost:880
"""

import os
import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# ─── Constantes ───
BIFROST_PORT = 880
BIFROST_URL = f"http://localhost:{BIFROST_PORT}"
BIFROST_CONFIG_DIR = Path.home() / ".bifrost"
BIFROST_CONFIG_FILE = BIFROST_CONFIG_DIR / "config.json"
BIFROST_ROUTES_FILE = BIFROST_CONFIG_DIR / "routes.json"

# Rutas de los binarios de agentes
AGENT_PATHS = {
    "claude-code": ["claude-code", "npx", "-y", "@anthropic-ai/claude-code"],
    "gemini-cli": ["gemini", "npx", "-y", "@google/gemini-cli"],
    "open-code": ["open-code", "npx", "-y", "open-code"],
}

# ─── CONFIGURACIÓN DEL GATEWAY ─────────────────────────────────

BIFROST_CONFIG_TEMPLATE = {
    "version": "1.0",
    "gateway": {
        "host": "0.0.0.0",
        "port": BIFROST_PORT,
        "log_level": "info",
    },
    "providers": {
        "cerebras": {
            "base_url": "https://api.cerebras.ai/v1",
            "api_key": os.getenv("CEREBRAS_API_KEY", ""),
            "models": ["glm-4", "gpt-oss-120b"],
            "priority": 1,
            "timeout": 30,
            "retry_count": 2,
        },
        "groq": {
            "base_url": "https://api.groq.com/openai/v1",
            "api_key": os.getenv("GROQ_API_KEY", ""),
            "models": ["llama-4-scout-17b", "llama-3.3-70b-versatile"],
            "priority": 2,
            "timeout": 45,
            "retry_count": 2,
        },
        "openrouter": {
            "base_url": "https://openrouter.ai/api/v1",
            "api_key": os.getenv("OPENROUTER_API_KEY", ""),
            "models": ["meta-llama/llama-3-8b-instruct:free", "gemma-2-2b-it:free"],
            "priority": 3,
            "timeout": 60,
            "retry_count": 1,
        },
    },
    "fallback": {
        "strategy": "chain",  # chain = probar en orden de prioridad
        "on_status_codes": [400, 401, 402, 403, 429, 500, 502, 503],
        "on_timeout": True,
        "on_empty_response": True,
        "health_check_interval": 30,  # segundos
    },
    "routing": {
        "default_provider": "cerebras",
        "model_mapping": {
            "claude-*": ["cerebras", "groq"],
            "gemini-*": ["groq", "openrouter"],
            "gpt-*": ["cerebras", "groq", "openrouter"],
            "llama-*": ["groq", "openrouter"],
            "default": ["cerebras", "groq", "openrouter"],
        },
    },
    "rate_limiting": {
        "enabled": True,
        "max_requests_per_minute": 30,
        "max_tokens_per_minute": 100000,
        "cooldown_after_error": 10,  # segundos
    },
}

# ─── RUTAS PARA AGENTES CLI ─────────────────────────────────────

BIFROST_ROUTES_TEMPLATE = {
    "routes": [
        {
            "name": "claude-code",
            "path_prefix": "/v1",
            "target": BIFROST_URL,
            "headers": {
                "X-Aura-Proxy": "bifrost",
                "X-Provider": "auto",
            },
        },
        {
            "name": "gemini-cli",
            "path_prefix": "/v1",
            "target": BIFROST_URL,
            "headers": {
                "X-Aura-Proxy": "bifrost",
                "X-Provider": "auto",
            },
        },
        {
            "name": "open-code",
            "path_prefix": "/v1",
            "target": BIFROST_URL,
            "headers": {
                "X-Aura-Proxy": "bifrost",
                "X-Provider": "auto",
            },
        },
    ]
}


# ─── FUNCIONES DE GESTIÓN ──────────────────────────────────────


def ensure_config_dir():
    """Crear directorio de configuración de Bifrost si no existe."""
    BIFROST_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Directorio Bifrost: {BIFROST_CONFIG_DIR}")


def write_config():
    """Escribir archivo de configuración de Bifrost."""
    ensure_config_dir()

    # Actualizar API keys desde entorno
    config = BIFROST_CONFIG_TEMPLATE.copy()
    config["providers"]["cerebras"]["api_key"] = os.getenv("CEREBRAS_API_KEY", "")
    config["providers"]["groq"]["api_key"] = os.getenv("GROQ_API_KEY", "")
    config["providers"]["openrouter"]["api_key"] = os.getenv("OPENROUTER_API_KEY", "")

    with open(BIFROST_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    logger.info(f"Configuración escrita: {BIFROST_CONFIG_FILE}")
    return config


def write_routes():
    """Escribir archivo de rutas para los agentes CLI."""
    ensure_config_dir()
    with open(BIFROST_ROUTES_FILE, "w", encoding="utf-8") as f:
        json.dump(BIFROST_ROUTES_TEMPLATE, f, indent=2)
    logger.info(f"Rutas escritas: {BIFROST_ROUTES_FILE}")


def load_config() -> Dict[str, Any]:
    """Cargar configuración actual de Bifrost."""
    if BIFROST_CONFIG_FILE.exists():
        with open(BIFROST_CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return write_config()


def load_routes() -> Dict[str, Any]:
    """Cargar rutas actuales."""
    if BIFROST_ROUTES_FILE.exists():
        with open(BIFROST_ROUTES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return BIFROST_ROUTES_TEMPLATE


def check_bifrost_health() -> Dict[str, Any]:
    """Verificar si Bifrost Gateway está corriendo y saludable."""
    try:
        import httpx
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_async_check_health())
        loop.close()
        return result
    except Exception as e:
        return {"status": "not_installed", "detail": str(e)[:200]}


async def _async_check_health() -> Dict[str, Any]:
    """Verificación asíncrona de salud."""
    try:
        import httpx

        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{BIFROST_URL}/health", timeout=5)
            if resp.status_code == 200:
                return {"status": "running", "port": BIFROST_URL, "data": resp.json()}
            return {"status": "error", "code": resp.status_code}
    except Exception as e:
        return {"status": "not_running", "detail": str(e)[:200]}


def get_agent_env_vars() -> Dict[str, str]:
    """
    Obtener variables de entorno necesarias para que los agentes CLI
    apunten al gateway local en lugar de los servidores oficiales.

    Los agentes deben configurarse con:
      ANTHROPIC_BASE_URL=http://localhost:880
      GEMINI_API_BASE=http://localhost:880
      OPENAI_BASE_URL=http://localhost:880
    """
    return {
        # Claude Code
        "ANTHROPIC_BASE_URL": BIFROST_URL if os.getenv("ANTHROPIC_API_KEY") else "",
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY", "dummy-key-for-local-proxy"),
        # Gemini CLI
        "GEMINI_API_BASE": BIFROST_URL,
        "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", "dummy-key-for-local-proxy"),
        # Open Code (OpenAI-compatible)
        "OPENAI_BASE_URL": f"{BIFROST_URL}/v1",
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", "dummy-key-for-local-proxy"),
    }


def get_fallback_chain_summary() -> List[Dict[str, Any]]:
    """Obtener resumen de la cadena de fallback configurada."""
    config = load_config()
    providers = config.get("providers", {})
    chain = []

    # Ordenar por prioridad
    sorted_providers = sorted(providers.items(), key=lambda x: x[1].get("priority", 999))

    for name, settings in sorted_providers:
        chain.append(
            {
                "name": name,
                "models": settings.get("models", []),
                "priority": settings.get("priority"),
                "configured": bool(settings.get("api_key")),
                "url": settings.get("base_url"),
            }
        )

    return chain


def install_bifrost_via_npm() -> Dict[str, Any]:
    """Instalar Bifrost Gateway globalmente mediante npm."""
    try:
        result = subprocess.run(
            ["npm", "install", "-g", "@bifrost/gateway"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            logger.info("Bifrost Gateway instalado globalmente")
            write_config()
            write_routes()
            return {"status": "ok", "detail": "Instalación completada"}
        else:
            return {"status": "error", "detail": result.stderr[:500]}
    except FileNotFoundError:
        return {
            "status": "error",
            "detail": "npm no encontrado. Instala Node.js desde https://nodejs.org",
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)[:300]}


def install_agent_clis() -> Dict[str, List[Dict[str, Any]]]:
    """Instalar CLIs de agentes de código globalmente."""
    results = []
    for agent_name in ["claude-code", "gemini-cli", "open-code"]:
        try:
            result = subprocess.run(
                ["npm", "install", "-g", f"@{agent_name.replace('-', '/')}"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                results.append(
                    {
                        "agent": agent_name,
                        "status": "installed",
                        "command": agent_name,
                    }
                )
            else:
                results.append(
                    {
                        "agent": agent_name,
                        "status": "error",
                        "detail": result.stderr[:200],
                    }
                )
        except Exception as e:
            results.append(
                {
                    "agent": agent_name,
                    "status": "error",
                    "detail": str(e)[:200],
                }
            )

    return {"install_results": results}


# ─── CONFIGURACIÓN DEL ENTORNO ─────────────────────────────────


def generate_env_block() -> str:
    """Generar bloque de configuración para .env."""
    blocks = []
    blocks.append("# ============================================")
    blocks.append("# BIFROST GATEWAY — PROVEEDORES ANTILÍMITES")
    blocks.append("# ============================================")
    blocks.append("CEREBRAS_API_KEY=                          # https://cloud.cerebras.ai/")
    blocks.append("GROQ_API_KEY=                              # https://console.groq.com/keys")
    blocks.append("OPENROUTER_API_KEY=                        # Ya existe arriba")
    blocks.append("")
    blocks.append("# ============================================")
    blocks.append("# AGENTES DE CÓDIGO (CLI) — APUNTAN A GATEWAY LOCAL")
    blocks.append("# ============================================")
    blocks.append("ANTHROPIC_API_KEY=dummy-key-for-local-proxy")
    blocks.append("ANTHROPIC_BASE_URL=http://localhost:880")
    blocks.append("GEMINI_API_BASE=http://localhost:880")
    blocks.append("OPENAI_BASE_URL=http://localhost:880/v1")
    blocks.append("OPENAI_API_KEY=dummy-key-for-local-proxy")
    blocks.append("")
    blocks.append("# ============================================")
    blocks.append("# BIFROST GATEWAY — CONFIGURACIÓN DEL ROUTER")
    blocks.append("# ============================================")
    blocks.append("BIFROST_PORT=880")
    blocks.append("BIFROST_LOG_LEVEL=info")

    return "\n".join(blocks)


# ─── INIT ──────────────────────────────────────────────────────


def init_bifrost():
    """Inicializar toda la configuración de Bifrost."""
    ensure_config_dir()
    config = write_config()
    routes = write_routes()

    summary = get_fallback_chain_summary()
    print(f"\n{'='*55}")
    print("   🌉 BIFROST GATEWAY — CONFIGURACIÓN COMPLETA")
    print(f"{'='*55}")
    print(f"\n  Puerto: {BIFROST_PORT}")
    print(f"  Config: {BIFROST_CONFIG_FILE}")
    print(f"  Rutas:  {BIFROST_ROUTES_FILE}")
    print(f"\n  Cadena de Fallback:")
    for p in summary:
        icon = "✅" if p["configured"] else "❌"
        print(f"    {icon} {p['name']:12s} → {', '.join(p['models'])}")

    print(f"\n  Agentes CLI configurados para localhost:880:")
    for agent, cmd in AGENT_PATHS.items():
        print(f"    • {agent:15s} → {cmd[0]}")

    print(f"\n  Variables de entorno generadas (para .env):")
    print(f"    {generate_env_block()}")
    print()

    return config


if __name__ == "__main__":
    init_bifrost()
