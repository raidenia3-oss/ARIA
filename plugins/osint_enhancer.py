"""AURA Plugin Example — OSINT Tools Enhancer."""

from __future__ import annotations

from typing import Any, Dict, Optional

from aura_plugin_system import AuraPlugin


class OSINTEnhancerPlugin(AuraPlugin):
    def get_name(self) -> str:
        return "OSINT Enhancer"
    
    def get_version(self) -> str:
        return "1.0.0"
    
    def get_description(self) -> str:
        return "Adds extra OSINT tools and quick search commands"
    
    def get_author(self) -> str:
        return "AURA"
    
    def get_commands(self) -> Dict[str, Any]:
        return {
            "osint_search": lambda query: f"https://www.google.com/search?q={query}",
            "whois": lambda domain: f"https://who.is/whois/{domain}",
            "shodan": lambda query: f"https://www.shodan.io/search?query={query}",
            "virustotal": lambda hash: f"https://www.virustotal.com/gui/search/{hash}",
        }
    
    def on_load(self) -> None:
        print(f"[PLUGIN] {self.get_name()} loaded!")
    
    def on_chat_message(self, message: str) -> Optional[str]:
        lower = message.lower()
        if lower.startswith("osint "):
            query = message[6:].strip()
            return f"OSINT search: https://www.google.com/search?q={query}"
        if lower.startswith("whois "):
            domain = message[6:].strip()
            return f"WHOIS lookup: https://who.is/whois/{domain}"
        if lower.startswith("shodan "):
            query = message[7:].strip()
            return f"Shodan search: https://www.shodan.io/search?query={query}"
        return None
