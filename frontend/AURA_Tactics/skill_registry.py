#!/usr/bin/env python3
"""
skill_registry.py — AURA Tactics Skill Registry
================================================
Índice maestro de habilidades del juego AURA Tactics.
Cada skill es un wrapper de solo-lectura sobre una capacidad real de AURA/AME.

Estructura:
  - skill_id: identificador único
  - name: nombre visible en el juego
  - description: descripción narrativa
  - tier: nivel de desbloqueo (1-5)
  - aura_component: módulo real de AURA que representa
  - effect: efecto en el juego (bonificador narrativo)
  - stability_check: qué verifica antes de permitir uso
  - xp_per_use: XP ganado por usar esta habilidad (subproducto)
"""

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)

# ─── Enum de Categorías ───
class SkillCategory(Enum):
    SENSING = "sensing"        # Percepción de red
    ANALYSIS = "analysis"      # Análisis OSINT
    DEFENSE = "defense"        # Protección Gatekeeper
    MOVEMENT = "movement"      # Mesh/Proxy
    COMMAND = "command"        # Swarm control
    TRANSMUTATION = "transmutation"  # Node Zero / AURA Avatar


@dataclass(frozen=True)
class Skill:
    """
    Habilidad del juego — NO modifica la red real.
    Es solo un wrapper narrativo sobre una capacidad existente de AURA.
    """
    skill_id: str
    name: str
    description: str
    category: SkillCategory
    tier: int                     # 1-5
    unlock_level: int             # Nivel de personaje requerido
    aura_module: str              # Ruta del módulo AURA que representa
    aura_function: str            # Función específica dentro del módulo
    stability_check: str          # ID del test de estabilidad requerido
    xp_per_use: int               # XP ganado como subproducto
    cooldown_seconds: int = 0     # Enfriamiento entre usos (narrativo)
    requirements: List[str] = field(default_factory=list)  # Skills requeridas previamente
    
    def validate_aura_available(self) -> bool:
        """Verifica que el módulo AURA real esté disponible (solo-lectura)"""
        try:
            # Solo importar y verificar existencia — NUNCA ejecutar
            module_path = self.aura_module.replace('/', '.')
            __import__(module_path, fromlist=[''])
            return True
        except ImportError:
            logger.warning(f"AURA module not available: {self.aura_module}")
            return False
        except Exception as e:
            logger.error(f"Error checking AURA module {self.aura_module}: {e}")
            return False


# ═══════════════════════════════════════════════════════
# REGISTRO MAESTRO DE HABILIDADES
# Cada entrada mapea 1:1 con una capacidad real de AURA.
# ═══════════════════════════════════════════════════════

