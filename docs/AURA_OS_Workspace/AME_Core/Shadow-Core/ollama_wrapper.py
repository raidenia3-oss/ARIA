"""
Wrapper para interactuar con Ollama y soportar streaming de respuestas.
"""

import asyncio
import json
import aiohttp
import logging

class OllamaWrapper:
    def __init__(self, base_url="http://localhost:11434"):
        self.base_url = base_url
        self.session = aiohttp.ClientSession()

    async def generate(self, prompt, model="dolphin-llama3"):
        """
        Genera una respuesta completa del modelo LLM.
        """
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False
        }
        async with self.session.post(url, json=payload) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("response", "")
            else:
                error_data = await response.json()
                raise Exception(f"Error en la generación: {error_data}")

    async def generate_stream(self, prompt, model="dolphin-llama3"):
        """
        Genera una respuesta del modelo LLM en streaming.
        """
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": True
        }

        async with self.session.post(url, json=payload) as response:
            if response.status != 200:
                error_data = await response.json()
                raise Exception(f"Error en el streaming: {error_data}")

            async for line in response.content:
                if line.endswith(b'\n'):
                    chunk = line.decode('utf-8').strip()
                    if chunk:
                        try:
                            data = json.loads(chunk)
                            if "response" in data:
                                yield data["response"]
                        except json.JSONDecodeError:
                            continue

    async def close(self):
        """Cierra la sesión HTTP."""
        await self.session.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()