# -*- coding: utf-8 -*-
"""AURA Netrunner Core — DGNS (Digital Grid Network System) engine.

Classes:
  - AccessPoint: nodo descubierto en la red local
  - ICE: contramedion de intrusion (firewall, honeypot, trap)
  - Mission: mision de hackeo generada automaticamente
  - NetrunnerState: estado global del modo netrunner
  - generate_access_points(): escanea y genera accesos

Integra con daemon via EventBus para:
  - Access points nuevos -> misiones automaticas
  - Hacks exitosos -> learning events -> AURA mejora
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("AURA.Netrunner")


class SecurityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class NodeType(str, Enum):
    IOT = "iot"
    SERVER = "server"
    PC = "pc"
    MOBILE = "mobile"
    ROUTER = "router"
    CAMERA = "camera"
    SMART_TV = "smart_tv"
    PRINTER = "printer"
    UNKNOWN = "unknown"


class AccessStatus(str, Enum):
    DISCOVERED = "discovered"
    OPEN = "open"
    FIREWALLED = "firewalled"
    HONEYPOT = "honeypot"
    COMPROMISED = "compromised"


@dataclass
class AccessPoint:
    ip: str
    mac: str
    node_type: NodeType
    security: SecurityLevel
    status: AccessStatus
    port: int = 80
    hostname: str = ""
    services: List[str] = field(default_factory=list)
    discovered_at: float = field(default_factory=time.time)
    last_scan: float = field(default_factory=time.time)
    signal_strength: int = field(default_factory=lambda: random.randint(-40, -90))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ip": self.ip,
            "mac": self.mac,
            "type": self.node_type.value,
            "security": self.security.value,
            "status": self.status.value,
            "port": self.port,
            "hostname": self.hostname or self.ip,
            "services": self.services,
            "signal": self.signal_strength,
            "discovered": self.discovered_at,
        }


@dataclass
class ICE:
    name: str
    ice_type: str
    strength: int
    trap_type: str = "none"
    triggered: bool = False
    damage: int = 0

    def is_breached(self, skill: int) -> bool:
        return skill >= self.strength

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.ice_type,
            "strength": self.strength,
            "trap": self.trap_type,
            "triggered": self.triggered,
            "damage": self.damage,
        }


@dataclass
class Mission:
    mission_id: str
    target_ip: str
    target_hostname: str
    difficulty: SecurityLevel
    objective: str
    reward: float
    status: str = "available"
    assigned_to: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    ices: List[ICE] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.mission_id,
            "target": self.target_ip,
            "hostname": self.target_hostname,
            "difficulty": self.difficulty.value,
            "objective": self.objective,
            "reward": self.reward,
            "status": self.status,
            "assigned": self.assigned_to,
            "ices": [ice.to_dict() for ice in self.ices],
        }


@dataclass
class NetrunnerState:
    access_points: List[AccessPoint] = field(default_factory=list)
    missions: List[Mission] = field(default_factory=list)
    compromised: List[str] = field(default_factory=list)
    total_rewards: float = 0.0
    hack_attempts: int = 0
    successful_hacks: int = 0
    last_scan_time: Optional[float] = None

    def get_map(self) -> Dict[str, Any]:
        return {
            "nodes": [ap.to_dict() for ap in self.access_points],
            "compromised": self.compromised,
            "mission_count": len(self.missions),
            "total_rewards": self.total_rewards,
        }


NETRUNNER_SECRET = "aura-netrunner-2026"


def generate_access_points(count: int = 8, subnet: str = "192.168.1") -> List[AccessPoint]:
    """Genera access points aleatorios para la red local."""
    types = list(NodeType)
    securities = list(SecurityLevel)
    statuses = list(AccessStatus)
    services_pool = [
        "ssh", "http", "https", "ftp", "smb", "telnet", "mysql",
        "redis", "nginx", "apache", "mysql", "docker", "vnc", "rdp",
    ]
    ap_types = [
        "Router", "Desktop PC", "Laptop", "Smart TV", "Printer",
        "Security Cam", "IoT Hub", "Server", "Mobile Device",
    ]

    aps: List[AccessPoint] = []
    for i in range(count):
        ip = f"{subnet}.{random.randint(2, 254)}"
        mac = ":".join(f"{random.randint(0, 255):02x}" for _ in range(6))
        node_type = random.choice(types)
        security = random.choices(
            securities, weights=[40, 30, 20, 10], k=1
        )[0]
        status = random.choices(
            statuses, weights=[30, 20, 30, 10, 10], k=1
        )[0]
        svc_count = random.randint(1, 5)
        services = random.sample(services_pool, svc_count)
        ap_type_name = random.choice(ap_types)

        ap = AccessPoint(
            ip=ip,
            mac=mac,
            node_type=node_type,
            security=security,
            status=status,
            port=random.choice([22, 80, 443, 3389, 8080, 8443]),
            hostname=f"{ap_type_name.lower().replace(' ', '-')}.local",
            services=services,
            signal_strength=random.randint(-90, -40),
        )
        aps.append(ap)

    logger.info("Generados %d access points", count)
    return aps


BONUS_MISSIONS = [
    {
        "mission_id": "NRK-BOSS-001",
        "title": "Breach Corporate Firewall",
        "target_ip": "10.0.0.1",
        "target_hostname": "corp-firewall.corp.local",
        "level": 5,
        "difficulty": SecurityLevel.HIGH,
        "objective": "Breach the corporate firewall to access internal network",
        "reward": 2.50,
        "description": "Penetrate the hardened perimeter firewall of a corporate network",
    },
    {
        "mission_id": "NRK-BOSS-002",
        "title": "Steal Data Vault",
        "target_ip": "10.0.1.100",
        "target_hostname": "vault.datacenter.local",
        "level": 7,
        "difficulty": SecurityLevel.CRITICAL,
        "objective": "Extract encrypted data from the central vault",
        "reward": 5.00,
        "description": "Infiltrate the data vault and exfiltrate encrypted sensitive files",
    },
    {
        "mission_id": "NRK-BOSS-003",
        "title": "Corrupt ICE Network",
        "target_ip": "10.0.2.50",
        "target_hostname": "ice-grid.security.local",
        "level": 8,
        "difficulty": SecurityLevel.CRITICAL,
        "objective": "Corrupt the ICE detection grid to create blind spots",
        "reward": 7.50,
        "description": "Deploy payloads to disable ICE monitoring across the security grid",
    },
    {
        "mission_id": "NRK-BOSS-004",
        "title": "Become System Admin",
        "target_ip": "10.0.0.254",
        "target_hostname": "root.admin.local",
        "level": 10,
        "difficulty": SecurityLevel.CRITICAL,
        "objective": "Escalate privileges to gain full system admin access",
        "reward": 15.00,
        "description": "Privilege escalation to root across the entire infrastructure",
    },
    {
        "mission_id": "NRK-BOSS-005",
        "title": "Hack The Planet",
        "target_ip": "0.0.0.0",
        "target_hostname": "the-planet.global",
        "level": 15,
        "difficulty": SecurityLevel.CRITICAL,
        "objective": "Boss level: Compromise global infrastructure",
        "reward": 50.00,
        "description": "FINAL BOSS: Take control of the global network backbone",
    },
]


def generate_bonus_missions(state: Optional[NetrunnerState] = None) -> List[Mission]:
    """Genera misiones especiales de alto nivel."""
    missions: List[Mission] = []
    existing_targets = set()
    if state:
        existing_targets = {m.target_ip for m in state.missions}

    for bm in BONUS_MISSIONS:
        if bm["target_ip"] in existing_targets:
            continue

        ap = AccessPoint(
            ip=bm["target_ip"],
            mac="AA:BB:CC:DD:EE:FF",
            node_type=NodeType.SERVER,
            security=bm["difficulty"],
            status=AccessStatus.OPEN,
            port=443,
            hostname=bm["target_hostname"],
            services=["ssh", "https", "admin"],
            signal_strength=-30,
        )

        mission = Mission(
            mission_id=bm["mission_id"],
            target_ip=bm["target_ip"],
            target_hostname=bm["target_hostname"],
            difficulty=bm["difficulty"],
            objective=bm["objective"],
            reward=bm["reward"],
            ices=generate_ices_for_ap(ap),
        )
        missions.append(mission)

    logger.info("Generadas %d misiones bonus", len(missions))
    return missions


def generate_ices_for_ap(ap: AccessPoint) -> List[ICE]:
    """Genera ICEs segun el nivel de seguridad del access point."""
    ices: List[ICE] = []
    security_weights = {
        SecurityLevel.LOW: (1, 2),
        SecurityLevel.MEDIUM: (2, 4),
        SecurityLevel.HIGH: (4, 6),
        SecurityLevel.CRITICAL: (6, 8),
    }
    min_str, max_str = security_weights.get(ap.security, (2, 4))
    ice_types = ["Firewall", "Honeypot", "IDS", "Trap", "Daemon", "Proxy"]
    trap_types = ["none", "trace", "lock", "crash", "alert_admin"]
    count = random.randint(min_str, max_str)

    for i in range(count):
        ice = ICE(
            name=f"ICE-{ap.ip.split('.')[-1]}-{i+1}",
            ice_type=random.choice(ice_types),
            strength=random.randint(min_str, max_str + 2),
            trap_type=random.choice(trap_types) if ap.security in (SecurityLevel.HIGH, SecurityLevel.CRITICAL) else "none",
        )
        ices.append(ice)
    return ices


def generate_missions_from_aps(aps: List[AccessPoint], state: NetrunnerState) -> List[Mission]:
    """Genera misiones basadas en access points descubiertos."""
    missions: List[Mission] = []
    existing_targets = {m.target_ip for m in state.missions}

    for ap in aps:
        if ap.ip in existing_targets:
            continue
        if ap.status in (AccessStatus.COMPROMISED, AccessStatus.HONEYPOT):
            continue

        reward_map = {
            SecurityLevel.LOW: random.uniform(0.05, 0.15),
            SecurityLevel.MEDIUM: random.uniform(0.15, 0.35),
            SecurityLevel.HIGH: random.uniform(0.35, 0.75),
            SecurityLevel.CRITICAL: random.uniform(0.75, 1.50),
        }
        reward = reward_map.get(ap.security, 0.1)
        objectives = [
            f"Access {ap.hostname}",
            f"Extract data from {ap.ip}",
            f"Compromise {ap.node_type.value} at {ap.ip}",
            f"Pivot through {ap.ip} to internal network",
            f"Map services on {ap.ip}",
        ]

        mission = Mission(
            mission_id=f"NRK-{int(time.time())}-{random.randint(100, 999)}",
            target_ip=ap.ip,
            target_hostname=ap.hostname,
            difficulty=ap.security,
            objective=random.choice(objectives),
            reward=reward,
            ices=generate_ices_for_ap(ap),
        )
        missions.append(mission)

    logger.info("Generadas %d misiones", len(missions))
    return missions


def generate_bonus_missions(state: Optional[NetrunnerState] = None) -> List[Mission]:
    """Genera misiones especiales de alto nivel."""
    missions: List[Mission] = []
    existing_targets = set()
    if state:
        existing_targets = {m.target_ip for m in state.missions}

    for bm in BONUS_MISSIONS:
        if bm["target_ip"] in existing_targets:
            continue

        ap = AccessPoint(
            ip=bm["target_ip"],
            mac="AA:BB:CC:DD:EE:FF",
            node_type=NodeType.SERVER,
            security=bm["difficulty"],
            status=AccessStatus.OPEN,
            port=443,
            hostname=bm["target_hostname"],
            services=["ssh", "https", "admin"],
            signal_strength=-30,
        )

        mission = Mission(
            mission_id=bm["mission_id"],
            target_ip=bm["target_ip"],
            target_hostname=bm["target_hostname"],
            difficulty=bm["difficulty"],
            objective=bm["objective"],
            reward=bm["reward"],
            ices=generate_ices_for_ap(ap),
        )
        missions.append(mission)

    logger.info("Generadas %d misiones bonus", len(missions))
    return missions


def attempt_hack(mission: Mission, skill: int = 5) -> Dict[str, Any]:
    """Intenta hackear un access point. Retorna resultado."""
    hack_result = {
        "mission_id": mission.mission_id,
        "target": mission.target_ip,
        "success": False,
        "damage_taken": 0,
        "traps_triggered": [],
        "ices_breached": 0,
    }

    for ice in mission.ices:
        if ice.is_breached(skill):
            hack_result["ices_breached"] += 1
        else:
            ice.triggered = True
            hack_result["traps_triggered"].append(ice.name)
            if ice.trap_type != "none":
                damage = random.randint(1, min(ice.strength, 10))
                hack_result["damage_taken"] += damage

    if not hack_result["traps_triggered"] or hack_result["ices_breached"] > len(mission.ices) // 2:
        hack_result["success"] = True
    elif hack_result["ices_breached"] >= len(mission.ices) // 2:
        hack_result["success"] = random.random() > 0.3

    return hack_result


def process_hack_result(
    hack_result: Dict[str, Any],
    mission: Mission,
    state: NetrunnerState,
    event_bus=None,
) -> Dict[str, Any]:
    """Procesa resultado de hack y emite eventos para el daemon."""
    mission.status = "completed" if hack_result["success"] else "failed"
    mission.completed_at = time.time()
    state.hack_attempts += 1

    if hack_result["success"]:
        state.successful_hacks += 1
        state.total_rewards += mission.reward
        if mission.target_ip not in state.compromised:
            state.compromised.append(mission.target_ip)
        if event_bus:
            event_bus.emit_simple("netrunner_hack_success", {
                "mission_id": mission.mission_id,
                "target": mission.target_ip,
                "reward": mission.reward,
                "total_rewards": state.total_rewards,
                "ices_breached": hack_result["ices_breached"],
                "timestamp": datetime.now().isoformat(),
            }, agent="netrunner")
            logger.info("Hack exitoso: %s -> +$%.2f", mission.target_ip, mission.reward)
    else:
        if event_bus:
            event_bus.emit_simple("netrunner_hack_fail", {
                "mission_id": mission.mission_id,
                "target": mission.target_ip,
                "damage": hack_result["damage_taken"],
                "traps": hack_result["traps_triggered"],
                "timestamp": datetime.now().isoformat(),
            }, agent="netrunner")
            logger.info("Hack fallido: %s", mission.target_ip)

    hack_result["mission"] = mission.to_dict()
    return hack_result
