"""Autonomy subsystem: supervised, self-healing background services."""
from backend.autonomy.supervisor import AutonomousSupervisor, get_supervisor

__all__ = ["AutonomousSupervisor", "get_supervisor"]
