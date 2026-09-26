"""
ai_router.py - Alternancia entre IA local (Ollama/LM Studio) y nube (Google Gemini)
"""

import os
import json
import requests
from typing import Dict, Any, Optional
import random

# Configuración
AI_PROVIDERS = {
    "local": {
        "enabled": True,
        "model": "llama3",
        "endpoint": "http://localhost:11434/api/generate",
        "timeout": 10
    },
    "gemini": {
        "enabled": True,
        "api_key": os.environ.get("GEMINI_API_KEY", ""),
        "endpoint": "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5:generateContent",
        "timeout": 15
    }
}

class AIProvider:
    """
    Clase base para proveedores de IA.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = config.get("name", "unknown")

    def generate(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        Genera una respuesta usando el proveedor de IA.
        """
        raise NotImplementedError("Método abstracto")

    def is_available(self) -> bool:
        """
        Verifica si el proveedor está disponible.
        """
        return self.config.get("enabled", False)

class LocalAIProvider(AIProvider):
    """
    Proveedor de IA local (Ollama/LM Studio).
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.name = "local"

    def generate(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        Genera una respuesta usando el endpoint local.
        """
        if not self.is_available():
            return {"error": "Local AI provider not enabled"}

        try:
            headers = {"Content-Type": "application/json"}
            payload = {
                "model": self.config.get("model", "llama3"),
                "prompt": prompt,
                "stream": False
            }

            response = requests.post(
                self.config["endpoint"],
                json=payload,
                headers=headers,
                timeout=self.config.get("timeout", 10)
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    "provider": "local",
                    "response": data.get("response", ""),
                    "model": data.get("model", ""),
                    "status": "success"
                }
            else:
                return {
                    "provider": "local",
                    "error": f"Error {response.status_code}: {response.text}",
                    "status": "failed"
                }

        except Exception as e:
            return {
                "provider": "local",
                "error": f"Exception: {str(e)}",
                "status": "failed"
            }

class GeminiAIProvider(AIProvider):
    """
    Proveedor de IA en la nube (Google Gemini).
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.name = "gemini"

    def generate(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        Genera una respuesta usando Google Gemini.
        """
        if not self.is_available():
            return {"error": "Gemini provider not enabled"}

        if not self.config.get("api_key"):
            return {"error": "Gemini API key not configured"}

        try:
            api_key = self.config.get("api_key", "")
            endpoint = self.config["endpoint"]
            url = f"{endpoint}?key={api_key}" if api_key else endpoint
            headers = {"Content-Type": "application/json"}

            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": prompt}
                        ]
                    }
                ]
            }

            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=self.config.get("timeout", 15)
            )

            if response.status_code == 200:
                data = response.json()
                if "candidates" in data and len(data["candidates"]) > 0:
                    candidate = data["candidates"][0]
                    if "content" in candidate and "parts" in candidate["content"]:
                        text = candidate["content"]["parts"][0].get("text", "")
                        return {
                            "provider": "gemini",
                            "response": text,
                            "status": "success"
                        }

            return {
                "provider": "gemini",
                "error": f"Unexpected response: {response.text}",
                "status": "failed"
            }

        except Exception as e:
            return {
                "provider": "gemini",
                "error": f"Exception: {str(e)}",
                "status": "failed"
            }

class AIRouter:
    """
    Router de IA que alterna entre proveedores locales y en la nube.
    """

    def __init__(self):
        self.providers = {
            "local": LocalAIProvider(AI_PROVIDERS["local"]),
            "gemini": GeminiAIProvider(AI_PROVIDERS["gemini"])
        }

    def get_available_providers(self) -> list:
        """
        Obtiene los proveedores disponibles.
        """
        return [name for name, provider in self.providers.items() if provider.is_available()]

    def select_provider(self, prompt: str) -> str:
        """
        Selecciona un proveedor basado en el tipo de tarea.
        """
        available = self.get_available_providers()

        if not available:
            return "none"

        # Priorizar local para tareas sensibles o de baja latencia
        if "local" in available and any(keyword in prompt.lower() for keyword in ["privado", "seguro", "local", "offline"]):
            return "local"

        # Priorizar Gemini para tareas complejas o que requieren contexto amplio
        if "gemini" in available and any(keyword in prompt.lower() for keyword in ["complejo", "análisis", "contexto", "amplio"]):
            return "gemini"

        # Alternar aleatoriamente si ambos están disponibles
        if len(available) > 1:
            return random.choice(available)

        return available[0]

    def generate(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        Genera una respuesta usando el proveedor seleccionado.
        """
        provider_name = self.select_provider(prompt)
        provider = self.providers.get(provider_name)

        if not provider or not provider.is_available():
            return {
                "error": f"No provider available (selected: {provider_name})",
                "status": "failed"
            }

        print(f"🤖 Usando {provider_name.upper()} AI: '{prompt[:30]}...'")

        return provider.generate(prompt, **kwargs)

    def test_connection(self) -> Dict[str, Any]:
        """
        Prueba la conexión con todos los proveedores disponibles.
        """
        results = {}

        for name, provider in self.providers.items():
            if provider.is_available():
                try:
                    test_prompt = f"Test de conexión para {name.upper()} AI"
                    result = provider.generate(test_prompt, timeout=5)
                    results[name] = {
                        "available": True,
                        "status": result.get("status", "unknown"),
                        "error": result.get("error", None)
                    }
                except Exception as e:
                    results[name] = {
                        "available": False,
                        "error": str(e)
                    }
            else:
                results[name] = {
                    "available": False,
                    "error": "Provider not enabled"
                }

        return results

def ask_ai(prompt: str, **kwargs) -> Dict[str, Any]:
    """
    Función principal para consultar IA.
    """
    router = AIRouter()
    return router.generate(prompt, **kwargs)

if __name__ == "__main__":
    print("""
    🤖 AI ROUTER MODULE
    ===================
    """)

    router = AIRouter()

    print("\n🔍 Proveyendo información de conexión:")
    connection_test = router.test_connection()
    for provider, status in connection_test.items():
        print(f"   {provider.upper()}: {'✅' if status['available'] else '❌'} {status.get('error', '')}")

    while True:
        prompt = input("\n💬 ¿Qué necesitas generar con IA? (o 'salir' para terminar): ").strip()

        if prompt.lower() in ('salir', 'exit', 'quit'):
            break

        if not prompt:
            print("⚠️ Por favor ingresa una pregunta.")
            continue

        print("\n🤖 Generando respuesta...")
        result = ask_ai(prompt)

        if "error" in result:
            print(f"❌ Error: {result['error']}")
        else:
            print(f"\n📌 Respuesta de {result['provider'].upper()} AI:")
            print(f"   {result['response'][:500]}...")  # Mostrar solo los primeros 500 caracteres