SKILL_REGISTRY: Dict[str, Skill] = {
    
    # ── TIER 1 — Habilidades Básicas (Nivel 1) ──
    
    "network_sense": Skill(
        skill_id="network_sense",
        name="Network Sense",
        description="Siente las vibraciones de la red local. Detecta dispositivos conectados y su estado.",
        category=SkillCategory.SENSING,
        tier=1,
        unlock_level=1,
        aura_module="AURA_Core.network_sensor",
        aura_function="get_network_status",
        stability_check="check_read_only_access",
        xp_per_use=5,
        cooldown_seconds=10
    ),
    
    "signal_scan": Skill(
        skill_id="signal_scan",
        name="Signal Scan",
        description="Escanea las señales Wi-Fi circundantes para medir la salud del espectro.",
        category=SkillCategory.SENSING,
        tier=1,
        unlock_level=1,
        aura_module="AME_Core.telemetria_radio",
        aura_function="generate_wifi_radar_data",
        stability_check="check_read_only_access",
        xp_per_use=8,
        cooldown_seconds=15
    ),
    
    # ── TIER 2 — Análisis (Nivel 3) ──
    
    "venice_eye": Skill(
        skill_id="venice_eye",
        name="Venice Eye",
        description="Activa el módulo Venice OSINT para inspeccionar objetivos remotos. Revela información oculta.",
        category=SkillCategory.ANALYSIS,
        tier=2,
        unlock_level=3,
        aura_module="AURA_Core.osint_engine",
        aura_function="execute",
        stability_check="check_osint_safe",
        xp_per_use=15,
        cooldown_seconds=30,
        requirements=["network_sense"]
    ),
    
    "telemetry_reading": Skill(
        skill_id="telemetry_reading",
        name="Telemetry Reading",
        description="Interpreta los flujos de telemetría de los nodos. Revela patrones de rendimiento.",
        category=SkillCategory.ANALYSIS,
        tier=2,
        unlock_level=3,
        aura_module="AURA_Core.telemetry_manager",
        aura_function="get_metrics",
        stability_check="check_read_only_access",
        xp_per_use=10,
        cooldown_seconds=20,
        requirements=["signal_scan"]
    ),
    
    # ── TIER 3 — Defensa (Nivel 5) ──
    
    "gatekeeper_shield": Skill(
        skill_id="gatekeeper_shield",
        name="Gatekeeper Shield",
        description="Despliega un escudo de seguridad alrededor del nodo usando el Gatekeeper. Las amenazas son interceptadas.",
        category=SkillCategory.DEFENSE,
        tier=3,
        unlock_level=5,
        aura_module="AURA_Core.gatekeeper",
        aura_function="validate_action",
        stability_check="check_gatekeeper_read_only",
        xp_per_use=25,
        cooldown_seconds=60,
        requirements=["network_sense", "venice_eye"]
    ),
    
    "mesh_walk": Skill(
        skill_id="mesh_walk",
        name="Mesh Walk",
        description="Camina a través de la malla de proxies. Cambia tu IP de salida para navegar anónimamente.",
        category=SkillCategory.MOVEMENT,
        tier=3,
        unlock_level=5,
        aura_module="Shadow-Core.mesh_config",
        aura_function="rotate_proxy",
        stability_check="check_mesh_idle",
        xp_per_use=20,
        cooldown_seconds=45,
        requirements=["signal_scan"]
    ),
    
    # ── TIER 4 — Comando (Nivel 7) ──
    
    "swarm_command": Skill(
        skill_id="swarm_command",
        name="Swarm Command",
        description="Toma el control del enjambre. Orquesta múltiples nodos para ejecutar tareas coordinadas.",
        category=SkillCategory.COMMAND,
        tier=4,
        unlock_level=7,
        aura_module="AURA_Core.swarm_manager",
        aura_function="assign_task",
        stability_check="check_swarm_idle",
        xp_per_use=40,
        cooldown_seconds=120,
        requirements=["gatekeeper_shield", "telemetry_reading"]
    ),
    
    "proxy_phase": Skill(
        skill_id="proxy_phase",
        name="Proxy Phase",
        description="Despliega un proxy mesh completo entre todos los nodos disponibles. El tráfico se redistribuye.",
        category=SkillCategory.MOVEMENT,
        tier=4,
        unlock_level=7,
        aura_module="Shadow-Core.mesh_config",
        aura_function="execute_via_mesh",
        stability_check="check_mesh_idle",
        xp_per_use=35,
        cooldown_seconds=90,
        requirements=["mesh_walk", "gatekeeper_shield"]
    ),
    
    # ── TIER 5 — Transmutación (Nivel 9) ──
    
    "node_zero": Skill(
        skill_id="node_zero",
        name="Node Zero",
        description="El nodo se convierte en el centro del mesh. Todas las rutas pasan por él. Control total de la red.",
        category=SkillCategory.TRANSMUTATION,
        tier=5,
        unlock_level=9,
        aura_module="AURA_Core.swarm_manager",
        aura_function="get_nodes",
        stability_check="check_read_only_access",
        xp_per_use=100,
        cooldown_seconds=300,
        requirements=["swarm_command", "proxy_phase"]
    ),
    
    "aura_avatar": Skill(
        skill_id="aura_avatar",
        name="AURA Avatar",
        description="El nodo trasciende. Se convierte en un avatar de AURA. Acceso completo a todas las capacidades del ecosistema.",
        category=SkillCategory.TRANSMUTATION,
        tier=5,
        unlock_level=9,
        aura_module="AURA_Core.aura_core",
        aura_function="get_status",
        stability_check="check_read_only_access",
        xp_per_use=150,
        cooldown_seconds=600,
        requirements=["node_zero", "swarm_command"]
    ),
}


