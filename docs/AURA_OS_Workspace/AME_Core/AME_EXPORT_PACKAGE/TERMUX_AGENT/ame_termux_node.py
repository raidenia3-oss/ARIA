#!/usr/bin/env python3
"""
ame_termux_node.py — Cliente Termux del Ecosistema AURA/AME
Lee notas Markdown de la bóveda e interactúa asíncronamente con el backend de la PC.
"""

import os, sys, json, time, logging, asyncio
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

try:
    import aiohttp
except ImportError:
    aiohttp = None

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('AME_Termux_Node')

SCRIPT_DIR = Path(__file__).resolve().parent
VAULT_DIR = SCRIPT_DIR.parent / "AURA_INTELLIGENCE_VAULT"
CONFIG_FILE = SCRIPT_DIR / "config" / "node_config.json"

DEFAULT_CONFIG = {
    "server_url": "http://192.168.3.10:5000",
    "poll_interval": 10,
    "vault_path": str(VAULT_DIR),
    "auto_sync": True
}

class AMETermuxNode:
    def __init__(self):
        self.config = self._load_config()
        self.server_url = self.config.get("server_url", "http://192.168.3.10:5000")
        self.session = None

    def _load_config(self) -> Dict:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE) as f:
                return json.load(f)
        return DEFAULT_CONFIG

    async def _get_session(self):
        if self.session is None and aiohttp:
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
        return self.session

    async def health_check(self) -> bool:
        if not aiohttp:
            return False
        try:
            s = await self._get_session()
            async with s.get(f"{self.server_url}/health") as r:
                return (await r.json()).get("status") == "healthy"
        except:
            return False

    async def chat(self, messages: List[Dict]) -> Optional[Dict]:
        if not aiohttp:
            return None
        try:
            s = await self._get_session()
            async with s.post(f"{self.server_url}/v1/chat/completions", json={"messages": messages}) as r:
                return await r.json() if r.status == 200 else None
        except:
            return None

    async def search(self, query: str, top_k: int = 5) -> List[Dict]:
        if not aiohttp:
            return []
        try:
            s = await self._get_session()
            async with s.post(f"{self.server_url}/v1/knowledge/search", json={"query": query, "top_k": top_k}) as r:
                return (await r.json()).get("results", []) if r.status == 200 else []
        except:
            return []

    def read_vault(self) -> List[str]:
        if not VAULT_DIR.exists():
            return []
        files = []
        for f in sorted(VAULT_DIR.rglob("*.md")):
            try:
                content = f.read_text(encoding='utf-8')
                files.append(f"📄 {f.relative_to(VAULT_DIR)} ({len(content)} chars)")
            except:
                pass
        return files

    async def interactive(self):
        print("\n=== AME Termux Node ===")
        print("Comandos: 'chat <msg>', 'buscar <q>', 'vault', 'salir'\n")

        while True:
            try:
                inp = input(">>> ").strip()
                if not inp:
                    continue
                if inp == "salir":
                    break
                if inp == "vault":
                    files = self.read_vault()
                    print(f"\nBóveda local ({len(files)} archivos):")
                    for f in files[:10]:
                        print(f"  {f}")
                    continue
                if inp.startswith("buscar "):
                    q = inp[7:]
                    results = await self.search(q)
                    print(f"\nResultados para '{q}':")
                    for r in results[:3]:
                        print(f"  [{r.get('similarity',0):.2f}] {r.get('title','?')}")
                        print(f"      {r.get('content','')[:150]}...")
                    continue
                if inp.startswith("chat "):
                    msg = inp[5:]
                    resp = await self.chat([{"role": "user", "content": msg}])
                    if resp:
                        content = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
                        print(f"\nAME: {content}\n")
                    else:
                        print("Error de conexión.\n")
                    continue
                # Default: enviar como chat
                resp = await self.chat([{"role": "user", "content": inp}])
                if resp:
                    content = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
                    print(f"\nAME: {content}\n")
                else:
                    print("Error de conexión.\n")
            except KeyboardInterrupt:
                print("\nSaliendo...")
                break

    async def run(self):
        alive = await self.health_check()
        if alive:
            logger.info("✅ Servidor PC conectado")
        else:
            logger.warning("⚠️ Servidor no disponible - modo local")
            files = self.read_vault()
            logger.info(f"Bóveda local: {len(files)} notas")

        if aiohttp:
            await self.interactive()
        else:
            logger.info("Modo lectura de bóveda (sin aiohttp):")
            for f in self.read_vault():
                print(f"  {f}")

        if self.session and aiohttp:
            await self.session.close()

def main():
    node = AMETermuxNode()
    asyncio.run(node.run())

if __name__ == "__main__":
    main()