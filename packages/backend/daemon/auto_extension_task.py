import json
import os
import time
import asyncio
import hashlib
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


class AutoExtensionTask:
    def __init__(self, interval_seconds: int = 86400):
        self.interval = interval_seconds
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._analysis_history: List[Dict[str, Any]] = []
        self._proposed_agents: List[Dict[str, Any]] = []
        self.storage_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs", "auto_extension")
        os.makedirs(self.storage_dir, exist_ok=True)
        self._load()

    def _load(self) -> None:
        path = os.path.join(self.storage_dir, "history.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._analysis_history = data.get("history", [])
                self._proposed_agents = data.get("proposed", [])
            except Exception:
                pass

    def _save(self) -> None:
        try:
            path = os.path.join(self.storage_dir, "history.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"history": self._analysis_history, "proposed": self._proposed_agents}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None

    async def _loop(self) -> None:
        while self._running:
            try:
                await self.run_analysis()
            except Exception as e:
                print(f"[AutoExtension] Analysis error: {e}")
            await asyncio.sleep(self.interval)

    async def run_analysis(self) -> Dict[str, Any]:
        analysis = {
            "timestamp": datetime.now().isoformat(),
            "trending_topics": await self._analyze_trending_topics(),
            "popular_requests": await self._analyze_popular_requests(),
            "capability_gaps": await self._identify_capability_gaps(),
            "proposed_agents": [],
            "score": 0,
        }

        for i in range(3):
            proposed = self._generate_proposal(analysis, i)
            analysis["proposed_agents"].append(proposed)
            self._proposed_agents.append(proposed)

        score = self._calculate_score(analysis)
        analysis["score"] = score

        self._analysis_history.append(analysis)
        if len(self._analysis_history) > 100:
            self._analysis_history = self._analysis_history[-100:]
        self._save()

        if score > 80:
            for agent in analysis["proposed_agents"]:
                self._auto_activate(agent)

        return analysis

    async def _analyze_trending_topics(self) -> List[Dict[str, Any]]:
        topics = [
            {"topic": "AI asistentes", "mentions": hash(str(time.time())) % 5000 + 1000, "growth": 15.5},
            {"topic": "Automatizacion", "mentions": hash(str(time.time() + 1)) % 3000 + 500, "growth": 8.2},
            {"topic": "Seguridad digital", "mentions": hash(str(time.time() + 2)) % 2000 + 200, "growth": 22.1},
        ]
        return topics

    async def _analyze_popular_requests(self) -> List[Dict[str, Any]]:
        return [
            {"type": "translation", "count": 145, "growth": 12.3},
            {"type": "summarization", "count": 89, "growth": 5.7},
            {"type": "content_moderation", "count": 67, "growth": 18.4},
        ]

    async def _identify_capability_gaps(self) -> List[Dict[str, Any]]:
        return [
            {"gap": "multimodal_search", "impact": "high", "demand": 0.78},
            {"gap": "voice_commands", "impact": "medium", "demand": 0.65},
            {"gap": "smart_automation", "impact": "high", "demand": 0.82},
        ]

    def _generate_proposal(self, analysis: Dict[str, Any], index: int) -> Dict[str, Any]:
        topics = analysis.get("trending_topics", [])
        gaps = analysis.get("capability_gaps", [])
        topic = topics[index % len(topics)]["topic"] if topics else "Nuevo dominio"
        gap = gaps[index % len(gaps)] if gaps else {"gap": "nueva_capabilidad", "impact": "medium"}

        name = f"auto-agent-{topic.lower().replace(' ', '-')}-{index + 1}"
        agent_type = {
            "multimodal_search": "search-agent",
            "voice_commands": "voice-agent",
            "smart_automation": "automation-agent",
        }.get(gap.get("gap", ""), "general-agent")

        return {
            "name": name,
            "type": agent_type,
            "description": f"Agente automatico para: {topic}",
            "capabilities": [gap["gap"], "automation", "learning"],
            "estimated_demand": gap.get("demand", 0.5),
            "confidence": round(hash(str(index) + topic) % 30 / 100 + 0.6, 2),
            "generated_code": f"# Auto-generated for {topic}\nclass {name.replace('-', '_')}(PluginAgent):\n    pass",
        }

    def _calculate_score(self, analysis: Dict[str, Any]) -> float:
        topics_score = len(analysis.get("trending_topics", [])) * 10
        requests_score = min(len(analysis.get("popular_requests", [])) * 12, 36)
        gaps_score = sum(g.get("demand", 0) * 40 for g in analysis.get("capability_gaps", []))
        return min(round(topics_score + requests_score + gaps_score, 1), 100)

    def _auto_activate(self, agent: Dict[str, Any]) -> None:
        agent["auto_activated"] = True
        agent["activated_at"] = datetime.now().isoformat()
        print(f"[AutoExtension] Auto-activated: {agent['name']}")

    def get_proposed_agents(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self._proposed_agents[-limit:]

    def get_analysis_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        return self._analysis_history[-limit:]

    def get_status(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "interval_seconds": self.interval,
            "analyses_run": len(self._analysis_history),
            "proposed_total": len(self._proposed_agents),
            "last_analysis": self._analysis_history[-1] if self._analysis_history else None,
        }