# ─── Utilidades del Registry ───

def get_skill(skill_id: str) -> Optional[Skill]:
    """Obtiene una skill por su ID."""
    return SKILL_REGISTRY.get(skill_id)


def get_skills_by_tier(tier: int) -> List[Skill]:
    """Obtiene todas las skills de un tier específico."""
    return [s for s in SKILL_REGISTRY.values() if s.tier == tier]


def get_skills_by_category(category: SkillCategory) -> List[Skill]:
    """Obtiene todas las skills de una categoría."""
    return [s for s in SKILL_REGISTRY.values() if s.category == category]


def get_skills_for_level(level: int) -> List[Skill]:
    """Obtiene todas las skills disponibles para un nivel dado."""
    return [s for s in SKILL_REGISTRY.values() if s.unlock_level <= level]


def get_next_skills_for_level(level: int) -> List[Skill]:
    """Obtiene las skills que se desbloquean al alcanzar un nivel."""
    return [s for s in SKILL_REGISTRY.values() if s.unlock_level == level]


def get_aura_module_map() -> Dict[str, List[str]]:
    """Devuelve un mapeo de módulos AURA a skills del juego.
    Útil para GAME_LOGIC_MAP.md."""
    mapping = {}
    for skill in SKILL_REGISTRY.values():
        module = skill.aura_module
        if module not in mapping:
            mapping[module] = []
        mapping[module].append(skill.skill_id)
    return mapping


def validate_skill_prerequisites(skill_id: str, unlocked_skills: List[str]) -> bool:
    """Valida que se tengan todos los prerequisitos de una skill."""
    skill = get_skill(skill_id)
    if not skill:
        return False
    return all(req in unlocked_skills for req in skill.requirements)


def registry_summary() -> Dict:
    """Resumen del registro para debugging y visualización."""
    return {
        "total_skills": len(SKILL_REGISTRY),
        "by_tier": {
            str(tier): len(get_skills_by_tier(tier))
            for tier in range(1, 6)
        },
        "by_category": {
            cat.value: len(get_skills_by_category(cat))
            for cat in SkillCategory
        },
        "by_level": {
            str(level): len(get_skills_for_level(level))
            for level in range(1, 10)
        },
        "total_aura_modules": len(set(
            s.aura_module for s in SKILL_REGISTRY.values()
        ))
    }


# ─── Punto de entrada ───
if __name__ == "__main__":
    print("=" * 60)
    print("AURA TACTICS — SKILL REGISTRY")
    print("=" * 60)
    print()
    
    summary = registry_summary()
    print(f"Total skills: {summary['total_skills']}")
    print(f"Por tier: {summary['by_tier']}")
    print(f"Por categoría: {summary['by_category']}")
    print(f"Por nivel: {summary['by_level']}")
    print(f"Módulos AURA mapeados: {summary['total_aura_modules']}")
    print()
    
    print("─── Habilidades por Tier ───")
    for tier in range(1, 6):
        print(f"\nTIER {tier}:")
        for skill in get_skills_by_tier(tier):
            reqs = ", ".join(skill.requirements) if skill.requirements else "ninguno"
            print(f"  [{skill.skill_id}] {skill.name}")
            print(f"    → {skill.description[:80]}...")
            print(f"    → Módulo AURA: {skill.aura_module}")
            print(f"    → Requisitos: {reqs}")
            print(f"    → XP/uso: {skill.xp_per_use}")
    print()
    print("─── Mapeo Módulos AURA ↔ Skills ───")
    for module, skills in get_aura_module_map().items():
        print(f"  {module}: {', '.join(skills)}")