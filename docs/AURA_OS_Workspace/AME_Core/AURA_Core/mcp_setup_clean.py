#!/usr/bin/env python3
"""
Script para configurar MCP (Model Context Protocol) en AURA.
"""

import json
from pathlib import Path


class MCPSetup:
    def __init__(self):
        self.mcp_config_dir = Path("~/.mcp").expanduser()
        self.mcp_config_dir.mkdir(exist_ok=True)

    def install_mcp(self):
        try:
            print("🔧 Configurando MCP...")
            config_path = self.mcp_config_dir / "config.json"
            config = {
                "version": "1.0",
                "servers": {
                    "vscode": {"enabled": True, "port": 5005, "description": "Contexto VS Code"},
                    "terminal": {"enabled": True, "port": 5006, "description": "Terminal"},
                },
            }
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
            return True
        except Exception as e:
            print(f"❌ Error al configurar MCP: {e}")
            return False
