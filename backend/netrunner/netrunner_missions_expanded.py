# -*- coding: utf-8 -*-
"""AURA Netrunner v2 — Expanded Mission System.

50+ missions across 4 tiers + bosses.
    Tier 1 (Level 1-5): 10 missions
    Tier 2 (Level 6-10): 10 missions
    Tier 3 (Level 11-15): 10 missions + Boss
    Tier 4 (Level 16-20): 10 missions + Final Boss

Integrates with daemon via EventBus.
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from backend.core import get_event_bus

logger = logging.getLogger("AURA.Netrunner")


class SecurityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MissionStatus(str, Enum):
    AVAILABLE = "available"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Mission:
    mission_id: str
    title: str
    target_ip: str
    target_hostname: str
    difficulty: SecurityLevel
    level: int
    objective: str
    description: str
    reward: float
    status: MissionStatus = MissionStatus.AVAILABLE
    ices: List[Dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.mission_id,
            "title": self.title,
            "target": self.target_ip,
            "hostname": self.target_hostname,
            "difficulty": self.difficulty.value,
            "level": self.level,
            "objective": self.objective,
            "description": self.description,
            "reward": self.reward,
            "status": self.status.value,
            "ices": self.ices,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


# ═══════════════════════════════════════════════════════
# TIER 1 — Levels 1-5 (Beginner, 10 missions)
# ═══════════════════════════════════════════════════════
TIER1_MISSIONS = [
    {"title": "Scan Network", "target_ip": "192.168.1.1", "level": 1, "reward": 1.00, "desc": "Basic network scan and enumerate hosts"},
    {"title": "Find Firewall", "target_ip": "192.168.1.2", "level": 2, "reward": 1.50, "desc": "Locate and identify firewall rules"},
    {"title": "Bypass Router", "target_ip": "192.168.1.1", "level": 2, "reward": 2.00, "desc": "Bypass the router to access internal network"},
    {"title": "Access Laptop", "target_ip": "192.168.1.10", "level": 3, "reward": 2.50, "desc": "Gain access to a user laptop"},
    {"title": "Steal WiFi Password", "target_ip": "192.168.1.1", "level": 3, "reward": 3.00, "desc": "Crack the WiFi password of the network"},
    {"title": "Map Subnet", "target_ip": "192.168.1.0", "level": 3, "reward": 2.75, "desc": "Map the entire subnet topology"},
    {"title": "Access Printer", "target_ip": "192.168.1.50", "level": 2, "reward": 1.75, "desc": "Access network printer admin panel"},
    {"title": "Read Smart TV Cache", "target_ip": "192.168.1.55", "level": 3, "reward": 2.25, "desc": "Extract cached credentials from Smart TV"},
    {"title": "Compromise IoT Hub", "target_ip": "192.168.1.60", "level": 4, "reward": 3.50, "desc": "Take over the IoT hub device"},
    {"title": "Sniff Credentials", "target_ip": "192.168.1.1", "level": 4, "reward": 4.00, "desc": "Sniff unencrypted credentials on the network"},
    {"title": "Port Scan", "target_ip": "192.168.1.2", "level": 1, "reward": 0.75, "desc": "Scan open ports on target host"},
    {"title": "Check Services", "target_ip": "192.168.1.3", "level": 1, "reward": 0.80, "desc": "Enumerate running services"},
    {"title": "DNS Lookup", "target_ip": "192.168.1.1", "level": 1, "reward": 0.50, "desc": "Perform DNS enumeration"},
    {"title": "Test Firewall Rules", "target_ip": "192.168.1.1", "level": 2, "reward": 1.25, "desc": "Test firewall rule weaknesses"},
    {"title": "Find Open Shares", "target_ip": "192.168.1.5", "level": 2, "reward": 1.50, "desc": "Discover open network shares"},
]

# ═══════════════════════════════════════════════════════
# TIER 2 — Levels 6-10 (Intermediate, 10 missions)
# ═══════════════════════════════════════════════════════
TIER2_MISSIONS = [
    {"title": "Breach Corporate Network", "target_ip": "10.0.0.1", "level": 6, "reward": 5.00, "desc": "Penetrate the corporate perimeter"},
    {"title": "Find Admin Account", "target_ip": "10.0.0.100", "level": 7, "reward": 6.50, "desc": "Locate and compromise admin credentials"},
    {"title": "Steal Database", "target_ip": "10.0.0.200", "level": 7, "reward": 8.00, "desc": "Exfiltrate the main database"},
    {"title": "Corrupt Backup", "target_ip": "10.0.0.250", "level": 8, "reward": 9.00, "desc": "Disable backup systems to cause impact"},
    {"title": "Deploy Ransomware (Simulated)", "target_ip": "10.0.0.1", "level": 8, "reward": 10.00, "desc": "Simulate ransomware deployment across network"},
    {"title": "Privilege Escalation", "target_ip": "10.0.0.50", "level": 8, "reward": 8.50, "desc": "Escalate from user to root"},
    {"title": "Lateral Movement", "target_ip": "10.0.1.0", "level": 7, "reward": 7.00, "desc": "Pivot through internal servers"},
    {"title": "Extract API Keys", "target_ip": "10.0.0.150", "level": 7, "reward": 7.50, "desc": "Find and extract hardcoded API keys"},
    {"title": "Disable SIEM", "target_ip": "10.0.0.5", "level": 9, "reward": 12.00, "desc": "Take down Security Information and Event Management"},
    {"title": "Establish Persistence", "target_ip": "10.0.0.1", "level": 9, "reward": 11.00, "desc": "Maintain long-term access to compromised system"},
]

# ═══════════════════════════════════════════════════════
# TIER 3 — Levels 11-15 (Advanced + Boss, 10 missions)
# ═══════════════════════════════════════════════════════
TIER3_MISSIONS = [
    {"title": "Hack Government Server", "target_ip": "172.16.0.1", "level": 11, "reward": 15.00, "desc": "Infiltrate government infrastructure"},
    {"title": "Steal Top Secret Data", "target_ip": "172.16.0.10", "level": 12, "reward": 20.00, "desc": "Extract classified intelligence data"},
    {"title": "Take Down ISP", "target_ip": "172.16.0.100", "level": 13, "reward": 25.00, "desc": "Disrupt ISP infrastructure operations"},
    {"title": "Become Master Hacker", "target_ip": "172.16.0.50", "level": 14, "reward": 30.00, "desc": "Achieve master hacker status by completing hard challenges"},
    {"title": "BOSS: Hack The Planet", "target_ip": "0.0.0.0", "level": 15, "reward": 50.00, "desc": "FINAL BOSS: Compromise global network backbone"},
    {"title": "Hack Military Network", "target_ip": "172.16.1.1", "level": 13, "reward": 22.00, "desc": "Access restricted military communication"},
    {"title": "Breach Bank Security", "target_ip": "172.16.0.5", "level": 13, "reward": 24.00, "desc": "Crack banking security systems"},
    {"title": "Disable Nuclear Plant", "target_ip": "172.16.0.77", "level": 14, "reward": 35.00, "desc": "Access SCADA of nuclear power plant (simulated)"},
    {"title": "Hack Crypto Exchange", "target_ip": "172.16.0.20", "level": 14, "reward": 28.00, "desc": "Steal from cryptocurrency exchange"},
    {"title": "Access 5G Core", "target_ip": "172.16.0.80", "level": 15, "reward": 32.00, "desc": "Compromise 5G mobile network core"},
]

# ═══════════════════════════════════════════════════════
# TIER 4 — Levels 16-20 (Master + Final Boss, 10 missions)
# ═══════════════════════════════════════════════════════
TIER4_MISSIONS = [
    {"title": "Hack Alien Network", "target_ip": "100.64.0.1", "level": 16, "reward": 40.00, "desc": "Access extraterrestrial communication network"},
    {"title": "Control Satellites", "target_ip": "100.64.0.10", "level": 17, "reward": 45.00, "desc": "Take control of orbital satellites"},
    {"title": "Start Cyber Revolution", "target_ip": "100.64.0.50", "level": 18, "reward": 50.00, "desc": "Initiate mass digital uprising"},
    {"title": "Build Net Utopia", "target_ip": "100.64.0.100", "level": 19, "reward": 55.00, "desc": "Construct a decentralized utopian network"},
    {"title": "FINAL BOSS: Netscape", "target_ip": "255.255.255.255", "level": 20, "reward": 100.00, "desc": "EASTER EGG: Defeat the legendary Netscape"},
    {"title": "Hack AI Core", "target_ip": "100.64.0.20", "level": 17, "reward": 42.00, "desc": "Access and control the AI core"},
    {"title": "Override Power Grid", "target_ip": "100.64.0.60", "level": 18, "reward": 48.00, "desc": "Control national power grid infrastructure"},
    {"title": "Access Quantum Computer", "target_ip": "100.64.0.80", "level": 18, "reward": 52.00, "desc": "Use quantum computer for cryptanalysis"},
    {"title": "Hack Time Machine", "target_ip": "100.64.0.99", "level": 19, "reward": 60.00, "desc": "Access temporal data (Easter Egg)"},
    {"title": "Transcend Network", "target_ip": "100.64.1.1", "level": 20, "reward": 75.00, "desc": "Become one with the network (Endgame)"},
]

ALL_MISSIONS = TIER1_MISSIONS + TIER2_MISSIONS + TIER3_MISSIONS + TIER4_MISSIONS

BONUS_MISSION_DEFS = [
    {"title": "Breach Corporate Firewall", "target_ip": "10.0.0.1", "level": 5, "reward": 2.50, "target_hostname": "corp-firewall.corp.local", "description": "Penetrate the hardened perimeter firewall"},
    {"title": "Steal Data Vault", "target_ip": "10.0.1.100", "level": 7, "reward": 5.00, "target_hostname": "vault.datacenter.local", "description": "Infiltrate the data vault"},
    {"title": "Corrupt ICE Network", "target_ip": "10.0.2.50", "level": 8, "reward": 7.50, "target_hostname": "ice-grid.security.local", "description": "Disable ICE monitoring grid"},
    {"title": "Become System Admin", "target_ip": "10.0.0.254", "level": 10, "reward": 15.00, "target_hostname": "root.admin.local", "description": "Privilege escalation to root"},
    {"title": "Hack The Planet", "target_ip": "0.0.0.0", "level": 15, "reward": 50.00, "target_hostname": "the-planet.global", "description": "FINAL BOSS"},
]

MISSING_COUNT = 18


def _generate_ices(difficulty: SecurityLevel) -> List[Dict[str, Any]]:
    ice_types = ["Firewall", "Honeypot", "IDS", "Trap", "Daemon", "Proxy"]
    trap_types = ["none", "trace", "lock", "crash", "alert_admin"]

    weights = {
        SecurityLevel.LOW: (1, 2),
        SecurityLevel.MEDIUM: (2, 4),
        SecurityLevel.HIGH: (4, 6),
        SecurityLevel.CRITICAL: (6, 8),
    }
    min_str, max_str = weights.get(difficulty, (2, 4))
    count = random.randint(min_str, max_str)

    ices = []
    for i in range(count):
        ices.append({
            "name": f"ICE-{i+1}",
            "type": random.choice(ice_types),
            "strength": random.randint(min_str, max_str + 2),
            "trap": random.choice(trap_types) if difficulty in (SecurityLevel.HIGH, SecurityLevel.CRITICAL) else "none",
        })
    return ices


def generate_missions_v2() -> List[Mission]:
    """Generate all 50+ tier missions."""
    missions: List[Mission] = []

    all_mission_defs = ALL_MISSIONS + [
        {
            "mission_id": f"NRK-BONUS-{i}",
            "title": bm["title"],
            "target_ip": bm["target_ip"],
            "target_hostname": bm["target_hostname"],
            "level": bm["level"],
            "reward": bm["reward"],
            "desc": bm["description"],
        }
        for i, bm in enumerate(BONUS_MISSION_DEFS)
    ]

    for i, mdef in enumerate(all_mission_defs):
        level = mdef.get("level", 1)
        if level <= 5:
            diff = SecurityLevel.LOW if level <= 2 else SecurityLevel.MEDIUM if level <= 3 else SecurityLevel.HIGH
        elif level <= 10:
            diff = SecurityLevel.MEDIUM if level <= 7 else SecurityLevel.HIGH if level <= 9 else SecurityLevel.CRITICAL
        elif level <= 15:
            diff = SecurityLevel.HIGH if level <= 12 else SecurityLevel.CRITICAL
        else:
            diff = SecurityLevel.CRITICAL

        mission = Mission(
            mission_id=mdef.get("mission_id", f"NRK-V2-{i:03d}") if "mission_id" in mdef else f"NRK-V2-{i:03d}",
            title=mdef["title"],
            target_ip=mdef["target_ip"],
            target_hostname=mdef.get("target_hostname", f"host-{mdef['target_ip'].replace('.', '-')}.local"),
            difficulty=diff,
            level=level,
            objective=mdef["desc"],
            description=mdef["desc"],
            reward=mdef["reward"],
            ices=_generate_ices(diff),
        )
        missions.append(mission)

    logger.info("Generated %d missions (v2)", len(missions))
    return missions


def attempt_mission_v2(mission: Mission, skill: int = 5) -> Dict[str, Any]:
    """Attempt to complete a mission."""
    ices_breached = 0
    traps_triggered = []
    damage = 0

    for ice in mission.ices:
        ice_strength = ice.get("strength", 5)
        if skill >= ice_strength:
            ices_breached += 1
        else:
            traps_triggered.append(ice.get("name", "ICE"))
            if ice.get("trap", "none") != "none":
                damage += random.randint(1, min(ice_strength, 10))

    success = ices_breached > len(mission.ices) // 2 or (not traps_triggered and skill >= 3)

    result = {
        "mission_id": mission.mission_id,
        "title": mission.title,
        "success": success,
        "damage_taken": damage,
        "traps_triggered": traps_triggered,
        "ices_breached": ices_breached,
        "total_ices": len(mission.ices),
    }

    if success:
        mission.status = MissionStatus.COMPLETED
        mission.completed_at = time.time()

        event_bus = get_event_bus()
        if event_bus:
            event_bus.emit_simple("netrunner_mission_complete", {
                "mission_id": mission.mission_id,
                "title": mission.title,
                "reward": mission.reward,
                "level": mission.level,
                "total_reward": mission.reward,
                "timestamp": datetime.now().isoformat(),
            }, agent="netrunner")
        logger.info("Mission complete: %s -> +$%.2f", mission.title, mission.reward)
    else:
        mission.status = MissionStatus.FAILED
        logger.info("Mission failed: %s", mission.title)

    return result


MISSIONS_V2_CACHE: Optional[List[Mission]] = None


def get_missions_v2() -> List[Mission]:
    """Get or create cached mission list."""
    global MISSIONS_V2_CACHE
    if MISSIONS_V2_CACHE is None:
        MISSIONS_V2_CACHE = generate_missions_v2()
    return MISSIONS_V2_CACHE


async def auto_generate_missions(state: Optional[Any] = None) -> List[Mission]:
    """Auto-generate missions for netrunner state (compatibility wrapper)."""
    return get_missions_v2()
