"""
Módulo de inicialización para los nodos avanzados de Shadow-Core.
Este archivo define la estructura base y los puntos de entrada para los nodos modulares.
"""

from .NOD_WIFI_DEAUTH import NOD_WIFI_DEAUTH
from .NOD_PHANTOM_OSINT import NOD_PHANTOM_OSINT
from .NOD_SIGNAL_STRIKE import NOD_SIGNAL_STRIKE

# Diccionario de nodos disponibles
NODES_REGISTRY = {
    "NOD_WIFI_DEAUTH": NOD_WIFI_DEAUTH,
    "NOD_PHANTOM_OSINT": NOD_PHANTOM_OSINT,
    "NOD_SIGNAL_STRIKE": NOD_SIGNAL_STRIKE
}

def get_node(node_id):
    """Obtiene un nodo por su ID."""
    return NODES_REGISTRY.get(node_id)

def list_nodes():
    """Lista todos los nodos disponibles."""
    return list(NODES_REGISTRY.keys())