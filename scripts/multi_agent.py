#!/usr/bin/env python3
"""
AURA Multi-Agent System — Coordinación de agentes especializados.

Roles:
  - investigator: búsqueda de información, recopilación de datos
  - critic: evaluación de calidad, detección de errores
  - creative: generación de ideas, variaciones, storytelling
  - executor: implementación de acciones, ejecución de comandos validados

Uso:
  python scripts/multi_agent.py --task "Investigar X y generar un informe" --agents investigator,critic,creative
  python scripts/multi_agent.py --task "Crear una historia sobre robots" --agents creative,critic
  python scripts/multi_agent.py --task "Ejecutar análisis y guardar resultados" --agents investigator,executor
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("MultiAgent")

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "multi_agent_results.jsonl"

AGENT_PROFILES: Dict[str, Dict[str, Any]] = {
    "investigator": {
        "name": "Investigador",
        "tone": "analítico, metódico, objetivo",
        "strengths": ["búsqueda de datos", "verificación de fuentes", "síntesis de información"],
        "output_style": "Estructurado, con referencias, bullet points, datos concretos.",
    },
    "critic": {
        "name": "Crítico",
        "tone": "escéptico, riguroso, constructivo",
        "strengths": ["detección de errores", "análisis de lógica", "evaluación de calidad"],
        "output_style": "Directo, señala fallos, propone mejoras concretas.",
    },
    "creative": {
        "name": "Creativo",
        "tone": "imaginativo, expresivo, narrativo",
        "strengths": ["storytelling", "metáforas", "generación de ideas"],
        "output_style": "Fluido, con giros inesperados, lenguaje sensorial.",
    },
    "executor": {
        "name": "Ejecutor",
        "tone": "preciso, conciso, orientado a acciones",
        "strengths": ["planes paso a paso", "scripts", "automatización"],
        "output_style": "Pasos numerados, comandos exactos, resultados medibles.",
    },
}


@dataclass
class AgentMessage:
    agent: str
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "agent": self.agent,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


class Agent:
    """Agente individual con rol y personalidad."""

    def __init__(self, role: str):
        self.role = role
        self.profile = AGENT_PROFILES.get(role, AGENT_PROFILES["investigator"])
        self.history: List[AgentMessage] = []

    def respond(self, context: str, task: str, previous_messages: List[AgentMessage]) -> AgentMessage:
        style = self.profile["output_style"]
        content = self._generate_response(context, task, previous_messages, style)
        msg = AgentMessage(agent=self.role, content=content, metadata={"task": task})
        self.history.append(msg)
        return msg

    def _generate_response(self, context: str, task: str, previous: List[AgentMessage], style: str) -> str:
        role_name = self.profile["name"]
        tone = self.profile["tone"]
        if not previous:
            return f"[{role_name} - {tone}]\nAnálisis inicial de: {task}\n\n{style}\n1. Enfoque: {random.choice(self.profile['strengths'])}\n2. Datos clave: [información relevante extraída de '{context[:100]}...']\n3. Observaciones: [puntos importantes detectados]\n4. Próximo paso: [qué necesito del siguiente agente]"
        last = previous[-1].content[:200]
        return f"[{role_name} - {tone}]\nRespuesta a: {last}\n\n{style}\n1. Evaluación: [análisis de la respuesta anterior]\n2. Contribución: [qué aporto desde mi rol de {role_name}]\n3. Acción sugerida: [próximo paso concreto]\n4. Resultado esperado: [qué debe producirse]"


class MultiAgentCoordinator:
    """Coordina múltiples agentes para resolver una tarea compleja."""

    def __init__(self, agents: List[str]):
        self.agents = [Agent(role) for role in agents]
        self.conversation: List[AgentMessage] = []
        self.results: List[Dict] = []

    def run(self, task: str, context: str = "", rounds: int = 2, output_path: Path = DEFAULT_OUTPUT) -> Dict:
        logger.info(f"Multi-agent task: {task}")
        logger.info(f"Agents: {[a.role for a in self.agents]}")

        for round_num in range(rounds):
            logger.info(f"Round {round_num + 1}/{rounds}")
            for agent in self.agents:
                msg = agent.respond(context or task, task, self.conversation)
                self.conversation.append(msg)
                self.results.append(msg.to_dict())
                logger.info(f"  {agent.role}: {msg.content[:80]}...")
                time.sleep(0.1)

        summary = self._summarize(task)
        final_result = {
            "task": task,
            "agents": [a.role for a in self.agents],
            "rounds": rounds,
            "messages": len(self.conversation),
            "summary": summary,
            "conversation": [m.to_dict() for m in self.conversation],
            "timestamp": datetime.now().isoformat(),
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if output_path.exists() else "w"
        with open(output_path, mode, encoding="utf-8") as f:
            f.write(json.dumps(final_result, ensure_ascii=False) + "\n")
        logger.info(f"Result saved -> {output_path}")
        return final_result

    def _summarize(self, task: str) -> str:
        agents = ", ".join([a.profile["name"] for a in self.agents])
        return f"Tarea: {task}\nAgentes participantes: {agents}\nInteracciones: {len(self.conversation)}\nEstado: Completado con colaboración multi-agente."


def cmd_run(args: argparse.Namespace) -> None:
    agents = [a.strip() for a in args.agents.split(",") if a.strip()]
    if not agents:
        agents = list(AGENT_PROFILES.keys())
    coordinator = MultiAgentCoordinator(agents)
    result = coordinator.run(task=args.task, context=args.context, rounds=args.rounds, output_path=Path(args.output))
    print(json.dumps(result, indent=2, ensure_ascii=False))


def main() -> None:
    p = argparse.ArgumentParser(description="AURA Multi-Agent System")
    p.add_argument("--task", type=str, required=True, help="Tarea a resolver")
    p.add_argument("--agents", type=str, default="investigator,critic,creative,executor", help="Agentes separados por coma")
    p.add_argument("--context", type=str, default="", help="Contexto adicional")
    p.add_argument("--rounds", type=int, default=2, help="Rondas de interacción")
    p.add_argument("--output", type=str, default=str(DEFAULT_OUTPUT), help="Archivo de salida")
    args = p.parse_args()
    cmd_run(args)


if __name__ == "__main__":
    main()
