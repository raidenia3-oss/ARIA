import time
import uuid
import json
import os
from typing import Any, Dict, List, Optional


class AgentRegistryV2:
    def __init__(self, storage_dir: Optional[str] = None):
        if storage_dir is None:
            base = os.path.dirname(os.path.abspath(__file__))
            storage_dir = os.path.join(base, "..", "logs", "agents")
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)
        self._agents: Dict[str, Dict[str, Any]] = {}
        self._configs: Dict[str, Dict[str, Any]] = {}
        self._endpoints: Dict[str, List[str]] = {}
        self._load()

    def _load(self) -> None:
        path = os.path.join(self.storage_dir, "registry.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._agents = data.get("agents", {})
                self._configs = data.get("configs", {})
                self._endpoints = data.get("endpoints", {})
            except Exception:
                pass

    def _save(self) -> None:
        try:
            path = os.path.join(self.storage_dir, "registry.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({
                    "agents": self._agents,
                    "configs": self._configs,
                    "endpoints": self._endpoints,
                }, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def register_agent(self, agent_config: Dict[str, Any]) -> Dict[str, Any]:
        name = agent_config.get("name", "")
        if not name:
            return {"error": "Agent name required", "agent_id": None, "endpoints": []}
        for aid, a in self._agents.items():
            if a.get("name") == name:
                return {"error": f"Agent '{name}' already registered", "agent_id": aid, "endpoints": self._endpoints.get(aid, [])}

        agent_id = f"agent-{uuid.uuid4().hex[:12]}"
        endpoints = [f"/api/agent/{agent_id}", f"/ws/agent/{agent_id}", f"/v1/agents/{name}"]
        created_at = time.time()

        agent_entry = {
            "agent_id": agent_id,
            "name": name,
            "type": agent_config.get("type", "custom"),
            "description": agent_config.get("description", ""),
            "status": "active",
            "created_at": created_at,
            "commands": agent_config.get("commands", []),
            "capabilities": agent_config.get("capabilities", []),
            "revenue": 0.0,
            "request_count": 0,
        }
        self._agents[agent_id] = agent_entry
        self._configs[agent_id] = {
            **agent_config,
            "settings": agent_config.get("settings", {}),
            "registered_at": created_at,
        }
        self._endpoints[agent_id] = endpoints
        self._save()
        return {"agent_id": agent_id, "endpoints": endpoints, "name": name, "status": "active"}

    def list_agents(self) -> List[Dict[str, Any]]:
        return [
            {
                "agent_id": a["agent_id"],
                "name": a["name"],
                "type": a["type"],
                "status": a["status"],
                "commands": a.get("commands", []),
                "revenue": a.get("revenue", 0.0),
                "request_count": a.get("request_count", 0),
                "created_at": a.get("created_at", 0),
            }
            for a in self._agents.values()
        ]

    def get_agent_config(self, agent_id: str) -> Optional[Dict[str, Any]]:
        if agent_id not in self._agents:
            return None
        return {
            "agent": self._agents[agent_id],
            "config": self._configs.get(agent_id, {}),
            "endpoints": self._endpoints.get(agent_id, []),
        }

    def update_agent_config(self, agent_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
        if agent_id not in self._agents:
            return {"status": "error", "error": f"Agent '{agent_id}' not found"}
        self._configs[agent_id] = {
            **self._configs.get(agent_id, {}),
            **config,
            "updated_at": time.time(),
        }
        for key in ("name", "description", "commands", "capabilities"):
            if key in config and key in self._agents[agent_id]:
                self._agents[agent_id][key] = config[key]
        if "status" in config:
            self._agents[agent_id]["status"] = config["status"]
        self._save()
        return {"status": "updated", "agent_id": agent_id, "config": self._configs[agent_id]}

    def get_agent_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        for a in self._agents.values():
            if a["name"] == name:
                return a
        return None

    def get_active_agents(self) -> List[Dict[str, Any]]:
        return [a for a in self._agents.values() if a.get("status") == "active"]
