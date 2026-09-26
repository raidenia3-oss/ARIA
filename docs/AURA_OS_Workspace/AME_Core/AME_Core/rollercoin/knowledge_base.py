"""
Módulo RollerCoin para AURA
Base de conocimiento que aprende con el tiempo.
"""

import json
import os
from pathlib import Path
from datetime import datetime

KB_PATH = Path("AME_Core/rollercoin/knowledge.json")


class KnowledgeBase:
    """
    Base de conocimiento de RollerCoin.
    Aprende con cada sesión: qué juegos dan más hashrate,
    cuánto duran los cooldowns, qué estrategias funcionan.
    """

    def __init__(self):
        self.data = self._load()

    def _load(self) -> dict:
        if KB_PATH.exists():
            return json.loads(KB_PATH.read_text())
        return {
            "games": {},
            "sessions": [],
            "best_strategies": {},
            "cooldown_history": {},
            "total_stats": {
                "games_played": 0,
                "hashrate_total": 0,
                "sessions": 0,
                "uptime_hours": 0,
            },
        }

    def save(self):
        KB_PATH.parent.mkdir(parents=True, exist_ok=True)
        KB_PATH.write_text(json.dumps(self.data, indent=2, ensure_ascii=False))

    def record_game_result(
        self,
        game_name: str,
        strategy: str,
        success: bool,
        hashrate_gained: str,
        cooldown_after: int,
    ):
        """Registra el resultado de un juego para aprender"""
        if game_name not in self.data["games"]:
            self.data["games"][game_name] = {
                "times_played": 0,
                "wins": 0,
                "losses": 0,
                "strategies": {},
                "avg_cooldown": 0,
                "cooldowns": [],
            }

        game = self.data["games"][game_name]
        game["times_played"] += 1
        if success:
            game["wins"] += 1
        else:
            game["losses"] += 1

        # Registrar efectividad de estrategia
        if strategy not in game["strategies"]:
            game["strategies"][strategy] = {"uses": 0, "wins": 0}
        game["strategies"][strategy]["uses"] += 1
        if success:
            game["strategies"][strategy]["wins"] += 1

        # Registrar cooldown
        game["cooldowns"].append(cooldown_after)
        if game["cooldowns"]:
            game["avg_cooldown"] = sum(game["cooldowns"]) / len(game["cooldowns"])

        self.data["total_stats"]["games_played"] += 1
        self.save()

    def get_best_strategy(self, game_name: str) -> str:
        """Retorna la mejor estrategia conocida para un juego"""
        if game_name not in self.data["games"]:
            return "generic"

        strategies = self.data["games"][game_name]["strategies"]
        if not strategies:
            return "generic"

        # Elegir la estrategia con mayor tasa de victoria
        best = max(strategies.items(), key=lambda x: x[1]["wins"] / max(x[1]["uses"], 1))
        return best[0]

    def save_state_snapshot(self, state: dict):
        """Guarda una foto del estado para análisis futuro"""
        snapshot = {
            "timestamp": state["timestamp"],
            "hashrate": state.get("hashrate", {}).get("raw", "?"),
            "games_available": sum(1 for g in state.get("games", []) if g.get("playable")),
            "balance_rlt": state.get("balance_rlt", "?"),
        }
        self.data["sessions"].append(snapshot)
        # Guardar solo las últimas 100 snapshots
        self.data["sessions"] = self.data["sessions"][-100:]
        self.save()

    def get_summary(self) -> str:
        """Resumen del conocimiento acumulado"""
        stats = self.data["total_stats"]
        games = self.data["games"]
        lines = [
            "📊 CONOCIMIENTO ACUMULADO:",
            f"   Juegos jugados: {stats['games_played']}",
            f"   Juegos conocidos: {len(games)}",
        ]
        for name, data in list(games.items())[:5]:
            rate = (data["wins"] / max(data["times_played"], 1)) * 100
            lines.append(f"   {name}: {data['times_played']} jugadas, " f"{rate:.0f}% victorias")
        return "\n".join(lines)
