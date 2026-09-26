"""BLOQUE 89 - Mesh consensus package (100% local, offline)."""
from backend.mesh_consensus.core import ConsensusRound, QUORUM_RATIO
from backend.mesh_consensus.engine import (
    SwarmConsensusEngine, get_consensus_engine, reset_consensus_engine,
)

__all__ = ["ConsensusRound", "QUORUM_RATIO", "SwarmConsensusEngine",
           "get_consensus_engine", "reset_consensus_engine"]

from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)
