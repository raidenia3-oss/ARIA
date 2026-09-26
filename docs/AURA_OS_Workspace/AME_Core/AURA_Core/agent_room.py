#!/usr/bin/env python3
"""
agent_room.py - Salas Multi-Agente y Orquestación
Modulo para chats grupales entre perfiles de IA distintos.
"""

import asyncio
import json
import logging
import time
import random
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class AgentProfile:
    def __init__(self, agent_id: str, name: str, provider: str, system_prompt: str = ""):
        self.agent_id = agent_id
        self.name = name
        self.provider = provider
        self.system_prompt = system_prompt
        self.message_history: List[Dict] = []

    def to_dict(self) -> Dict:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "provider": self.provider,
            "history_len": len(self.message_history),
        }


class AgentRoom:
    def __init__(self, room_id: str, topic: str = ""):
        self.room_id = room_id
        self.topic = topic
        self.agents: Dict[str, AgentProfile] = {}
        self.participants: List[str] = []
        self.message_log: List[Dict] = []
        self.created_at = datetime.now().isoformat()

    def add_agent(self, profile: AgentProfile):
        self.agents[profile.agent_id] = profile
        if profile.agent_id not in self.participants:
            self.participants.append(profile.agent_id)

    def remove_agent(self, agent_id: str):
        self.agents.pop(agent_id, None)
        if agent_id in self.participants:
            self.participants.remove(agent_id)

    def get_summary(self) -> Dict:
        return {
            "room_id": self.room_id,
            "topic": self.topic,
            "agents": [a.to_dict() for a in self.agents.values()],
            "messages": len(self.message_log),
            "participants": self.participants,
        }


class AgentOrchestrator:
    def __init__(self):
        self.rooms: Dict[str, AgentRoom] = {}
        self.max_rounds = 3
        self.delay_between_agents = 1.0

    def create_room(self, room_id: str, topic: str = "") -> AgentRoom:
        room = AgentRoom(room_id, topic)
        self.rooms[room_id] = room
        logger.info(f"[Orchestrator] Sala creada: {room_id}")
        return room

    def register_agent(self, room_id: str, profile: AgentProfile) -> bool:
        room = self.rooms.get(room_id)
        if not room:
            return False
        room.add_agent(profile)
        logger.info(f"[Orchestrator] Agente {profile.name} unido a {room_id}")
        return True

    async def run_debate(self, room_id: str, initial_prompt: str, ws_callback=None) -> List[Dict]:
        room = self.rooms.get(room_id)
        if not room or not room.agents:
            return []

        messages: List[Dict] = []
        participants = list(room.agents.values())
        current_prompt = initial_prompt

        for round_idx in range(1, self.max_rounds + 1):
            for agent in participants:
                response = {
                    "room_id": room_id,
                    "round": round_idx,
                    "agent_id": agent.agent_id,
                    "agent_name": agent.name,
                    "provider": agent.provider,
                    "content": f"[Respuesta simulada de {agent.name} sobre: {current_prompt[:60]}...]",
                    "timestamp": datetime.now().isoformat(),
                }
                room.message_log.append(response)
                messages.append(response)
                if ws_callback:
                    await ws_callback(response)
                await asyncio.sleep(self.delay_between_agents)
            current_prompt = messages[-1]["content"] if messages else current_prompt

        return messages

    def get_room(self, room_id: str) -> Optional[AgentRoom]:
        return self.rooms.get(room_id)

    def list_rooms(self) -> List[Dict]:
        return [room.get_summary() for room in self.rooms.values()]


_orchestrator = AgentOrchestrator()


def get_orchestrator() -> AgentOrchestrator:
    return _orchestrator
